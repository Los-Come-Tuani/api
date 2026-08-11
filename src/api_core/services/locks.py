from contextlib import contextmanager
from datetime import timedelta
from typing import TYPE_CHECKING

from django.core.exceptions import ObjectDoesNotExist
from django.db.utils import OperationalError
from pglock import timeout
from psycopg.errors import LockNotAvailable

from api_exceptions.enums import ConflictErrorTypes, RequestScopes
from api_exceptions.errors import ConflictError, NotFoundError

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Final

    from api_utils.types import DatabaseModel

########################################################################################

LOCK_TIMEOUT: Final[timedelta] = timedelta(seconds=5)

RETRIES: Final[int] = 3

########################################################################################


@contextmanager
def guarded_lock() -> Iterator[None]:
    try:
        with timeout(LOCK_TIMEOUT):
            yield
    except OperationalError as o:
        if not isinstance(o.__cause__, LockNotAvailable):
            raise

        raise ConflictError(type=ConflictErrorTypes.LOCKED) from o


########################################################################################


def lock_instance(*, lookup: dict, model: type[DatabaseModel]) -> DatabaseModel:
    with guarded_lock():
        try:
            return model._default_manager.select_for_update(
                no_key=True,
            ).get(**lookup)
        except ObjectDoesNotExist as o:
            raise NotFoundError(field_errors=lookup).scoped(RequestScopes.PATH) from o
