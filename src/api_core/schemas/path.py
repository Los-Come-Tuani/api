from uuid import UUID

from pydantic import PositiveInt

from .get import BaseGet, PrimaryKey

########################################################################################

type InstancePath = IntInstancePath | UuidInstancePath

type RelatedInstancePath = UuidToIntRelatedPath | UuidToUuidRelatedPath

########################################################################################


class IntInstancePath(BaseGet[PositiveInt]):
    pass


########################################################################################


class UuidInstancePath(BaseGet):
    pass


########################################################################################


class RelatedPath[
    PK: PrimaryKey = UUID,
    RelatedPK: PrimaryKey = PositiveInt,
](BaseGet[PK]):
    related: RelatedPK


########################################################################################


class UuidToIntRelatedPath(RelatedPath):
    pass


########################################################################################


class UuidToUuidRelatedPath(RelatedPath[UUID, UUID]):
    pass
