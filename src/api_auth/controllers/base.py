from abc import ABC, abstractmethod
from typing import ClassVar

from dmr.serializer import BaseSerializer

from api_auth.services.csrf import ensure_csrf
from api_core.controllers.base import BaseController
from api_core.controllers.mixins import PublicEndpointMixin, StrictThrottlingMixin

########################################################################################


class AuthController[Serializer: BaseSerializer](
    PublicEndpointMixin,
    StrictThrottlingMixin,
    BaseController[Serializer],
):
    pass


########################################################################################


class PrivateAuthController[Serializer: BaseSerializer](
    StrictThrottlingMixin,
    BaseController[Serializer],
):
    # Quien tiene un rol que exige el segundo factor y todavía no lo activó solo puede
    # usar lo que sirve para activarlo (y lo mínimo de la cuenta): esos controladores
    # lo declaran con `True`. Ver `api_auth.services.roles.ensure_two_factor_enrolled`.
    allows_pending_two_factor: ClassVar[bool] = False


########################################################################################


class MobileAuthController[Serializer: BaseSerializer](AuthController[Serializer]):
    namespace: ClassVar[str] = "mobile"
    variant: ClassVar[str] = "Mobile"


########################################################################################


class WebAuthController[Serializer: BaseSerializer](AuthController[Serializer], ABC):
    namespace: ClassVar[str] = "web"
    variant: ClassVar[str] = "Web"

    @abstractmethod
    async def post(  # ruff: ignore[missing-return-type-undocumented-public-function]
        self,
        *args,  # ruff: ignore[missing-type-args]
        **kwargs,  # ruff: ignore[missing-type-kwargs]
    ):
        ensure_csrf(self.request)
