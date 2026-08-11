from typing import TYPE_CHECKING

from .base import ModelController
from .detail import (
    ModelDetailController,
    ModelManyToManyDetailController,
    ModelNestedDetailController,
)
from .list import (
    ModelListAllController,
    ModelListController,
    ModelManyToManyListController,
    ModelNestedListController,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

########################################################################################

__all__: Sequence[str] = (
    "ModelController",
    "ModelDetailController",
    "ModelListAllController",
    "ModelListController",
    "ModelManyToManyDetailController",
    "ModelManyToManyListController",
    "ModelNestedDetailController",
    "ModelNestedListController",
)
