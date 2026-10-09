from typing import TYPE_CHECKING

from django.db.models import (
    CharField,
    CheckConstraint,
    DateTimeField,
    Index,
    PositiveIntegerField,
    Q,
    TextField,
    UniqueConstraint,
)
from django.db.models.deletion import RESTRICT, SET_NULL
from django.db.models.fields.related import ForeignKey
from django.db.models.functions import Now
from django.utils.timezone import now

from api_auth.models import ApiUser
from api_core.models.base import ApiModel
from api_utils.db import track_table

if TYPE_CHECKING:
    from collections.abc import Sequence

########################################################################################
# Las tablas y columnas están en español (modelo de dominio, `Convenciones`); el código
# Python sigue en inglés. Cada campo declara su `db_column`.
########################################################################################


# Alguien que vio la landing pide que le muestren K'Plan. No tiene cuenta. Si al
# enviarla ya había una versión publicada, recibió los links en ese momento y queda
# entregada; si no, queda pendiente hasta que el equipo se los haga llegar por fuera y
# la marque.
@track_table(meta={"db_table": "solicitud_demo_cambio"})
class DemoRequest(ApiModel):
    name = CharField(db_column="nombre", max_length=120)
    email = CharField(db_column="correo", max_length=254)
    phone = CharField(
        blank=True, db_column="telefono", db_default="", default="", max_length=30
    )
    organization = CharField(db_column="organizacion", max_length=160)
    kind = CharField(db_column="tipo", max_length=16)
    city = CharField(
        blank=True, db_column="ciudad", db_default="", default="", max_length=120
    )
    message = TextField(blank=True, db_column="mensaje", db_default="", default="")
    status = CharField(
        db_column="estado", db_default="pendiente", default="pendiente", max_length=16
    )
    delivered_at = DateTimeField(
        db_column="entregada_en", db_default=None, default=None, null=True
    )
    # lo que el equipo anota al atenderla; quien la pidió no lo ve
    notes = TextField(blank=True, db_column="notas", db_default="", default="")
    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)
    updated_at = DateTimeField(
        db_column="actualizado_en", db_default=None, default=None, null=True
    )
    updated_by = ForeignKey(
        db_column="actualizado_por",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="+",
        to=ApiUser,
    )

    class Meta(ApiModel.Meta):
        db_table: str = "solicitud_demo"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(
                    kind__in=["comercio", "alcaldia", "institucion", "operador", "otro"]
                ),
                name="chk_solicituddemo_tipo",
            ),
            CheckConstraint(
                condition=Q(status="pendiente", delivered_at__isnull=True)
                | Q(status="entregada", delivered_at__isnull=False),
                name="chk_solicituddemo_estado",
            ),
        )

        indexes: Sequence[Index] = (
            Index(fields=["status", "-created_at"], name="idx_solicituddemo_bandeja"),
            Index(fields=["email"], name="idx_solicituddemo_correo"),
        )


# Una versión de la app con el link (de Drive) donde está su instalador. La vigente de
# cada plataforma es la publicada más reciente: publicar otra la reemplaza y retirarla
# deja otra vez la anterior. Su link se entrega a quien pide una demo.
@track_table(meta={"db_table": "version_app_cambio"})
class AppRelease(ApiModel):
    platform = CharField(db_column="plataforma", max_length=16)
    version = CharField(db_column="version", max_length=32)
    notes = TextField(blank=True, db_column="notas", db_default="", default="")
    link = CharField(db_column="enlace", max_length=500)
    status = CharField(
        db_column="estado", db_default="borrador", default="borrador", max_length=16
    )
    # cuántas solicitudes de demo recibieron este link
    deliveries = PositiveIntegerField(db_column="entregas", db_default=0, default=0)
    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)
    created_by = ForeignKey(
        db_column="creado_por",
        on_delete=RESTRICT,
        related_name="+",
        to=ApiUser,
    )
    published_at = DateTimeField(
        db_column="publicado_en", db_default=None, default=None, null=True
    )
    published_by = ForeignKey(
        db_column="publicado_por",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="+",
        to=ApiUser,
    )
    withdrawn_at = DateTimeField(
        db_column="retirado_en", db_default=None, default=None, null=True
    )

    class Meta(ApiModel.Meta):
        db_table: str = "version_app"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            CheckConstraint(
                condition=Q(platform__in=["android", "macos", "windows"]),
                name="chk_versionapp_plataforma",
            ),
            CheckConstraint(
                condition=Q(status__in=["borrador", "publicada", "retirada"]),
                name="chk_versionapp_estado",
            ),
            CheckConstraint(
                condition=Q(link__startswith="https://"),
                name="chk_versionapp_enlace",
            ),
            UniqueConstraint(
                fields=["platform", "version"], name="unq_versionapp_version"
            ),
        )

        indexes: Sequence[Index] = (
            Index(
                fields=["platform", "status", "-published_at"],
                name="idx_versionapp_vigente",
            ),
        )
