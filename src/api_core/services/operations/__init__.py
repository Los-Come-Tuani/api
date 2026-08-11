from typing import TYPE_CHECKING

from .base import (
    CreateOperation,
    DestroyOperation,
    ModelOperation,
    RetrieveOperation,
    UpdateOperation,
    split_payload,
)
from .flat import FlatCreateOperation, FlatRetrieveOperation, FlatUpdateOperation
from .link import (
    FlatLinkAttachOperation,
    FlatLinkDetachOperation,
    FlatLinkInspectOperation,
    LinkAttachOperation,
    LinkDetachOperation,
    LinkInspectOperation,
    LinkOperation,
)
from .m2m import (
    ManyToManyCreateOperation,
    ManyToManyOperation,
    ManyToManyUpdateOperation,
)
from .nested import NestedCreateOperation, NestedOperation, NestedUpdateOperation

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__: Sequence[str] = (
    "CreateOperation",
    "DestroyOperation",
    "FlatCreateOperation",
    "FlatLinkAttachOperation",
    "FlatLinkDetachOperation",
    "FlatLinkInspectOperation",
    "FlatRetrieveOperation",
    "FlatUpdateOperation",
    "LinkAttachOperation",
    "LinkDetachOperation",
    "LinkInspectOperation",
    "LinkOperation",
    "ManyToManyCreateOperation",
    "ManyToManyOperation",
    "ManyToManyUpdateOperation",
    "ModelOperation",
    "NestedCreateOperation",
    "NestedOperation",
    "NestedUpdateOperation",
    "RetrieveOperation",
    "UpdateOperation",
    "split_payload",
)
