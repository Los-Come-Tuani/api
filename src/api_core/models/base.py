from typing import TYPE_CHECKING, override
from uuid import UUID, uuid7

from django.db.models import Model, UUIDField
from django.db.models.functions import UUID7
from pgtrigger import Before, ReadOnly, Statement, Trigger, Truncate

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import ClassVar

    from django.db.models.manager import Manager
    from django.db.models.options import Options
    from django.db.models.query import QuerySet
    from ty_extensions import Intersection

    from .event import ApiEvent

########################################################################################


class ApiModel(Model):
    id = UUIDField(db_default=UUID7(), default=uuid7, primary_key=True)

    pk: UUID

    pgh_event_model: ClassVar[ApiEvent]

    objects: ClassVar[Intersection[Manager, QuerySet]]

    _default_manager: ClassVar[Intersection[Manager, QuerySet]]

    _meta: ClassVar[Options]

    class Meta:
        abstract: bool = True
        triggers: Sequence[Trigger] = (
            Trigger(
                level=Statement,
                name="trg_protect_truncate",
                operation=Truncate,
                when=Before,
                func="RAISE EXCEPTION 'No se permite truncar tablas.';",
            ),
            ReadOnly(fields=["id"], name="trg_readonly_primarykey"),
        )

    @override
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(id={self.pk})"
