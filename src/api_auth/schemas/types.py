from typing import Annotated

from pydantic import StringConstraints

########################################################################################

type JwtToken = Annotated[str, StringConstraints(max_length=512, min_length=1)]
type Password = Annotated[str, StringConstraints(max_length=256, min_length=1)]
type TwoFactorCode = Annotated[str, StringConstraints(max_length=32, min_length=6)]
type Username = Annotated[str, StringConstraints(max_length=100, min_length=1)]
