from typing import TYPE_CHECKING, override

from asgiref.sync import sync_to_async
from django.contrib.auth.base_user import BaseUserManager
from django.db.transaction import atomic
from django.utils.timezone import now
from pgtrigger import ignore

from api_auth.enums import ApiUserStatus

if TYPE_CHECKING:
    from .user import ApiUser

########################################################################################


class ApiUserManager(BaseUserManager):
    use_in_migrations = True

    # El correo es el identificador de acceso y se guarda siempre en minúsculas. El
    # `normalize_email` de Django solo baja a minúsculas el dominio, y dos cuentas
    # `Ana@x.com` y `ana@x.com` serían distintas para la base.
    @override
    @classmethod
    def normalize_email(cls, email: str | None) -> str:
        return (email or "").strip().lower()

    async def acreate_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> ApiUser:
        return await sync_to_async(self.create_superuser)(
            email,
            password,
            **extra_fields,
        )

    async def acreate_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> ApiUser:
        return await sync_to_async(self.create_user)(email, password, **extra_fields)

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> ApiUser:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields["is_staff"] is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)

    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> ApiUser:
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        return self._create_user(email, password, **extra_fields)

    # el trigger impide insertar usuarios por cualquier otra vía: esta es la única
    # puerta, y es la que guarda la contraseña ya con hash
    @ignore("apiauth.ApiUser:trg_apiuser_protect_insert")
    def _create_user(
        self,
        email: str,
        password: str | None,
        **extra_fields: object,
    ) -> ApiUser:
        if not email:
            raise ValueError("The given email must be set")

        status = extra_fields.setdefault("status", ApiUserStatus.ACTIVE)

        # `is_active` es el reflejo de `status` y la base exige que coincidan
        extra_fields["is_active"] = status == ApiUserStatus.ACTIVE

        # una cuenta que nace activa nace verificada, salvo que se diga otra cosa
        if status == ApiUserStatus.ACTIVE:
            extra_fields.setdefault("verified_at", now())

        user: ApiUser = self.model(email=self.normalize_email(email), **extra_fields)

        user.set_password(password)  # una contraseña `None` queda inutilizable

        # El insert va en su propio savepoint: si falla (correo repetido...) y esto
        # corre dentro de otra transacción, esta queda utilizable y `ignore` puede
        # limpiar su estado. Sin esto el error real se pierde detrás de un
        # `TransactionManagementError`.
        with atomic(using=self._db):
            user.save(using=self._db)

        return user
