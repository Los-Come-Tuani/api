from typing import TYPE_CHECKING

from django.db.models import (
    BooleanField,
    CharField,
    CheckConstraint,
    DateTimeField,
    F,
    Index,
    OneToOneField,
    Q,
    TextField,
    UniqueConstraint,
)
from django.db.models.deletion import CASCADE, RESTRICT
from django.db.models.fields.related import ForeignKey
from django.db.models.functions import Now
from django.utils.timezone import now
from pgtrigger import After, Delete, Insert, Protect, ReadOnly, Trigger, Update

from api_auth.models import ApiUser
from api_catalogs.models import Reason
from api_core.models.base import ApiModel
from api_moderation.enums import VerificationProcedures
from api_organizations.models import Business, CulturalInstitution
from api_territory.models import Municipality
from api_utils.db import track_table

if TYPE_CHECKING:
    from collections.abc import Sequence

########################################################################################
# Las tablas y columnas están en español (modelo de dominio, `Convenciones`); el código
# Python sigue en inglés. Cada campo declara su `db_column`.
########################################################################################


# Los estados de una verificación: la misma máquina para todo lo que se verifica. Dos
# estados están en la bandeja del moderador y dos cierran el expediente.
@track_table(meta={"db_table": "estado_verificacion_cambio"})
class VerificationStatus(ApiModel):
    code = CharField(db_column="codigo", max_length=24)
    label = CharField(db_column="etiqueta", max_length=60)
    in_queue = BooleanField(db_column="en_bandeja")
    is_terminal = BooleanField(db_column="es_terminal")

    class Meta(ApiModel.Meta):
        db_table: str = "estado_verificacion"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_estadoverificacion_codigo"),
        )


########################################################################################


# La cola de trabajo del equipo: una solicitud por registro que aspira a existir para el
# turista. Objetos mutuamente excluyentes: las tres organizaciones y el perfil de un
# prestador. El modelo prevé la acreditación en lugar del perfil; aquí el expediente es
# de la persona, porque la revisión en dos pasos decide sobre ella y sus documentos se
# revisan dentro (ver `docs/prestadores.md`).
#
# Se atiende por orden de llegada (`submitted_at`). Quien la toma queda en `taken_by`, y
# soltarla es volver ese campo a nulo.
@track_table(meta={"db_table": "solicitud_verificacion_cambio"})
class VerificationRequest(ApiModel):
    business = ForeignKey(
        db_column="comercio_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=CASCADE,
        related_name="verification_requests",
        to=Business,
    )
    municipality = ForeignKey(
        db_column="alcaldia_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=CASCADE,
        related_name="verification_requests",
        to=Municipality,
    )
    institution = ForeignKey(
        db_column="institucion_cultural_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=CASCADE,
        related_name="verification_requests",
        to=CulturalInstitution,
    )
    provider = ForeignKey(
        db_column="perfil_prestador_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=CASCADE,
        related_name="verification_requests",
        to="apiprofiles.ProviderProfile",
    )

    procedure = CharField(
        choices=VerificationProcedures,
        db_column="tramite",
        db_default=VerificationProcedures.APPLICATION,
        default=VerificationProcedures.APPLICATION,
        max_length=16,
    )

    status = ForeignKey(
        db_column="estado_id",
        on_delete=RESTRICT,
        related_name="requests",
        to=VerificationStatus,
    )

    # qué moderador la tiene en revisión
    taken_by = ForeignKey(
        db_column="tomada_por",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="+",
        to=ApiUser,
    )

    submitted_at = DateTimeField(db_column="enviada_en", db_default=Now(), default=now)
    # nulo mientras está en la bandeja
    resolved_at = DateTimeField(
        db_column="resuelta_en",
        db_default=None,
        default=None,
        null=True,
    )

    class Meta(ApiModel.Meta):
        db_table: str = "solicitud_verificacion"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            # exactamente un objeto
            CheckConstraint(
                condition=(
                    Q(
                        business__isnull=False,
                        institution__isnull=True,
                        municipality__isnull=True,
                        provider__isnull=True,
                    )
                    | Q(
                        business__isnull=True,
                        institution__isnull=False,
                        municipality__isnull=True,
                        provider__isnull=True,
                    )
                    | Q(
                        business__isnull=True,
                        institution__isnull=True,
                        municipality__isnull=False,
                        provider__isnull=True,
                    )
                    | Q(
                        business__isnull=True,
                        institution__isnull=True,
                        municipality__isnull=True,
                        provider__isnull=False,
                    )
                ),
                name="chk_solicitudverificacion_objeto_excluyente",
            ),
            CheckConstraint(
                condition=Q(procedure__in=VerificationProcedures.values),
                name="chk_solicitudverificacion_tramite",
            ),
            # solo un prestador aprobado renueva
            CheckConstraint(
                condition=Q(procedure=VerificationProcedures.APPLICATION)
                | Q(provider__isnull=False),
                name="chk_solicitudverificacion_renovacion_prestador",
            ),
            CheckConstraint(
                condition=Q(resolved_at__isnull=True)
                | Q(resolved_at__gte=F("submitted_at")),
                name="chk_solicitudverificacion_resuelta_coherente",
            ),
            # un registro no tiene dos expedientes abiertos a la vez; corregir y volver
            # a enviar abre otro cuando el anterior ya se resolvió
            UniqueConstraint(
                condition=Q(business__isnull=False, resolved_at__isnull=True),
                fields=["business"],
                name="unq_solicitudverificacion_abierta_comercio",
            ),
            UniqueConstraint(
                condition=Q(institution__isnull=False, resolved_at__isnull=True),
                fields=["institution"],
                name="unq_solicitudverificacion_abierta_institucion",
            ),
            UniqueConstraint(
                condition=Q(municipality__isnull=False, resolved_at__isnull=True),
                fields=["municipality"],
                name="unq_solicitudverificacion_abierta_alcaldia",
            ),
            UniqueConstraint(
                condition=Q(provider__isnull=False, resolved_at__isnull=True),
                fields=["provider"],
                name="unq_solicitudverificacion_abierta_prestador",
            ),
        )

        indexes: Sequence[Index] = (
            Index(
                condition=Q(resolved_at__isnull=True),
                fields=["submitted_at"],
                name="idx_solicitudverificacion_bandeja",
            ),
            Index(
                condition=Q(resolved_at__isnull=True),
                fields=["taken_by"],
                name="idx_solicitudverificacion_tomada",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            # mutable protegida: lo que se verifica y cuándo llegó no se reescriben
            ReadOnly(
                fields=[
                    "business",
                    "institution",
                    "municipality",
                    "procedure",
                    "provider",
                    "submitted_at",
                ],
                name="trg_solicitudverificacion_readonly",
            ),
        )


########################################################################################


# Cómo se cerró un expediente: quién decidió, cuándo y por qué. Es un hecho, así que
# solo se inserta. El motivo es obligatorio al rechazar: sin él, el solicitante
# reintenta a ciegas (RF-B-04).
class VerificationResolution(ApiModel):
    request = OneToOneField(
        db_column="solicitud_id",
        on_delete=CASCADE,
        related_name="resolution",
        to=VerificationRequest,
    )
    resolved_by = ForeignKey(
        db_column="resuelta_por",
        on_delete=RESTRICT,
        related_name="+",
        to=ApiUser,
    )

    approved = BooleanField(db_column="aprobada")
    reason = ForeignKey(
        db_column="motivo_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="+",
        to=Reason,
    )
    # lo que se le comunica al solicitante
    note = TextField(blank=True, db_column="nota", db_default="", default="")

    resolved_at = DateTimeField(db_column="resuelta_en", db_default=Now(), default=now)

    class Meta(ApiModel.Meta):
        db_table: str = "resolucion_verificacion"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(approved=True) | Q(reason__isnull=False),
                name="chk_resolucionverificacion_motivo_exigido",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            # de solo inserción: la decisión ya tomada no se reescribe ni se borra
            Protect(
                name="trg_resolucionverificacion_soloinsercion",
                operation=Update | Delete,
            ),
            # la aprobación es la única vía por la que algo se hace visible: el
            # disparador escribe `verificado_en` en el objeto y no el servicio
            Trigger(
                func="""
                IF NEW.aprobada THEN
                    UPDATE comercio SET verificado_en = NEW.resuelta_en
                    WHERE verificado_en IS NULL AND id = (
                        SELECT comercio_id FROM solicitud_verificacion
                        WHERE id = NEW.solicitud_id
                    );

                    UPDATE alcaldia SET verificado_en = NEW.resuelta_en
                    WHERE verificado_en IS NULL AND id = (
                        SELECT alcaldia_id FROM solicitud_verificacion
                        WHERE id = NEW.solicitud_id
                    );

                    UPDATE institucion_cultural SET verificado_en = NEW.resuelta_en
                    WHERE verificado_en IS NULL AND id = (
                        SELECT institucion_cultural_id FROM solicitud_verificacion
                        WHERE id = NEW.solicitud_id
                    );
                END IF;

                RETURN NULL;
                """,
                name="trg_resolucionverificacion_aplica",
                operation=Insert,
                when=After,
            ),
        )
