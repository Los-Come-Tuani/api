from http import HTTPStatus
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError as DjangoValidationError
from dmr.errors import ValidationError as DmrValidationError

from api_exceptions.enums import BadRequestErrorTypes, RequestScopes
from api_utils.strings import dotted_join

from .typed import TypedApiError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Final, Self

    from dmr.errors import ErrorDetail
    from pydantic_core import ErrorDetails

    from api_exceptions.types import GenericValidationError

########################################################################################


class BadRequestError(TypedApiError[BadRequestErrorTypes]):
    DEFAULT_FMT_MSG: Final[str] = "'{}' no es un valor válido."
    DEFAULT_MSG: Final[str] = "Este valor no es válido."

    DMR_SCOPE_MAPPER: Final[dict[str, RequestScopes]] = {
        "parsed_body": RequestScopes.BODY,
        "parsed_cookies": RequestScopes.COOKIES,
        "parsed_file_metadata": RequestScopes.FILES,
        "parsed_headers": RequestScopes.HEADERS,
        "parsed_path": RequestScopes.PATH,
        "parsed_query": RequestScopes.QUERY,
    }

    PYDANTIC_TYPE_MAPPER: Final[dict[str, str]] = {
        "api_custom": "{}",
        "extra_forbidden": "Este campo no es válido para esta acción.",
        "greater_than": "Este campo debe ser mayor a {}.",
        "greater_than_equal": "Este campo debe ser mayor, o igual, a {}.",
        "missing": "Este campo es requerido.",
        "less_than": "Este campo debe ser menor a {}.",
        "less_than_equal": "Este campo debe ser menor, o igual, a {}.",
        "string_too_short": "Este campo debe tener un mínimo de {} caracter(es).",
        "string_too_long": "Este campo debe tener un máximo de {} caracter(es).",
    }

    default_detail: Final[str] = "La solicitud contiene datos inválidos."

    default_http_status: Final[HTTPStatus] = HTTPStatus.BAD_REQUEST

    @classmethod
    def from_validation_error(cls, exc: GenericValidationError) -> Self:
        if isinstance(exc, DjangoValidationError):
            return cls(type=BadRequestErrorTypes.FAILED_VALIDATION)

        field_errors = {}

        errs = exc.payload if isinstance(exc, DmrValidationError) else exc.errors()

        for err in errs:
            field: str = dotted_join(*cls.scope_loc(*err.get("loc", ())))

            if field and field not in field_errors:
                field_errors[field] = cls.parse_pydantic_error(err)

        return cls(
            field_errors=field_errors,
            type=BadRequestErrorTypes.FAILED_VALIDATION,
        )

    @classmethod
    def parse_pydantic_error(cls, err: ErrorDetail | ErrorDetails) -> str:
        ctx: dict | None = err.get("ctx")

        msg: str | None = cls.PYDANTIC_TYPE_MAPPER.get(err.get("type", ""))

        if msg is not None and "{" in msg and ctx is not None:
            return msg.format(*ctx.values())
        if msg is not None:
            return msg

        if value := err.get("input"):
            return cls.DEFAULT_FMT_MSG.format(value)

        return err.get("msg", cls.DEFAULT_MSG)

    @classmethod
    def scope_loc(cls, *loc: int | str) -> Sequence[int | str]:
        if not loc:
            return loc

        head, *rest = loc

        scope: RequestScopes | None = cls.DMR_SCOPE_MAPPER.get(str(head))

        if scope is None:
            return loc

        return (scope, *rest)
