from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async
from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.db.models.functions import Lower
from django.db.transaction import atomic
from django.utils.timezone import now
from django.views.decorators.debug import sensitive_variables

from api_auth.enums import VerificationPurposes
from api_auth.models import ApiUser
from api_auth.services.account import ensure_strong_password, invalid_code_error
from api_auth.services.verification import check_code_sync
from api_catalogs.models import BusinessType, Currency, InstitutionType
from api_core.services.uploads import UploadKinds, verify_upload
from api_exceptions.enums import BadRequestErrorTypes, RequestScopes
from api_exceptions.errors import BadRequestError, ConflictError, NotFoundError
from api_moderation.enums import API_STATUS, VerificationStates
from api_moderation.models import (
    VerificationRequest,
    VerificationResolution,
    VerificationStatus,
)
from api_organizations.models import (
    Business,
    BusinessHours,
    CulturalInstitution,
    Photo,
    SignatureDish,
)
from api_organizations.schemas.application import (
    ApplicationGet,
    BusinessResubmitPost,
    InstitutionResubmitPost,
    MunicipalityResubmitPost,
    ReasonGet,
    ResolutionGet,
)
from api_roles.services import grant_role_sync, organization_of_sync
from api_territory.models import City, Municipality

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Final
    from uuid import UUID

    from api_organizations.schemas.application import (
        ApplicantPost,
        BusinessApplicationPost,
        InstitutionApplicationPost,
        MunicipalityApplicationPost,
        ResubmitPost,
    )

########################################################################################

# - el rol de sistema de cada clase de organización: el de quien se postula
ROLE_NAMES: Final[dict[str, str]] = {
    "business": "Negocio",
    "institution": "Institución",
    "municipality": "Alcaldía",
}

# - la llave de `solicitud_verificacion` que corresponde a cada clase
REQUEST_FIELDS: Final[dict[str, str]] = {
    "business": "business",
    "institution": "institution",
    "municipality": "municipality",
}


@dataclass(frozen=True, slots=True)
class Registered:
    user: ApiUser
    request: VerificationRequest


########################################################################################
# Errores con el nombre del campo


def field_error(field: str, message: str) -> BadRequestError:
    return BadRequestError(
        field_errors={field: message},
        type=BadRequestErrorTypes.FAILED_VALIDATION,
    ).scoped(RequestScopes.BODY)


def taken(field: str, message: str) -> ConflictError:
    return ConflictError(field_errors={field: message}).scoped(RequestScopes.BODY)


########################################################################################
# Lo que hay que resolver antes de abrir la transacción


def find_city(city_id: UUID) -> City:
    city: City | None = City.objects.filter(pk=city_id).first()

    if city is None:
        raise field_error("city_id", "Esa ciudad no existe.")

    return city


def find_active[Model: BusinessType | InstitutionType](
    model: type[Model],
    pk: UUID,
    field: str,
) -> Model:
    found: Model | None = model.objects.filter(active=True, pk=pk).first()

    if found is None:
        raise field_error(field, "Esa opción no existe.")

    return found


########################################################################################
# El alta, común a las tres clases


# Crea la cuenta de quien se postula, su organización y el expediente de verificación, y
# le da el rol de su clase sobre esa organización, todo en una sola transacción: si algo
# falla, el código del correo vuelve a servir.
def open_application_sync(
    *,
    applicant: ApplicantPost,
    create: Callable[[], Business | CulturalInstitution | Municipality],
    kind: str,
) -> Registered:
    # primero se comprueba aparte: un código equivocado suma un intento, y ese intento
    # tiene que quedar guardado aunque la petición termine en error
    if not check_code_sync(
        code=applicant.code,
        consume=False,
        destination=applicant.email,
        purpose=VerificationPurposes.EMAIL,
    ):
        raise invalid_code_error()

    def persist() -> Registered:
        with atomic():
            if not check_code_sync(
                code=applicant.code,
                consume=True,
                destination=applicant.email,
                purpose=VerificationPurposes.EMAIL,
            ):
                raise invalid_code_error()

            user: ApiUser = ApiUser.objects.create_user(
                email=applicant.email,
                first_name=applicant.first_name,
                last_name=applicant.last_name,
                password=applicant.password,
            )

            organization = create()

            request: VerificationRequest = VerificationRequest.objects.create(
                status=VerificationStatus.objects.get(
                    code=VerificationStates.SUBMITTED
                ),
                **{REQUEST_FIELDS[kind]: organization},
            )

            grant_role_sync(
                granted_by=user,
                role=Group.objects.get(name=ROLE_NAMES[kind]),
                scope_object=organization,
                user=user,
            )

            return Registered(user=user, request=request)

    try:
        return persist()
    except IntegrityError as i:
        raise ConflictError.from_integrity_error(i).scoped(RequestScopes.BODY) from i


@sensitive_variables()
async def ensure_applicant_password(applicant: ApplicantPost) -> None:
    # primero la contraseña, para no gastar el código de quien la eligió mal
    await sync_to_async(ensure_strong_password)(
        applicant.password,
        user=ApiUser(
            email=applicant.email,
            first_name=applicant.first_name,
            last_name=applicant.last_name,
        ),
    )


########################################################################################
# Comercio


def register_business_sync(data: BusinessApplicationPost) -> Registered:
    city: City = find_city(data.city_id)
    business_type: BusinessType = find_active(
        BusinessType,
        data.business_type_id,
        "business_type_id",
    )
    currency: Currency | None = Currency.objects.filter(
        code=data.signature_dish.currency
    ).first()

    if currency is None:
        raise field_error("signature_dish.currency", "Esa moneda no existe.")

    if Business.objects.filter(ruc=data.ruc).exists():
        raise taken("ruc", "Ya hay un comercio registrado con ese RUC.")

    # la foto ya tiene que estar subida (una consulta al almacenamiento: fuera de la
    # transacción)
    verify_upload(
        UploadKinds.SIGNATURE_DISH_PHOTO,
        data.signature_dish.photo_key,
        field="signature_dish.photo_key",
    )

    def create() -> Business:
        business: Business = Business.objects.create(
            address=data.address,
            alternate_phone=data.alternate_phone,
            business_type=business_type,
            city=city,
            latitude=data.latitude,
            longitude=data.longitude,
            name=data.name,
            phone=data.phone,
            ruc=data.ruc,
        )

        BusinessHours.objects.bulk_create(
            BusinessHours(
                business=business,
                closed=row.closed,
                closes=row.closes,
                opens=row.opens,
                weekday=row.weekday,
            )
            for row in data.hours
        )

        photo: Photo = Photo.objects.create(
            business=business,
            file_key=data.signature_dish.photo_key,
        )

        SignatureDish.objects.create(
            business=business,
            currency=currency,
            description=data.signature_dish.description,
            name=data.signature_dish.name,
            photo=photo,
            reference_price=data.signature_dish.reference_price,
        )

        return business

    return open_application_sync(applicant=data, create=create, kind="business")


@sensitive_variables()
async def register_business(data: BusinessApplicationPost) -> Registered:
    await ensure_applicant_password(data)

    return await sync_to_async(register_business_sync)(data)


########################################################################################
# Institución cultural


def register_institution_sync(data: InstitutionApplicationPost) -> Registered:
    city: City = find_city(data.city_id)
    institution_type: InstitutionType = find_active(
        InstitutionType,
        data.institution_type_id,
        "institution_type_id",
    )

    if (
        CulturalInstitution.objects
        .filter(
            city=city,
        )
        .annotate(lowered=Lower("name"))
        .filter(lowered=data.name.lower())
        .exists()
    ):
        raise taken("name", "Ya hay una institución con ese nombre en esa ciudad.")

    verify_upload(
        UploadKinds.LEGAL_DOCUMENT,
        data.document_key,
        field="document_key",
    )

    def create() -> CulturalInstitution:
        return CulturalInstitution.objects.create(
            city=city,
            contact_email=data.contact_email,
            document_key=data.document_key,
            institution_type=institution_type,
            name=data.name,
            phone=data.phone,
        )

    return open_application_sync(applicant=data, create=create, kind="institution")


@sensitive_variables()
async def register_institution(data: InstitutionApplicationPost) -> Registered:
    await ensure_applicant_password(data)

    return await sync_to_async(register_institution_sync)(data)


########################################################################################
# Alcaldía


def register_municipality_sync(data: MunicipalityApplicationPost) -> Registered:
    city: City = find_city(data.city_id)

    if Municipality.objects.filter(city=city).exists():
        raise taken("city_id", "Esa ciudad ya tiene una alcaldía registrada.")

    verify_upload(
        UploadKinds.LEGAL_DOCUMENT,
        data.document_key,
        field="document_key",
    )

    def create() -> Municipality:
        return Municipality.objects.create(
            city=city,
            contact_email=data.contact_email,
            document_key=data.document_key,
            name=data.name,
            phone=data.phone,
        )

    return open_application_sync(applicant=data, create=create, kind="municipality")


@sensitive_variables()
async def register_municipality(data: MunicipalityApplicationPost) -> Registered:
    await ensure_applicant_password(data)

    return await sync_to_async(register_municipality_sync)(data)


########################################################################################
# Lo que ve quien se postuló


def organization_record(request: VerificationRequest) -> tuple[str, Any]:
    # la organización del expediente y de qué clase es: solo una de las tres llaves
    for kind, record in (
        ("business", request.business),
        ("institution", request.institution),
        ("municipality", request.municipality),
    ):
        if record is not None:
            return kind, record

    raise ValueError("Un expediente sin organización no debería existir.")


def application_payload(request: VerificationRequest) -> ApplicationGet:
    found: Any = request
    kind, record = organization_record(request)

    resolution: VerificationResolution | None = (
        VerificationResolution.objects
        .select_related("reason")
        .filter(request=request)
        .first()
    )

    resolved: Any = resolution

    return ApplicationGet(
        id=found.pk,
        kind=kind,  # ty: ignore[invalid-argument-type]
        organization_id=record.pk,
        organization_name=str(record.name),
        resolution=(
            None
            if resolved is None
            else ResolutionGet(
                approved=bool(resolved.approved),
                note=str(resolved.note),
                reason=(
                    None
                    if resolved.reason is None
                    else ReasonGet(
                        code=str(resolved.reason.code),
                        label=str(resolved.reason.label),
                    )
                ),
                resolved_at=resolved.resolved_at,
            )
        ),
        resolved_at=found.resolved_at,
        status=API_STATUS[str(found.status.code)],  # ty: ignore[invalid-argument-type]
        submitted_at=found.submitted_at,
    )


# La solicitud más reciente de la organización de la persona. El expediente rechazado
# queda en el historial; corregir y volver a enviar abre otro, y ese es el último.
def latest_application_sync(user: ApiUser) -> VerificationRequest:
    organization = organization_of_sync(user)

    if organization is None:
        raise NotFoundError(detail="Tu cuenta no tiene una solicitud de organización.")

    request: VerificationRequest | None = (
        VerificationRequest.objects
        .select_related("business", "institution", "municipality", "status")
        .filter(**{f"{REQUEST_FIELDS[organization.kind]}_id": organization.id})
        .order_by("-submitted_at")
        .first()
    )

    if request is None:
        raise NotFoundError(detail="Tu cuenta no tiene una solicitud de organización.")

    return request


########################################################################################
# Corregir y volver a enviar


def start_new_request(
    record: Business | CulturalInstitution | Municipality,
    kind: str,
) -> VerificationRequest:
    # el expediente rechazado se conserva; corregir abre otro, que vuelve a la bandeja
    return VerificationRequest.objects.create(
        status=VerificationStatus.objects.get(code=VerificationStates.SUBMITTED),
        **{REQUEST_FIELDS[kind]: record},
    )


def resubmit_business(
    record: Business, data: BusinessResubmitPost
) -> VerificationRequest:
    city: City = find_city(data.city_id)
    business_type: BusinessType = find_active(
        BusinessType,
        data.business_type_id,
        "business_type_id",
    )
    currency: Currency | None = Currency.objects.filter(
        code=data.signature_dish.currency
    ).first()

    if currency is None:
        raise field_error("signature_dish.currency", "Esa moneda no existe.")

    if Business.objects.filter(ruc=data.ruc).exclude(pk=record.pk).exists():
        raise taken("ruc", "Ya hay un comercio registrado con ese RUC.")

    verify_upload(
        UploadKinds.SIGNATURE_DISH_PHOTO,
        data.signature_dish.photo_key,
        field="signature_dish.photo_key",
    )

    def persist() -> VerificationRequest:
        with atomic():
            target: Any = record
            target.address = data.address
            target.alternate_phone = data.alternate_phone
            target.business_type = business_type
            target.city = city
            target.latitude = data.latitude
            target.longitude = data.longitude
            target.name = data.name
            target.phone = data.phone
            # el RUC se corrige mientras la ficha no está verificada
            target.ruc = data.ruc
            target.save()

            BusinessHours.objects.filter(business=record).delete()
            BusinessHours.objects.bulk_create(
                BusinessHours(
                    business=record,
                    closed=row.closed,
                    closes=row.closes,
                    opens=row.opens,
                    weekday=row.weekday,
                )
                for row in data.hours
            )

            # reemplazar el platillo es retirar el vigente e insertar el nuevo
            SignatureDish.objects.filter(
                business=record,
                withdrawn_at__isnull=True,
            ).update(withdrawn_at=now())

            photo: Photo = Photo.objects.create(
                business=record,
                file_key=data.signature_dish.photo_key,
            )
            SignatureDish.objects.create(
                business=record,
                currency=currency,
                description=data.signature_dish.description,
                name=data.signature_dish.name,
                photo=photo,
                reference_price=data.signature_dish.reference_price,
            )

            return start_new_request(record, "business")

    return persist()


def resubmit_institution(
    record: CulturalInstitution,
    data: InstitutionResubmitPost,
) -> VerificationRequest:
    city: City = find_city(data.city_id)
    institution_type: InstitutionType = find_active(
        InstitutionType,
        data.institution_type_id,
        "institution_type_id",
    )

    if (
        CulturalInstitution.objects
        .filter(city=city)
        .annotate(lowered=Lower("name"))
        .filter(lowered=data.name.lower())
        .exclude(pk=record.pk)
        .exists()
    ):
        raise taken("name", "Ya hay una institución con ese nombre en esa ciudad.")

    verify_upload(UploadKinds.LEGAL_DOCUMENT, data.document_key, field="document_key")

    def persist() -> VerificationRequest:
        with atomic():
            target: Any = record
            target.city = city
            target.contact_email = data.contact_email
            target.document_key = data.document_key
            target.institution_type = institution_type
            target.name = data.name
            target.phone = data.phone
            target.save()

            return start_new_request(record, "institution")

    return persist()


def resubmit_municipality(
    record: Municipality,
    data: MunicipalityResubmitPost,
) -> VerificationRequest:
    city: City = find_city(data.city_id)

    if Municipality.objects.filter(city=city).exclude(pk=record.pk).exists():
        raise taken("city_id", "Esa ciudad ya tiene una alcaldía registrada.")

    verify_upload(UploadKinds.LEGAL_DOCUMENT, data.document_key, field="document_key")

    def persist() -> VerificationRequest:
        with atomic():
            target: Any = record
            target.city = city
            target.contact_email = data.contact_email
            target.document_key = data.document_key
            target.name = data.name
            target.phone = data.phone
            target.save()

            return start_new_request(record, "municipality")

    return persist()


# Quien se postuló corrige lo que el equipo rechazó y lo manda de nuevo. Solo se puede
# cuando el último expediente se rechazó: mientras está en revisión no se toca, y una
# organización aprobada ya no se edita por aquí.
def resubmit_sync(user: ApiUser, data: ResubmitPost) -> VerificationRequest:
    latest: VerificationRequest = latest_application_sync(user)
    kind, record = organization_record(latest)

    if latest.resolved_at is None:
        raise ConflictError(detail="Tu solicitud todavía está en revisión.")

    resolution: Any = VerificationResolution.objects.filter(request=latest).first()

    if resolution is None or resolution.approved:
        raise ConflictError(detail="Tu solicitud ya fue aprobada.")

    if data.kind != kind:
        raise field_error("kind", "Esos datos no son de tu tipo de organización.")

    try:
        match data:
            case BusinessResubmitPost():
                return resubmit_business(record, data)
            case InstitutionResubmitPost():
                return resubmit_institution(record, data)
            case MunicipalityResubmitPost():
                return resubmit_municipality(record, data)
    except IntegrityError as i:
        raise ConflictError.from_integrity_error(i).scoped(RequestScopes.BODY) from i
