from functools import cache
from http import HTTPStatus

from dmr import modify

from api_utils.env import OPENAPI

from .base import BaseController
from .mixins import PublicEndpointMixin
from .serializers import CustomPydanticFastSerializer

########################################################################################


@cache
def build_root_response() -> dict[str, str]:
    return {
        "description": OPENAPI.description,
        "title": OPENAPI.title,
        "version": OPENAPI.version,
    }  # ty: ignore[invalid-return-type]


########################################################################################


class RootController(
    PublicEndpointMixin,
    BaseController[CustomPydanticFastSerializer],
):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> dict[str, str]:  # ruff: ignore[no-self-use]
        return build_root_response()
