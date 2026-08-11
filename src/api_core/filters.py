from typing import TYPE_CHECKING, override

from django.db.models import Q
from django_filters import NumberFilter, RangeFilter
from django_filters.constants import EMPTY_VALUES
from django_filters.filters import CharFilter, ChoiceFilter

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.db.models import TextChoices
    from django.db.models.query import QuerySet

########################################################################################


class FloatFilter(NumberFilter):
    pass


class FloatRangeFilter(RangeFilter):
    pass


class DecimalFilter(NumberFilter):
    pass


class DecimalRangeFilter(RangeFilter):
    pass


class IntFilter(NumberFilter):
    pass


class IntRangeFilter(RangeFilter):
    pass


########################################################################################


class LoweredFilter(CharFilter):
    @override
    def __init__(self, **kwargs: bool | str | None) -> None:
        kwargs.setdefault("lookup_expr", "im_unaccent__icontains")

        super().__init__(**kwargs)


########################################################################################


class LoweredSearchFilter(LoweredFilter):
    @override
    def __init__(
        self,
        *search_fields: str,
        **kwargs: bool | str | None,
    ) -> None:
        self.search_fields: Sequence[str] = search_fields

        super().__init__(**kwargs)

    @override
    def filter(self, qs: QuerySet, value: str | None) -> QuerySet:
        if value in EMPTY_VALUES or not self.search_fields:
            return qs

        if self.distinct:
            qs: QuerySet = qs.distinct()

        query = Q()

        for field in self.search_fields:
            query |= Q(**{f"{field}__{self.lookup_expr}": value})

        qs: QuerySet = qs.filter(query) if not self.exclude else qs.exclude(query)

        return qs


########################################################################################


class TypedChoiceFilter(ChoiceFilter):
    @override
    def __init__(
        self,
        enum: type[TextChoices],
        **kwargs: bool | str | None,
    ) -> None:
        self.enum = enum

        kwargs.setdefault("choices", enum.choices)

        super().__init__(**kwargs)


########################################################################################


class TypedLoweredFilter(TypedChoiceFilter, LoweredFilter):
    pass
