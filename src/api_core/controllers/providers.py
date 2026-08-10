from abc import ABC, abstractmethod

from django.db.models.query import QuerySet
from django.http import HttpResponse

########################################################################################


class HandleNotAllowedProvider(ABC):
    @abstractmethod
    def handle_method_not_allowed(self, method: str) -> HttpResponse:
        pass


########################################################################################


class QuerySetProvider(ABC):
    @abstractmethod
    def build_qs(self) -> QuerySet:
        pass
