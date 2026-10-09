from typing import TYPE_CHECKING, Any

from django.db.transaction import atomic

from api_catalogs.models import Language
from api_core.services.uploads import UploadKinds, verify_upload
from api_profiles.enums import LEVEL_BY_API_NAME
from api_profiles.models import ProviderLanguage, ProviderProfile
from api_profiles.services.application import own_profile_sync
from api_profiles.services.documents import field_error

if TYPE_CHECKING:
    from api_auth.models import ApiUser
    from api_profiles.schemas.profile import ProviderProfilePatch

########################################################################################


# Cambia lo descriptivo del perfil: la presentación, el teléfono, los idiomas y la foto.
# Se ve de inmediato y no pasa por la revisión (RF-P-06).
def update_profile_sync(user: ApiUser, patch: ProviderProfilePatch) -> ProviderProfile:
    changes: dict[str, Any] = patch.model_dump(exclude_unset=True)
    photo_key: str | None = changes.get("photo_key")

    if photo_key is not None:
        verify_upload(UploadKinds.PROVIDER_PHOTO, photo_key, field="photo_key")

    languages: dict[str, Language] = {}

    if "languages" in changes:
        codes: list[str] = [item.code for item in patch.languages]
        languages = {
            str(row.code): row
            for row in Language.objects.filter(active=True, code__in=codes)
        }

        for index, code in enumerate(codes):
            if code not in languages:
                raise field_error(f"languages.{index}.code", "Ese idioma no existe.")

    with atomic():
        profile: Any = own_profile_sync(user, lock=True)

        if "presentation" in changes:
            profile.presentation = patch.presentation

        if "phone" in changes:
            profile.phone = patch.phone

        if "photo_key" in changes:
            profile.photo_key = photo_key or ""

        profile.save()

        if "languages" in changes:
            ProviderLanguage.objects.filter(provider=profile).delete()
            ProviderLanguage.objects.bulk_create(
                ProviderLanguage(
                    language=languages[item.code],
                    level=LEVEL_BY_API_NAME[item.level],
                    provider=profile,
                )
                for item in patch.languages
            )

    return own_profile_sync(user)
