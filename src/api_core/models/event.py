from typing import TYPE_CHECKING
from uuid import uuid7

from django.db.models import DateTimeField, TextField, UUIDField
from django.db.models.functions import UUID7, Now
from django.template.defaulttags import now
from pghistory.models import Event
from pghistory.utils import JSONField

if TYPE_CHECKING:
    from typing import ClassVar

    from django.db.models.options import Options
    from pghistory.models import EventQuerySet

########################################################################################


class ApiEvent(Event):
    pgh_id = UUIDField(db_default=UUID7(), default=uuid7, primary_key=True)
    pgh_context = JSONField(db_default=None, default=None, null=True)
    pgh_created_at = DateTimeField(db_default=Now(), default=now)
    pgh_label = TextField(db_default="", default="")

    pgh_obj_id = None
    pgh_tracked_model = None
    pgh_trackers = None

    objects: ClassVar[EventQuerySet]

    _meta: ClassVar[Options]

    class Meta(Event.Meta):
        abstract = True
