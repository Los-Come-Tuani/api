from dataclasses import dataclass
from typing import Final, override

from django.http import HttpRequest
from dmr.controller import Controller
from dmr.endpoint import Endpoint
from dmr.throttling import AsyncThrottle, Rate
from dmr.throttling.algorithms import LeakyBucket
from dmr.throttling.cache_keys import BaseThrottleCacheKey

########################################################################################


def build_throttle(max_requests: int, duration_in_seconds: Rate) -> AsyncThrottle:
    return AsyncThrottle(
        algorithm=LeakyBucket(),
        cache_key=ForwardedAddr(),
        duration_in_seconds=duration_in_seconds,
        max_requests=max_requests,
    )


########################################################################################


@dataclass(frozen=True, kw_only=True, slots=True)
class ForwardedAddr(BaseThrottleCacheKey):
    name: Final[str] = "ForwardedAddr"

    runs_before_auth: Final[bool] = True

    @override
    def __call__(
        self,
        endpoint: Endpoint,
        controller: Controller,
    ) -> str | None:
        addr: str | None = self.resolve_addr(controller.request)

        if addr is None:
            return None

        return f"{type(controller).__qualname__}::{endpoint.metadata.method}::{addr}"

    @staticmethod
    def resolve_addr(request: HttpRequest) -> str | None:
        forwarded: str | None = request.META.get("HTTP_X_FORWARDED_FOR")

        if forwarded is not None:
            return forwarded.rsplit(sep=",", maxsplit=1)[-1].strip()

        return request.META.get("REMOTE_ADDR")
