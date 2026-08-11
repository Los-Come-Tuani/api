from django.core.exceptions import (
    RequestDataTooBig,
    TooManyFieldsSent,
    TooManyFilesSent,
    ValidationError as DjangoValidationError,
)
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError, RestrictedError
from dmr.errors import ValidationError as DmrValidationError
from pydantic import ValidationError as PydanticValidationError

########################################################################################

GenericConflictError = IntegrityError | RestrictedError | ProtectedError

GenericValidationError = (
    DjangoValidationError | DmrValidationError | PydanticValidationError
)

UploadLimitError = RequestDataTooBig | TooManyFieldsSent | TooManyFilesSent
