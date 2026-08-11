from abc import ABC, abstractmethod
from typing import override

from .base import LaxDTO
from .pagination import PageQuery

########################################################################################


class FilterQuery(ABC, LaxDTO):
    @abstractmethod
    def get_filters(self) -> dict:
        pass


########################################################################################


class PaginatedFilterQuery(FilterQuery, PageQuery):
    @override
    def get_filters(self) -> dict:
        return self.model_dump(
            exclude=set(PageQuery.model_fields.keys()),
            exclude_unset=True,
            mode="json",
        )


########################################################################################


class UnpaginatedFilterQuery(FilterQuery, LaxDTO):
    @override
    def get_filters(self) -> dict:
        return self.model_dump(exclude_unset=True, mode="json")
