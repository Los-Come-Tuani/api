from typing import Literal

from .base import DTO

########################################################################################


class HealthCheckGet(DTO):
    status: Literal["error", "success"]
    components: dict[str, str]


########################################################################################


class HealthCheckError(HealthCheckGet):
    status: Literal["error"] = "error"


########################################################################################


class HealthCheckSuccess(HealthCheckGet):
    status: Literal["success"] = "success"
