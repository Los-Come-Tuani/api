from typing import TYPE_CHECKING, override

from django.contrib.auth.backends import ModelBackend

if TYPE_CHECKING:
    from django.db.models.query import QuerySet

    from api_auth.models import ApiUser

########################################################################################


class ApiUserBackend(ModelBackend):
    @override
    def _get_user_permissions(self, user_obj: ApiUser) -> QuerySet:
        return user_obj.permissions.all()  # ty: ignore[unresolved-attribute]
