from http import HTTPStatus

from django.views.decorators.debug import sensitive_variables
from dmr import Body, modify

from api_auth.enums import VerificationPurposes
from api_auth.schemas.account import (
    RegisterCodeGet,
    RegisterCodePost,
    RegisterPost,
    RegisterVerifyPost,
)
from api_auth.schemas.session import SessionUserGet
from api_auth.services.account import (
    invalid_code_error,
    register_account,
    request_registration_code,
)
from api_auth.services.session_user import build_session_user
from api_auth.services.verification import check_code, signup_code_reaches_people
from api_core.controllers.serializers import CustomPydanticFastSerializer

from .base import AuthController

########################################################################################


class RegisterCodeController(AuthController[CustomPydanticFastSerializer]):
    # si el alta pide el código, antes de pedirlo: el portal oculta ese campo si no
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> RegisterCodeGet:  # ruff: ignore[no-self-use]
        return RegisterCodeGet(code_required=signup_code_reaches_people())

    @modify(status_code=HTTPStatus.OK)
    async def post(self, parsed_body: Body[RegisterCodePost]) -> RegisterCodeGet:  # ruff: ignore[no-self-use]
        # responde igual exista o no la cuenta, para no revelar quién está registrado
        await request_registration_code(parsed_body.email)

        return RegisterCodeGet(code_required=signup_code_reaches_people())


class RegisterVerifyController(AuthController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.NO_CONTENT)
    @sensitive_variables()
    async def post(self, parsed_body: Body[RegisterVerifyPost]) -> None:  # ruff: ignore[no-self-use]
        # no gasta el código: solo le dice a la app que puede seguir con el formulario
        if not await check_code(
            code=parsed_body.code,
            destination=parsed_body.email,
            purpose=VerificationPurposes.EMAIL,
        ):
            raise invalid_code_error()


class RegisterController(AuthController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.CREATED)
    @sensitive_variables()
    async def post(self, parsed_body: Body[RegisterPost]) -> SessionUserGet:  # ruff: ignore[no-self-use]
        return await build_session_user(await register_account(parsed_body))
