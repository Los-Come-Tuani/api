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

    @override
    def user_can_authenticate(self, user: ApiUser) -> bool:
        # El backend solo comprueba la contraseña. Si la cuenta puede operar o no (está
        # pendiente, suspendida...) se resuelve después, en `authenticate_user`, para
        # poder decirle al titular por qué no entra sin revelarle nada a quien tantea.
        return True
