from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from django.db.models import TextChoices

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

########################################################################################


# - lo que puede hacer una persona del equipo de K'Plan. Son los mismos identificadores
#   que usa el portal (`src/data/models/access.ts`): un rol es un grupo con un conjunto
#   de ellos
class FunctionalPermissions(TextChoices):
    AGENDA_VIEW = "agenda.view"
    BILLING_MANAGE = "billing.manage"
    BILLING_VIEW = "billing.view"
    CIRCUITS_MANAGE = "circuits.manage"
    CIRCUITS_VIEW = "circuits.view"
    CONTENT_MODERATE = "content.moderate"
    DEMOS_MANAGE = "demos.manage"
    DEMOS_VIEW = "demos.view"
    GUIDES_DECIDE = "guides.decide"
    GUIDES_REVIEW = "guides.review"
    GUIDES_VIEW = "guides.view"
    ORGANIZATIONS_MANAGE = "organizations.manage"
    ORGANIZATIONS_REVIEW = "organizations.review"
    ORGANIZATIONS_VIEW = "organizations.view"
    PLACES_MANAGE = "places.manage"
    PLACES_VIEW = "places.view"
    RELEASES_MANAGE = "releases.manage"
    RELEASES_VIEW = "releases.view"
    STAFF_MANAGE = "staff.manage"
    USERS_MANAGE = "users.manage"
    USERS_VIEW = "users.view"


@dataclass(frozen=True, slots=True)
class PermissionInfo:
    id: str
    module: str
    label: str
    description: str


########################################################################################

P = FunctionalPermissions

# en el orden en que el portal los muestra, agrupados por módulo
CATALOG: Final[Sequence[PermissionInfo]] = (
    PermissionInfo(
        P.AGENDA_VIEW,
        "Agenda",
        "Ver la agenda",
        "La semana de llegadas de todos los lugares de K'Plan.",
    ),
    PermissionInfo(
        P.ORGANIZATIONS_VIEW,
        "Organizaciones",
        "Ver organizaciones",
        "Ve las organizaciones y sus solicitudes sin poder cambiarlas.",
    ),
    PermissionInfo(
        P.ORGANIZATIONS_REVIEW,
        "Organizaciones",
        "Admitir organizaciones",
        "Aprueba o rechaza los negocios y alcaldías nuevos.",
    ),
    PermissionInfo(
        P.ORGANIZATIONS_MANAGE,
        "Organizaciones",
        "Administrar organizaciones",
        "Crea, edita, suspende y reactiva organizaciones.",
    ),
    PermissionInfo(
        P.GUIDES_VIEW,
        "Guías y traductores",
        "Ver solicitudes",
        "Ve las solicitudes de guías y traductores sin poder revisarlas.",
    ),
    PermissionInfo(
        P.GUIDES_REVIEW,
        "Guías y traductores",
        "Revisar solicitudes",
        "Revisa documentos y antecedentes, y pide correcciones.",
    ),
    PermissionInfo(
        P.GUIDES_DECIDE,
        "Guías y traductores",
        "Decidir solicitudes",
        "Da la decisión final: aprueba o rechaza al guía o traductor.",
    ),
    PermissionInfo(
        P.PLACES_VIEW,
        "Contenido",
        "Ver lugares",
        "Ve la ficha de cualquier parada de la app sin poder editarla.",
    ),
    PermissionInfo(
        P.PLACES_MANAGE,
        "Contenido",
        "Editar lugares",
        "Edita la ficha de cualquier parada de la app.",
    ),
    PermissionInfo(
        P.CIRCUITS_VIEW,
        "Contenido",
        "Ver circuitos",
        "Ve los circuitos de la app sin poder editarlos.",
    ),
    PermissionInfo(
        P.CIRCUITS_MANAGE,
        "Contenido",
        "Circuitos",
        "Crea y edita los circuitos de la app, incluidos los especiales de K'Plan "
        "y sus insignias extra.",
    ),
    PermissionInfo(
        P.CONTENT_MODERATE,
        "Contenido",
        "Moderar contenido",
        "Cupones, eventos y campañas de insignias de todas las organizaciones.",
    ),
    PermissionInfo(
        P.USERS_VIEW,
        "Usuarios",
        "Ver usuarios",
        "Ve a todos los usuarios sin poder suspenderlos ni cambiarlos.",
    ),
    PermissionInfo(
        P.USERS_MANAGE,
        "Usuarios",
        "Administrar usuarios",
        "Ve a todos los usuarios, suspende y reactiva cuentas.",
    ),
    PermissionInfo(
        P.STAFF_MANAGE,
        "Usuarios",
        "Administrar el equipo",
        "Invita a personas del equipo, les asigna un rol y edita los roles.",
    ),
    PermissionInfo(
        P.BILLING_VIEW,
        "Finanzas",
        "Ver cobros y tarifas",
        "Ve los cobros y las tarifas de K'Plan sin poder cambiarlos.",
    ),
    PermissionInfo(
        P.BILLING_MANAGE,
        "Finanzas",
        "Cobros y tarifas",
        "Ve los cobros y cambia las tarifas de K'Plan.",
    ),
    PermissionInfo(
        P.DEMOS_VIEW,
        "Sitio web",
        "Ver solicitudes de demo",
        "Ve quién pidió una demostración desde la landing, sin poder atenderla.",
    ),
    PermissionInfo(
        P.DEMOS_MANAGE,
        "Sitio web",
        "Atender solicitudes de demo",
        "Cambia el estado de las solicitudes de demo, anota el seguimiento y recibe "
        "el aviso de cada una nueva.",
    ),
    PermissionInfo(
        P.RELEASES_VIEW,
        "Sitio web",
        "Ver versiones de la app",
        "Ve los instaladores de la app y cuál se descarga desde la landing.",
    ),
    PermissionInfo(
        P.RELEASES_MANAGE,
        "Sitio web",
        "Publicar versiones de la app",
        "Sube los instaladores (APK, DMG, EXE), los publica en la landing y los "
        "retira.",
    ),
)

ALL_IDS: Final[frozenset[str]] = frozenset(info.id for info in CATALOG)

# Quién da, además, el permiso de solo ver: quien puede revisar o administrar un módulo
# también lo ve, sin que el rol tenga que marcar las dos casillas.
IMPLIED_BY: Final[Mapping[str, frozenset[str]]] = {
    P.BILLING_VIEW: frozenset({P.BILLING_MANAGE}),
    P.CIRCUITS_VIEW: frozenset({P.CIRCUITS_MANAGE}),
    P.DEMOS_VIEW: frozenset({P.DEMOS_MANAGE}),
    P.GUIDES_VIEW: frozenset({P.GUIDES_REVIEW, P.GUIDES_DECIDE}),
    P.ORGANIZATIONS_VIEW: frozenset({P.ORGANIZATIONS_REVIEW, P.ORGANIZATIONS_MANAGE}),
    P.PLACES_VIEW: frozenset({P.PLACES_MANAGE}),
    P.RELEASES_VIEW: frozenset({P.RELEASES_MANAGE}),
    P.USERS_VIEW: frozenset({P.USERS_MANAGE}),
}

########################################################################################


# - los permisos concedidos más los de solo ver que se desprenden de ellos
def expand_implied(granted: Iterable[str]) -> frozenset[str]:
    held: set[str] = set(granted)

    for viewing, stronger in IMPLIED_BY.items():
        if held & stronger:
            held.add(viewing)

    return frozenset(held)
