from http import HTTPStatus
from re import search, sub
from typing import TYPE_CHECKING, Final

from django.db.models.deletion import ProtectedError, RestrictedError
from psycopg.errors import (
    ForeignKeyViolation,
    IntegrityError as PsqlIntegrityError,
    NotNullViolation,
    RestrictViolation,
    UniqueViolation,
)

from api_exceptions.enums import ConflictErrorTypes

from .typed import TypedApiError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Self

    from django.db import IntegrityError as DjangoIntegrityError

########################################################################################


class ConflictError(TypedApiError[ConflictErrorTypes]):
    default_detail: Final[str] = "Hay un conflicto con el estado actual del recurso."

    default_http_status: Final[HTTPStatus] = HTTPStatus.CONFLICT

    @classmethod
    def determine_type(cls, exc: PsqlIntegrityError) -> ConflictErrorTypes:
        match exc:
            case ForeignKeyViolation():
                return ConflictErrorTypes.BAD_FOREIGN
            case NotNullViolation():
                return ConflictErrorTypes.NULL
            case RestrictViolation():
                return ConflictErrorTypes.RESTRICT
            case UniqueViolation():
                return ConflictErrorTypes.UNIQUE
            case _:
                return ConflictErrorTypes.CHECK

    @classmethod
    def from_integrity_error(cls, exc: DjangoIntegrityError) -> Self:
        if isinstance(exc, (RestrictedError, ProtectedError)):
            return cls(type=ConflictErrorTypes.RESTRICT)

        return cls.from_psql_error(exc)

    @classmethod
    def from_psql_error(cls, exc: DjangoIntegrityError) -> Self:
        exc: PsqlIntegrityError | None = cls.traverse_traceback(exc)

        if exc is None:
            return cls()

        err_type = cls.determine_type(exc)

        diag = exc.diag

        col: str | None = diag.column_name
        msg: str | None = diag.message_primary

        if err_type in {ConflictErrorTypes.BAD_FOREIGN, ConflictErrorTypes.UNIQUE}:
            col = cls.parse_col_from_psql_error(msg=diag.message_detail)

            msg: str = (
                "No existe un registro relacionado con el valor proporcionado."
                if err_type == ConflictErrorTypes.BAD_FOREIGN
                else "Ya existe un registro con el valor proporcionado."
            )

        return cls(
            field_errors=({col: msg} if col is not None and msg is not None else {}),
            type=err_type,
        )

    @classmethod
    def parse_col_from_psql_error(cls, msg: str | None) -> str | None:
        if msg is None:
            return None

        regex = search(
            pattern=r"\((.+?)\)=\(.+?\)",
            string=msg,
        )

        if regex is None:
            return None

        return (
            sub(
                pattern=r"^[a-zA-Z_]+\((.*?)\).*$",
                repl=r"\1",
                string=regex.group(1),
            )
            .split(sep="::")[0]
            .strip()
            .strip('"')
        )

    @classmethod
    def parse_pairs(cls, msg: str | None) -> dict[str, str]:
        if msg is None:
            return {}

        regex = search(
            pattern=r"\((.+?)\)=\((.+?)\)",
            string=msg,
        )

        if regex is None:
            return {}

        cols: Sequence[str] = tuple(
            col.strip().strip('"') for col in regex.group(1).split(sep=", ")
        )

        vals: Sequence[str] = tuple(
            val.strip() for val in regex.group(2).split(sep=", ")
        )

        if len(cols) != len(vals):
            return {}

        return dict(zip(cols, vals, strict=True))

    @classmethod
    def parse_pairs_from_psql_error(cls, exc: DjangoIntegrityError) -> dict[str, str]:
        psql: PsqlIntegrityError | None = cls.traverse_traceback(exc)

        if psql is None:
            return {}

        return cls.parse_pairs(msg=psql.diag.message_detail)

    @classmethod
    def traverse_traceback(cls, exc: DjangoIntegrityError) -> PsqlIntegrityError | None:
        cur_exc = exc

        while cur_exc is not None:
            if isinstance(cur_exc, PsqlIntegrityError):
                return cur_exc

            cur_exc = cur_exc.__cause__ or cur_exc.__context__

        return None
