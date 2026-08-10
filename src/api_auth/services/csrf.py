from typing import TYPE_CHECKING, Final, override

from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.utils.translation import gettext

from api_core.config import CONFIG
from api_exceptions.enums import RequestScopes
from api_exceptions.errors import ForbiddenError

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

########################################################################################


class ReasonedCsrfMiddleware(CsrfViewMiddleware):
    @override
    def _reject(self, request: HttpRequest, reason: str) -> str:
        return reason


########################################################################################


async def dummy(  # ruff: ignore[unused-async]
    *args,  # ruff: ignore[missing-type-args, unused-function-argument]
    **kwargs,  # ruff: ignore[missing-type-kwargs, unused-function-argument]
) -> None:
    return None


########################################################################################

CSRF_CHECKER: Final = ReasonedCsrfMiddleware(get_response=dummy)

########################################################################################


def attach_csrf(response: HttpResponse, request: HttpRequest) -> HttpResponse:
    response.headers[CONFIG.csrf_header] = get_token(request)

    return response


########################################################################################


def ensure_csrf(request: HttpRequest) -> None:
    CSRF_CHECKER.process_request(request)

    if reason := CSRF_CHECKER.process_view(
        callback_args=(),
        callback_kwargs={},
        callback=None,
        request=request,
    ):
        raise ForbiddenError(
            detail="La autenticación CSRF falló.",
            field_errors={CONFIG.csrf_cookie_name: gettext(message=reason)},
        ).scoped(RequestScopes.COOKIES)
