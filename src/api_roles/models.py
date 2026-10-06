from typing import TYPE_CHECKING

from django.contrib.auth.models import Group
from django.db.models import (
    CheckConstraint,
    DateTimeField,
    F,
    Index,
    Q,
    UniqueConstraint,
)
from django.db.models.deletion import RESTRICT
from django.db.models.fields.related import ForeignKey
from django.db.models.functions import Now
from django.utils.timezone import now
from pgtrigger import (
    Before,
    Delete,
    Insert,
    Protect,
    Q as PgQ,
    Trigger,
    Update,
    UpdateOf,
)

from api_auth.models import ApiUser
from api_core.models.base import ApiModel
from api_organizations.models import Business, CulturalInstitution
from api_territory.models import Municipality
from api_utils.db import track_table

if TYPE_CHECKING:
    from collections.abc import Sequence

########################################################################################
# Las tablas y columnas están en español (modelo de dominio, `Convenciones`); el código
# Python sigue en inglés. Cada campo declara su `db_column`.
########################################################################################


# Quién desempeña qué rol y sobre qué objeto (D-02): el rol de operador de comercio no
# basta, hay que saber de cuál. Tres llaves nulables y no un par genérico de tipo e
# identificador: así cada referencia conserva su llave foránea real. Las tres nulas
# significan alcance global (el personal interno).
#
# El permiso se da siempre por rol (D-03); aquí se decide sobre qué objeto actúa quien
# lo tiene. La asignación no se borra: revocar es escribir `revoked_at`, y eso permite
# responder quién tenía qué acceso el día en que ocurrió algo.
@track_table(meta={"db_table": "asignacion_rol_cambio"})
class RoleAssignment(ApiModel):
    user = ForeignKey(
        db_column="usuario_id",
        on_delete=RESTRICT,
        related_name="role_assignments",
        to=ApiUser,
    )
    # un rol es un grupo con perfil (`ApiGroupProfile`); su ámbito exigido está ahí
    role = ForeignKey(
        db_column="rol_id",
        on_delete=RESTRICT,
        related_name="assignments",
        to=Group,
    )

    municipality = ForeignKey(
        db_column="alcaldia_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="role_assignments",
        to=Municipality,
    )
    business = ForeignKey(
        db_column="comercio_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="role_assignments",
        to=Business,
    )
    institution = ForeignKey(
        db_column="institucion_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="role_assignments",
        to=CulturalInstitution,
    )

    granted_by = ForeignKey(
        db_column="otorgada_por",
        on_delete=RESTRICT,
        related_name="+",
        to=ApiUser,
    )
    granted_at = DateTimeField(db_column="otorgada_en", db_default=Now(), default=now)
    # nulo mientras el acceso vive
    revoked_at = DateTimeField(
        db_column="revocada_en",
        db_default=None,
        default=None,
        null=True,
    )

    class Meta(ApiModel.Meta):
        db_table: str = "asignacion_rol"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            # a lo sumo un ámbito: ninguno es el alcance global
            CheckConstraint(
                condition=(
                    Q(business__isnull=True, institution__isnull=True)
                    | Q(business__isnull=True, municipality__isnull=True)
                    | Q(institution__isnull=True, municipality__isnull=True)
                ),
                name="chk_asignacionrol_ambito_unico",
            ),
            CheckConstraint(
                condition=Q(revoked_at__isnull=True)
                | Q(revoked_at__gte=F("granted_at")),
                name="chk_asignacionrol_revocada_coherente",
            ),
            # el mismo rol no se acumula dos veces sobre lo mismo mientras vive
            UniqueConstraint(
                condition=Q(revoked_at__isnull=True),
                fields=["user", "role", "municipality", "business", "institution"],
                name="unq_asignacionrol_vigente",
                nulls_distinct=False,
            ),
        )

        indexes: Sequence[Index] = (
            # resolver permisos en cada petición
            Index(
                condition=Q(revoked_at__isnull=True),
                fields=["user"],
                name="idx_asignacionrol_vigentes",
            ),
            Index(
                condition=Q(revoked_at__isnull=True),
                fields=["municipality"],
                name="idx_asignacionrol_alcaldia",
            ),
            Index(
                condition=Q(revoked_at__isnull=True),
                fields=["business"],
                name="idx_asignacionrol_comercio",
            ),
            Index(
                condition=Q(revoked_at__isnull=True),
                fields=["institution"],
                name="idx_asignacionrol_institucion",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            # el ámbito presente coincide con el que exige el rol (RF-A-03): sin esto,
            # un operador de comercio podría asignarse a una ciudad sin que nada lo vea
            Trigger(
                declare=[("required", "varchar"), ("present", "varchar")],
                func="""
                SELECT scope INTO required
                FROM apiauth_apigroupprofile
                WHERE group_id = NEW.rol_id;

                IF required IS NULL THEN
                    RAISE EXCEPTION 'El rol no tiene perfil y no se puede asignar.';
                END IF;

                IF NEW.alcaldia_id IS NOT NULL THEN
                    present := 'municipality';
                ELSIF NEW.comercio_id IS NOT NULL THEN
                    present := 'business';
                ELSIF NEW.institucion_id IS NOT NULL THEN
                    present := 'institution';
                ELSE
                    present := 'global';
                END IF;

                IF present <> required THEN
                    RAISE EXCEPTION 'El ámbito no es el que exige el rol.';
                END IF;

                RETURN NEW;
                """,
                name="trg_asignacionrol_ambito_coincide",
                operation=Insert | Update,
                when=Before,
            ),
            # la revocación no se deshace: quien vuelve a tener el rol recibe otra fila
            Trigger(
                condition=PgQ(
                    old__revoked_at__isnull=False, new__revoked_at__isnull=True
                ),
                func="RAISE EXCEPTION 'Una asignación revocada no se reactiva.';",
                name="trg_asignacionrol_norevive",
                operation=UpdateOf("revocada_en"),
                when=Before,
            ),
            # revocar es escribir la fecha, no borrar
            Protect(name="trg_asignacionrol_no_borrar", operation=Delete),
        )
