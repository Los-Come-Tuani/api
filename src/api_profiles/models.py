from typing import TYPE_CHECKING

from django.db.models import (
    BooleanField,
    CharField,
    CheckConstraint,
    DateField,
    DateTimeField,
    DecimalField,
    F,
    Index,
    IntegerField,
    OneToOneField,
    Q,
    TextField,
    UniqueConstraint,
)
from django.db.models.deletion import CASCADE, RESTRICT
from django.db.models.fields.related import ForeignKey
from django.db.models.functions import Now
from django.utils.timezone import now
from pgtrigger import (
    Before,
    Insert,
    Q as PgQ,
    ReadOnly,
    Trigger,
    Update,
    UpdateOf,
)

from api_auth.models import ApiUser
from api_catalogs.models import CredentialType, Language, Reason, ServiceType
from api_core.models.base import ApiModel
from api_profiles.enums import LanguageLevels, Verdicts
from api_territory.models import City
from api_utils.db import track_table

if TYPE_CHECKING:
    from collections.abc import Sequence

# Los disparadores que nombran columnas (UpdateOf) llevan el nombre real de la columna,
# en español: pgtrigger no resuelve db_column. Las condiciones (Q) sí usan campos.
########################################################################################
# Las tablas y columnas están en español (modelo de dominio, `Convenciones`); el código
# Python sigue en inglés. Cada campo declara su `db_column`.
########################################################################################


# Los estados del perfil de un prestador. No son los de su cuenta: un prestador
# suspendido entra a la app para regularizar sus papeles, pero no aparece en búsquedas
# ni recibe contrataciones.
@track_table(meta={"db_table": "estado_prestador_cambio"})
class ProviderStatus(ApiModel):
    code = CharField(db_column="codigo", max_length=24)
    label = CharField(db_column="etiqueta", max_length=60)
    is_visible = BooleanField(db_column="es_visible")
    accepts_bookings = BooleanField(db_column="acepta_reservas")

    class Meta(ApiModel.Meta):
        db_table: str = "estado_prestador"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_estadoprestador_codigo"),
        )


########################################################################################


# El perfil profesional de un guía o de un traductor (RF-P-01). Una cuenta ejerce un
# solo papel (RF-S-26): quien es turista, opera una organización o es del equipo no
# tiene, además, un perfil de prestador.
@track_table(meta={"db_table": "perfil_prestador_cambio"})
class ProviderProfile(ApiModel):
    user = OneToOneField(
        db_column="usuario_id",
        on_delete=CASCADE,
        related_name="provider_profile",
        to=ApiUser,
    )
    status = ForeignKey(
        db_column="estado_id",
        on_delete=RESTRICT,
        related_name="profiles",
        to=ProviderStatus,
    )

    # dónde opera; nulo es todo el país (la cobertura nacional del INTUR)
    city = ForeignKey(
        db_column="ciudad_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="providers",
        to=City,
    )
    phone = CharField(db_column="telefono", max_length=30)
    # lo que ve el turista
    presentation = TextField(
        blank=True, db_column="presentacion", db_default="", default=""
    )
    # la clave de la foto en el almacenamiento de archivos
    photo_key = CharField(
        blank=True,
        db_column="foto_clave",
        db_default="",
        default="",
        max_length=255,
    )
    # lleva turistas en su vehículo: se le piden licencia de conducir y seguro
    carries_tourists = BooleanField(
        db_column="lleva_turistas", db_default=False, default=False
    )

    # derivados de las reseñas (llegan con F7): sin reseñas no hay promedio, no un cero
    rating_average = DecimalField(
        db_column="promedio_valoracion",
        db_default=None,
        decimal_places=2,
        default=None,
        max_digits=3,
        null=True,
    )
    reviews_count = IntegerField(db_column="total_resenas", db_default=0, default=0)

    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)
    # nulo hasta la primera aprobación
    approved_at = DateTimeField(
        db_column="aprobado_en",
        db_default=None,
        default=None,
        null=True,
    )

    class Meta(ApiModel.Meta):
        db_table: str = "perfil_prestador"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(rating_average__isnull=True)
                | (Q(rating_average__gte=1) & Q(rating_average__lte=5)),
                name="chk_perfilprestador_promedio_rango",
            ),
            CheckConstraint(
                condition=Q(reviews_count=0, rating_average__isnull=True)
                | Q(reviews_count__gt=0, rating_average__isnull=False),
                name="chk_perfilprestador_promedio_coherente",
            ),
            CheckConstraint(
                condition=Q(approved_at__isnull=True)
                | Q(approved_at__gte=F("created_at")),
                name="chk_perfilprestador_aprobado_coherente",
            ),
        )

        indexes: Sequence[Index] = (
            # el listado por reputación: los nuevos, sin promedio, quedan abajo
            Index(
                F("status"),
                F("rating_average").desc(nulls_last=True),
                name="idx_perfilprestador_busqueda",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(
                fields=["created_at", "user"],
                name="trg_perfilprestador_readonly",
            ),
            # un solo papel por cuenta (RF-S-26)
            Trigger(
                func="""
                IF EXISTS (
                    SELECT 1
                    FROM apiauth_apiusergroups ug
                    JOIN apiauth_apigroupprofile gp ON gp.group_id = ug.group_id
                    WHERE ug.api_user_id = NEW.usuario_id
                    AND (gp.kind <> 'public' OR gp.role = 'turista')
                ) THEN
                    RAISE EXCEPTION 'Esta cuenta ya ejerce otro papel.';
                END IF;

                RETURN NEW;
                """,
                name="trg_perfilprestador_un_papel",
                operation=Insert,
                when=Before,
            ),
            Trigger(
                condition=PgQ(
                    old__approved_at__isnull=False, new__approved_at__isnull=True
                ),
                func="RAISE EXCEPTION 'La primera aprobación no se borra.';",
                name="trg_perfilprestador_noreaprueba",
                operation=UpdateOf("aprobado_en"),
                when=Before,
            ),
        )


########################################################################################


# Qué ofrece y qué habla. Son tablas y no campos: una misma persona puede ofrecer los
# dos servicios, y el idioma se compara con el que pide el turista.
@track_table(meta={"db_table": "prestador_servicio_cambio"})
class ProviderService(ApiModel):
    provider = ForeignKey(
        db_column="perfil_prestador_id",
        on_delete=CASCADE,
        related_name="services",
        to=ProviderProfile,
    )
    service = ForeignKey(
        db_column="tipo_servicio_id",
        on_delete=RESTRICT,
        related_name="+",
        to=ServiceType,
    )

    class Meta(ApiModel.Meta):
        db_table: str = "prestador_servicio"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(
                fields=["provider", "service"],
                name="unq_prestadorservicio_par",
            ),
        )


@track_table(meta={"db_table": "prestador_idioma_cambio"})
class ProviderLanguage(ApiModel):
    provider = ForeignKey(
        db_column="perfil_prestador_id",
        on_delete=CASCADE,
        related_name="languages",
        to=ProviderProfile,
    )
    language = ForeignKey(
        db_column="idioma_id",
        on_delete=RESTRICT,
        related_name="+",
        to=Language,
    )
    level = CharField(choices=LanguageLevels, db_column="nivel", max_length=16)

    class Meta(ApiModel.Meta):
        db_table: str = "prestador_idioma"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            UniqueConstraint(
                fields=["provider", "language"],
                name="unq_prestadoridioma_par",
            ),
            CheckConstraint(
                condition=Q(level__in=LanguageLevels.values),
                name="chk_prestadoridioma_nivel",
            ),
        )


########################################################################################


@track_table(meta={"db_table": "estado_acreditacion_cambio"})
class CredentialStatus(ApiModel):
    code = CharField(db_column="codigo", max_length=24)
    label = CharField(db_column="etiqueta", max_length=60)
    # solo lo aprobado y sin vencer acredita
    accredits = BooleanField(db_column="acredita")
    is_terminal = BooleanField(db_column="es_terminal")

    class Meta(ApiModel.Meta):
        db_table: str = "estado_acreditacion"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_estadoacreditacion_codigo"),
        )


# Un documento del prestador con sus fechas. No se reabre: renovar o corregir es subir
# otro, que genera otra fila; así queda cuántas veces se intentó y por qué falló.
#
# Quien revisa deja su veredicto (`verdict`) mientras el expediente está abierto; el
# estado cambia cuando el expediente se resuelve. Por eso el veredicto y el estado son
# dos cosas: un documento aceptado en un expediente rechazado sigue aceptado y no se
# vuelve a revisar.
@track_table(meta={"db_table": "acreditacion_cambio"})
class Credential(ApiModel):
    provider = ForeignKey(
        db_column="perfil_prestador_id",
        on_delete=CASCADE,
        related_name="credentials",
        to=ProviderProfile,
    )
    credential_type = ForeignKey(
        db_column="tipo_acreditacion_id",
        on_delete=RESTRICT,
        related_name="credentials",
        to=CredentialType,
    )
    status = ForeignKey(
        db_column="estado_id",
        on_delete=RESTRICT,
        related_name="credentials",
        to=CredentialStatus,
    )
    # el expediente en el que se subió
    request = ForeignKey(
        db_column="solicitud_id",
        on_delete=RESTRICT,
        related_name="credentials",
        to="apimoderation.VerificationRequest",
    )

    # el folio declarado del documento
    number = CharField(db_column="numero", max_length=60)
    # la referencia en el almacenamiento de archivos, no el archivo
    file_key = CharField(db_column="archivo_id", max_length=255)
    issued_on = DateField(db_column="emitida_el")
    # nulo si el tipo no vence
    expires_on = DateField(
        db_column="vence_el",
        db_default=None,
        default=None,
        null=True,
    )
    uploaded_at = DateTimeField(db_column="cargada_en", db_default=Now(), default=now)

    # vacío mientras nadie lo revisa
    verdict = CharField(
        blank=True,
        choices=Verdicts,
        db_column="veredicto",
        db_default="",
        default="",
        max_length=16,
    )
    reviewed_by = ForeignKey(
        db_column="revisada_por",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="+",
        to=ApiUser,
    )
    reviewed_at = DateTimeField(
        db_column="revisada_en",
        db_default=None,
        default=None,
        null=True,
    )
    # por qué se rechazó: se le comunica al prestador
    reason = ForeignKey(
        db_column="motivo_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="+",
        to=Reason,
    )
    note = TextField(blank=True, db_column="nota", db_default="", default="")

    class Meta(ApiModel.Meta):
        db_table: str = "acreditacion"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(expires_on__isnull=True) | Q(expires_on__gt=F("issued_on")),
                name="chk_acreditacion_vigencia_orden",
            ),
            CheckConstraint(
                condition=Q(verdict="") | Q(verdict__in=Verdicts.values),
                name="chk_acreditacion_veredicto",
            ),
            # sin veredicto no hay revisión; con él, se sabe quién y cuándo
            CheckConstraint(
                condition=Q(
                    reason__isnull=True,
                    reviewed_at__isnull=True,
                    reviewed_by__isnull=True,
                    verdict="",
                )
                | (
                    Q(reviewed_at__isnull=False, reviewed_by__isnull=False)
                    & ~Q(verdict="")
                ),
                name="chk_acreditacion_revision_coherente",
            ),
            # un rechazo sin causa obliga a reintentar a ciegas (RF-B-04)
            CheckConstraint(
                condition=~Q(verdict=Verdicts.REJECTED) | Q(reason__isnull=False),
                name="chk_acreditacion_motivo_exigido",
            ),
        )

        indexes: Sequence[Index] = (
            # el barrido diario que vence documentos
            Index(
                condition=Q(expires_on__isnull=False),
                fields=["expires_on"],
                name="idx_acreditacion_vencimiento",
            ),
            # los documentos vigentes de un perfil: el más reciente de cada tipo
            Index(
                F("provider"),
                F("credential_type"),
                F("uploaded_at").desc(),
                name="idx_acreditacion_perfil_tipo",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            # mutable protegida: lo que se declaró y se subió no se reescribe
            ReadOnly(
                fields=[
                    "credential_type",
                    "expires_on",
                    "file_key",
                    "issued_on",
                    "number",
                    "provider",
                    "request",
                    "uploaded_at",
                ],
                name="trg_acreditacion_readonly",
            ),
            # RF-S-13: el tipo que vence exige la fecha
            Trigger(
                func="""
                IF NEW.vence_el IS NULL AND EXISTS (
                    SELECT 1 FROM tipo_acreditacion
                    WHERE id = NEW.tipo_acreditacion_id AND exige_vencimiento
                ) THEN
                    RAISE EXCEPTION 'Ese documento exige su fecha de vencimiento.';
                END IF;

                RETURN NEW;
                """,
                name="trg_acreditacion_vencimiento_exigido",
                operation=Insert,
                when=Before,
            ),
            # uno en vigor por tipo: el que lo reemplaza deja al anterior `reemplazada`
            # antes de quedar aprobado
            Trigger(
                func="""
                IF EXISTS (
                    SELECT 1 FROM estado_acreditacion
                    WHERE id = NEW.estado_id AND codigo = 'aprobada'
                ) AND EXISTS (
                    SELECT 1 FROM acreditacion a
                    JOIN estado_acreditacion e ON e.id = a.estado_id
                    WHERE a.perfil_prestador_id = NEW.perfil_prestador_id
                    AND a.tipo_acreditacion_id = NEW.tipo_acreditacion_id
                    AND a.id <> NEW.id
                    AND e.codigo = 'aprobada'
                ) THEN
                    RAISE EXCEPTION 'Ya hay un documento de ese tipo en vigor.';
                END IF;

                RETURN NEW;
                """,
                name="trg_acreditacion_vigente_unica",
                operation=Insert | Update,
                when=Before,
            ),
        )
