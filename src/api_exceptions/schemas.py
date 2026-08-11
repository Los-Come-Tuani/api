from functools import cache

from pydantic import create_model

from api_core.schemas.base import PermissiveDTO

from .errors import ApiError

########################################################################################


class ApiErrorResponse(PermissiveDTO):
    detail: str = ApiError.default_detail

    field_errors: dict[str, str] | None = None

    @staticmethod
    @cache
    def from_exc(exc: type[ApiError]) -> type[ApiErrorResponse]:
        if exc is ApiError:
            return ApiErrorResponse

        kwargs: dict = {"__base__": ApiErrorResponse}

        kwargs["detail"] = (
            dt | str if (dt := getattr(exc, "detail_type", None)) else str,
            exc.default_detail,
        )

        kwargs["field_errors"] = (dict[str, str] | None, None)

        return create_model(
            exc.__name__.replace("Error", "Response"),
            **kwargs,
        )
