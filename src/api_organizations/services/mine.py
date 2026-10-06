from typing import TYPE_CHECKING, Any

from api_core.services.uploads import read_url
from api_organizations.models import Business, CulturalInstitution, SignatureDish
from api_organizations.schemas.mine import (
    MineApplicationGet,
    Submitted,
    SubmittedBusinessGet,
    SubmittedDishGet,
    SubmittedFileGet,
    SubmittedHoursGet,
    SubmittedInstitutionGet,
    SubmittedMunicipalityGet,
)
from api_organizations.services.application import (
    application_payload,
    organization_record,
)

if TYPE_CHECKING:
    from api_moderation.models import VerificationRequest
    from api_territory.models import Municipality

########################################################################################


def file_payload(key: str) -> SubmittedFileGet:
    return SubmittedFileGet(key=key, url=read_url(key))


def business_payload(record: Business) -> SubmittedBusinessGet:
    # los atributos de los modelos de Django no tienen tipos para ty: se leen sin ellos
    business: Any = record

    dish: Any = (
        SignatureDish.objects
        .select_related("currency", "photo")
        .filter(business=record, withdrawn_at__isnull=True)
        .first()
    )

    return SubmittedBusinessGet(
        address=str(business.address),
        alternate_phone=str(business.alternate_phone),
        business_type_id=business.business_type_id,
        city_id=business.city_id,
        hours=[
            SubmittedHoursGet(
                closed=bool(row.closed),
                closes=row.closes,
                opens=row.opens,
                weekday=int(row.weekday),
            )
            for row in business.hours.order_by("weekday")
        ],
        kind="business",
        latitude=float(business.latitude),
        longitude=float(business.longitude),
        name=str(business.name),
        phone=str(business.phone),
        ruc=str(business.ruc),
        signature_dish=(
            None
            if dish is None
            else SubmittedDishGet(
                currency=str(dish.currency.code),
                description=str(dish.description),
                name=str(dish.name),
                photo=(
                    None
                    if dish.photo is None
                    else file_payload(str(dish.photo.file_key))
                ),
                reference_price=float(dish.reference_price),
            )
        ),
    )


def institution_payload(record: CulturalInstitution) -> SubmittedInstitutionGet:
    institution: Any = record

    return SubmittedInstitutionGet(
        city_id=institution.city_id,
        contact_email=str(institution.contact_email),
        document=file_payload(str(institution.document_key)),
        institution_type_id=institution.institution_type_id,
        kind="institution",
        name=str(institution.name),
        phone=str(institution.phone),
    )


def municipality_payload(record: Municipality) -> SubmittedMunicipalityGet:
    municipality: Any = record

    return SubmittedMunicipalityGet(
        city_id=municipality.city_id,
        contact_email=str(municipality.contact_email),
        document=file_payload(str(municipality.document_key)),
        kind="municipality",
        name=str(municipality.name),
        phone=str(municipality.phone),
    )


########################################################################################


def submitted_payload(request: VerificationRequest) -> Submitted:
    kind, record = organization_record(request)

    match kind:
        case "business":
            return business_payload(record)
        case "institution":
            return institution_payload(record)
        case _:
            return municipality_payload(record)


# La solicitud con los datos que mandó, listos para llenar el formulario de corrección.
def mine_payload(request: VerificationRequest) -> MineApplicationGet:
    return MineApplicationGet(
        **dict(application_payload(request)),
        submitted=submitted_payload(request),
    )
