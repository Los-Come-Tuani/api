from http import HTTPStatus
from typing import override

from asgiref.sync import sync_to_async
from django.http import HttpResponse
from django.views.decorators.debug import sensitive_variables
from dmr import Body, CookieSpec, ResponseSpec, modify, validate

from api_auth.controllers.base import WebAuthController
from api_auth.enums import TokenTypes
from api_auth.services.cookies import build_cookied_response
from api_auth.services.jwt import EncodedJwtPair
from api_auth.services.session import open_session
from api_auth.services.session_user import build_session_user
from api_core.controllers.base import BaseController
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_exceptions.errors import ForbiddenError
from api_organizations.schemas.application import (
    ApplicationGet,
    ApplicationSessionResponse,
    BusinessApplicationPost,
    InstitutionApplicationPost,
    MunicipalityApplicationPost,
)
from api_organizations.services.application import (
    Registered,
    application_payload,
    latest_application_sync,
    register_business,
    register_institution,
    register_municipality,
)

########################################################################################

# - la sesión se abre con cookies, igual que el inicio de sesión del portal
APPLICATION_RESPONSES = (
    ResponseSpec(
        cookies={
            TokenTypes.ACCESS: CookieSpec(skip_validation=True),
            TokenTypes.REFRESH: CookieSpec(skip_validation=True),
        },
        return_type=ApplicationSessionResponse,
        status_code=HTTPStatus.CREATED,
    ),
)


# Deja a quien se postuló dentro: verificó su correo con el código, y entra con acceso
# limitado a su solicitud mientras el equipo la revisa.
async def application_response(
    ctrl: WebAuthController[CustomPydanticFastSerializer],
    registered: Registered,
) -> HttpResponse:
    session: EncodedJwtPair | str = await open_session(registered.user)

    # una cuenta recién creada no tiene segundo factor: la sesión se abre directo
    if not isinstance(session, EncodedJwtPair):
        raise ForbiddenError

    return build_cookied_response(
        ctrl=ctrl,
        data=ApplicationSessionResponse(
            application=await sync_to_async(application_payload)(registered.request),
            user=await build_session_user(registered.user),
        ),
        status=HTTPStatus.CREATED,
        tokens=session,
    )


########################################################################################
# Alta pública: la persona verifica su correo con un código (`/auth/register-code/`) y
# manda sus datos con su contraseña. Es solo del portal (cookies y CSRF).


class BusinessApplicationController(WebAuthController[CustomPydanticFastSerializer]):
    @override
    @sensitive_variables()
    @validate(*APPLICATION_RESPONSES, validate_responses=False)
    async def post(self, parsed_body: Body[BusinessApplicationPost]) -> HttpResponse:
        await super().post()

        return await application_response(self, await register_business(parsed_body))


class InstitutionApplicationController(
    WebAuthController[CustomPydanticFastSerializer],
):
    @override
    @sensitive_variables()
    @validate(*APPLICATION_RESPONSES, validate_responses=False)
    async def post(self, parsed_body: Body[InstitutionApplicationPost]) -> HttpResponse:
        await super().post()

        return await application_response(self, await register_institution(parsed_body))


class MunicipalityApplicationController(
    WebAuthController[CustomPydanticFastSerializer],
):
    @override
    @sensitive_variables()
    @validate(*APPLICATION_RESPONSES, validate_responses=False)
    async def post(
        self,
        parsed_body: Body[MunicipalityApplicationPost],
    ) -> HttpResponse:
        await super().post()

        return await application_response(
            self, await register_municipality(parsed_body)
        )


########################################################################################


# La solicitud de quien entró: el estado, y si ya se resolvió, cómo (con el motivo si
# se rechazó).
class MineApplicationController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> ApplicationGet:
        request = await sync_to_async(latest_application_sync)(self.request.user)

        return await sync_to_async(application_payload)(request)
