from http import HTTPStatus

from asgiref.sync import sync_to_async
from dmr import modify

from api_catalogs.models import (
    BusinessType,
    CredentialType,
    CulturalPillar,
    InstitutionType,
    Language,
    ServiceType,
)
from api_catalogs.schemas import CityGet, CredentialTypeGet, OptionGet
from api_core.controllers.base import BaseController
from api_core.controllers.mixins import PublicEndpointMixin
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_territory.models import City

########################################################################################

# Las listas que necesitan los formularios de alta, antes de que haya una sesión: por
# eso son públicas. No traen nada sensible: son catálogos cerrados.


class CityListController(
    PublicEndpointMixin,
    BaseController[CustomPydanticFastSerializer],
):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[CityGet]:  # ruff: ignore[no-self-use]
        rows = await sync_to_async(list)(City.objects.order_by("name"))

        return [
            CityGet(
                active=bool(city.active),
                code=str(city.code),
                id=str(city.pk),
                latitude=float(city.latitude),
                longitude=float(city.longitude),
                name=str(city.name),
            )
            for city in rows
        ]


class BusinessTypeListController(
    PublicEndpointMixin,
    BaseController[CustomPydanticFastSerializer],
):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[OptionGet]:  # ruff: ignore[no-self-use]
        rows = await sync_to_async(list)(
            BusinessType.objects.filter(active=True).order_by("label")
        )

        return [
            OptionGet(code=str(row.code), id=str(row.pk), label=str(row.label))
            for row in rows
        ]


class InstitutionTypeListController(
    PublicEndpointMixin,
    BaseController[CustomPydanticFastSerializer],
):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[OptionGet]:  # ruff: ignore[no-self-use]
        rows = await sync_to_async(list)(
            InstitutionType.objects.filter(active=True).order_by("label")
        )

        return [
            OptionGet(code=str(row.code), id=str(row.pk), label=str(row.label))
            for row in rows
        ]


class LanguageListController(
    PublicEndpointMixin,
    BaseController[CustomPydanticFastSerializer],
):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[OptionGet]:  # ruff: ignore[no-self-use]
        rows = await sync_to_async(list)(
            Language.objects.filter(active=True).order_by("name")
        )

        return [
            OptionGet(code=str(row.code), id=str(row.pk), label=str(row.name))
            for row in rows
        ]


class ServiceTypeListController(
    PublicEndpointMixin,
    BaseController[CustomPydanticFastSerializer],
):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[OptionGet]:  # ruff: ignore[no-self-use]
        rows = await sync_to_async(list)(
            ServiceType.objects.filter(active=True).order_by("label")
        )

        return [
            OptionGet(code=str(row.code), id=str(row.pk), label=str(row.label))
            for row in rows
        ]


class PillarListController(
    PublicEndpointMixin,
    BaseController[CustomPydanticFastSerializer],
):
    # los pilares culturales que clasifican los lugares, en el orden de la app
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[OptionGet]:  # ruff: ignore[no-self-use]
        rows = await sync_to_async(list)(
            CulturalPillar.objects.filter(active=True).order_by("order", "label")
        )

        return [
            OptionGet(code=str(row.code), id=str(row.pk), label=str(row.label))
            for row in rows
        ]


class CredentialTypeListController(
    PublicEndpointMixin,
    BaseController[CustomPydanticFastSerializer],
):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[CredentialTypeGet]:  # ruff: ignore[no-self-use]
        rows = await sync_to_async(list)(
            CredentialType.objects
            .select_related("service")
            .filter(active=True)
            .order_by("order", "label")
        )

        return [
            CredentialTypeGet(
                code=str(row.code),
                id=str(row.pk),
                label=str(row.label),
                requires_expiry=bool(row.requires_expiry),
                requires_vehicle=bool(row.requires_vehicle),
                service=None if row.service is None else str(row.service.code),
            )
            for row in rows
        ]
