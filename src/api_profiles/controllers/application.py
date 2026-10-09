from http import HTTPStatus

from asgiref.sync import sync_to_async
from django.views.decorators.debug import sensitive_variables
from dmr import Body, modify

from api_auth.controllers.base import MobileAuthController
from api_auth.services.jwt import EncodedJwtPair
from api_auth.services.session import open_session
from api_auth.services.session_user import build_session_user
from api_core.controllers.base import BaseController
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_exceptions.errors import ForbiddenError
from api_profiles.schemas.application import (
    ProviderApplicationGet,
    ProviderApplicationPost,
    ProviderApplicationResponse,
    ProviderRenewalPost,
    ProviderResubmitPost,
)
from api_profiles.schemas.profile import ProviderProfileGet, ProviderProfilePatch
from api_profiles.services.application import (
    latest_application_sync,
    own_profile_sync,
    register,
    renew_sync,
    resubmit_sync,
)
from api_profiles.services.payloads import mine_payload, profile_payload
from api_profiles.services.profile import update_profile_sync

########################################################################################
# Postulación pública desde la app: la persona verifica su correo con un código
# (`/auth/register-code/`) y manda su cuenta, su perfil y sus documentos. La cuenta
# queda dentro, con los tokens en el cuerpo, igual que el inicio de sesión móvil.


class ProviderApplicationController(MobileAuthController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.CREATED)
    @sensitive_variables()
    async def post(  # ruff: ignore[no-self-use]
        self,
        parsed_body: Body[ProviderApplicationPost],
    ) -> ProviderApplicationResponse:
        registered = await register(parsed_body)
        session: EncodedJwtPair | str = await open_session(registered.user)

        # una cuenta recién creada no tiene segundo factor: la sesión se abre directo
        if not isinstance(session, EncodedJwtPair):
            raise ForbiddenError

        return ProviderApplicationResponse(
            access=session.access,
            application=await sync_to_async(mine_payload)(registered.request),
            refresh=session.refresh,
            user=await build_session_user(registered.user),
        )


########################################################################################
# Lo que ve el prestador de sí mismo


# Su expediente más reciente: el estado, cómo se resolvió y qué hay que corregir.
class MineProviderApplicationController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> ProviderApplicationGet:
        request = await sync_to_async(latest_application_sync)(self.request.user)

        return await sync_to_async(mine_payload)(request)


# Corregir lo rechazado y volver a enviarlo: abre otro expediente.
class MineProviderResubmitController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.CREATED)
    async def post(
        self,
        parsed_body: Body[ProviderResubmitPost],
    ) -> ProviderApplicationGet:
        request = await sync_to_async(resubmit_sync)(self.request.user, parsed_body)

        return await sync_to_async(mine_payload)(request)


# Renovar uno o más documentos sin dejar de trabajar.
class MineProviderRenewalController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.CREATED)
    async def post(
        self, parsed_body: Body[ProviderRenewalPost]
    ) -> ProviderApplicationGet:
        request = await sync_to_async(renew_sync)(self.request.user, parsed_body)

        return await sync_to_async(mine_payload)(request)


# El perfil público: lo descriptivo se cambia sin pasar por la revisión.
class MineProviderProfileController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> ProviderProfileGet:
        profile = await sync_to_async(own_profile_sync)(self.request.user)

        return await sync_to_async(profile_payload)(profile)

    @modify(status_code=HTTPStatus.OK)
    async def patch(
        self, parsed_body: Body[ProviderProfilePatch]
    ) -> ProviderProfileGet:
        profile = await sync_to_async(update_profile_sync)(
            self.request.user,
            parsed_body,
        )

        return await sync_to_async(profile_payload)(profile)
