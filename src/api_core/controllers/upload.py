from http import HTTPStatus

from asgiref.sync import sync_to_async
from dmr import Body, modify

from api_core.controllers.base import BaseController
from api_core.controllers.mixins import PublicEndpointMixin, StrictThrottlingMixin
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.schemas.upload import UploadGet, UploadPost
from api_core.services.uploads import issue_upload
from api_exceptions.specs import ServiceUnavailableSpec

########################################################################################


# Pública a propósito: quien se postula sube sus documentos antes de tener cuenta. Lo
# que la acota es el límite estricto de peticiones, los tipos y tamaños de cada clase
# de archivo y que la URL firmada solo sirve para ese archivo, durante unos minutos.
class UploadController(
    PublicEndpointMixin,
    StrictThrottlingMixin,
    BaseController[CustomPydanticFastSerializer],
):
    @modify(
        extra_responses=[ServiceUnavailableSpec],
        status_code=HTTPStatus.CREATED,
    )
    async def post(self, parsed_body: Body[UploadPost]) -> UploadGet:  # ruff: ignore[no-self-use]
        signed = await sync_to_async(issue_upload)(
            parsed_body.kind,
            parsed_body.content_type,
            parsed_body.size,
        )

        return UploadGet(
            expires_in=signed.expires_in,
            headers=signed.headers,
            key=signed.key,
            max_bytes=signed.max_bytes,
            method="PUT",
            url=signed.url,
        )
