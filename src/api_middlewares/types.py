from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from django.http import HttpRequest, HttpResponse

########################################################################################

type AsyncSyncResponse = Awaitable[HttpResponse] | HttpResponse

type MiddlewareCallable = Callable[[HttpRequest], AsyncSyncResponse]
