import json
import re

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, override

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db.transaction import atomic
from django.utils.timezone import get_current_timezone, localdate, now

from api_agenda.models import Event, EventStatus
from api_auth.models import ApiUser, ApiUserGroups, ApiUserTotpDevice
from api_catalogs.models import (
    BenefitType,
    BusinessType,
    CulturalPillar,
    Currency,
    EventCategory,
    InstitutionType,
    Language,
    ServiceType,
)
from api_catalogs.seeder import SERVICE_GUIDE
from api_core.config import CONFIG
from api_organizations.models import Business, CulturalInstitution
from api_profiles.enums import ProviderStates
from api_profiles.models import (
    ProviderLanguage,
    ProviderProfile,
    ProviderService,
    ProviderStatus,
)
from api_rewards.models import CampaignStatus, CouponCampaign
from api_rewards.services.badges import sync_badge
from api_services.models import GuidedDeparture
from api_territory.models import (
    Circuit,
    CircuitStatus,
    CircuitStop,
    City,
    Municipality,
    PointOfInterest,
)
from api_territory.services.images import replace_photos

if TYPE_CHECKING:
    from argparse import ArgumentParser

########################################################################################

FIXTURES: Final[Path] = Path(__file__).resolve().parents[2] / "fixtures"

CIRCUIT_CATEGORIES: Final[dict[str, str]] = {
    "Ciudad": "city",
    "Cultura": "culture",
    "Naturaleza": "nature",
}
DIFFICULTIES: Final[dict[str, str]] = {"Fácil": "easy", "Moderado": "moderate"}

CLOCK: Final[re.Pattern[str]] = re.compile(
    r"^\s*(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?\s*$", re.IGNORECASE
)
HOURS: Final[re.Pattern[str]] = re.compile(r"(\d+)\s*h")
MINUTES: Final[re.Pattern[str]] = re.compile(r"(\d+)\s*min")

# - las salidas de guía que se publican en cada circuito, a tantos días de la carga (más
#   uno o dos según el circuito); al desplegar otro día se agregan las que falten
DEPARTURE_DAYS: Final[tuple[int, ...]] = (3, 6, 10, 13)
DEPARTURE_CAPACITY: Final[int] = 12

########################################################################################


def clock(text: str | None) -> time | None:
    if not text:
        return None

    match = CLOCK.match(text)

    if match is None:
        raise CommandError(f"Hora que no se entiende: {text!r}")

    hour, minute, half = int(match[1]) % 12, int(match[2]), match[3].lower()

    return time(hour + (12 if half == "p" else 0), minute)


def minutes(text: str) -> int:
    hours = HOURS.search(text)
    rest = MINUTES.search(text)

    total: int = (int(hours[1]) * 60 if hours else 0) + (int(rest[1]) if rest else 0)

    return total or 30


def read(name: str) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads((FIXTURES / name).read_text("utf-8"))

    return data


# La alcaldía que organiza un circuito creativo de ejemplo; una real sin verificar no
# se toca.
def organizer(city: City, name: str) -> Municipality:
    municipality, _ = Municipality.objects.get_or_create(
        city=city,
        defaults={
            "contact_email": f"alcaldia.{city.code}@example.com",
            "document_key": "legal-document/ejemplo.pdf",
            "name": name,
            "phone": "2222-0000",
            "verified_at": now(),
        },
    )

    if municipality.verified_at is None:
        raise CommandError(
            f"La alcaldía de {city.name} existe y no está verificada: no se toca."
        )

    return municipality


# La institución que programa un evento de ejemplo, igual que la alcaldía.
def institution(city: City, name: str, kind: str) -> CulturalInstitution:
    found: CulturalInstitution | None = CulturalInstitution.objects.filter(
        city=city, name=name
    ).first()

    if found is None:
        found = CulturalInstitution.objects.create(
            city=city,
            contact_email=f"contacto.{city.code}@example.com",
            document_key="legal-document/ejemplo.pdf",
            institution_type=InstitutionType.objects.get(code=kind),
            name=name,
            phone="2222-0000",
        )
        CulturalInstitution.objects.filter(pk=found.pk).update(verified_at=now())
        found.refresh_from_db()

    if found.verified_at is None:
        raise CommandError(f"{name} existe y no está verificada: no se toca.")

    return found


# Una cuenta que ya existía pasa a superusuario sin nada con lo que otra persona pueda
# entrar: en un API de pruebas el alta acepta cualquier código, así que la contraseña y
# el segundo factor pueden ser de quien la creó con ese correo. Se entra con Google, que
# sí prueba que el correo es suyo.
def promote(user: ApiUser) -> None:
    found: Any = user

    ApiUserTotpDevice.objects.filter(api_user=user).delete()
    found.set_unusable_password()
    found.is_staff = True
    found.is_superuser = True
    found.sessions_revoked_at = now()
    found.verified_at = found.verified_at or now()
    found.save(
        update_fields=[
            "is_staff",
            "is_superuser",
            "password",
            "sessions_revoked_at",
            "verified_at",
        ]
    )


# Un guía o traductor ya aprobado, sin documentos: solo lo que el turista ve.
def create_provider(
    row: dict[str, Any],
    user: ApiUser,
    city: City | None,
) -> ProviderProfile:
    stamp: datetime = now()
    provider: ProviderProfile = ProviderProfile.objects.create(
        approved_at=stamp,
        carries_tourists=bool(row.get("carriesTourists")),
        city=city,
        created_at=stamp,
        phone=row["phone"],
        presentation=row.get("presentation", ""),
        status=ProviderStatus.objects.get(code=ProviderStates.ACTIVE),
        user=user,
    )
    ProviderService.objects.bulk_create(
        ProviderService(provider=provider, service=ServiceType.objects.get(code=code))
        for code in row["services"]
    )
    ProviderLanguage.objects.bulk_create(
        ProviderLanguage(
            language=Language.objects.get(code=spoken["code"]),
            level=spoken["level"],
            provider=provider,
        )
        for spoken in row["languages"]
    )
    # la cuenta ejerce un solo papel: guía si guía, si no traductor
    role: str = "Guía" if SERVICE_GUIDE in row["services"] else "Traductor"
    ApiUserGroups.objects.create(api_user=user, group=Group.objects.get(name=role))

    return provider


########################################################################################


class Command(BaseCommand):
    help = (
        "Carga el contenido de ejemplo (solo desarrollo y demo): los superusuarios del "
        "equipo, lugares, circuitos, eventos, guías y traductores con sus salidas, y "
        "comercios con sus cupones. Crea las alcaldías e instituciones verificadas que "
        "organizan."
    )

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Correr aunque DEPLOY esté activo (no se recomienda).",
        )
        parser.add_argument(
            "--on-deploy",
            action="store_true",
            help=(
                "Al desplegar: carga solo en las ramas de SEED_CONTENT_BRANCHES, y un "
                "error no detiene el despliegue."
            ),
        )

    @override
    def handle(self, *args: object, **options: Any) -> None:
        if options["on_deploy"]:
            self.on_deploy()
            return

        if CONFIG.DEPLOY and not options["force"]:
            raise CommandError(
                "Es contenido de ejemplo: con DEPLOY=True hace falta --force."
            )

        self.load()

    def on_deploy(self) -> None:
        branch: str = CONFIG.RAILWAY_GIT_BRANCH

        if branch not in CONFIG.SEED_CONTENT_BRANCHES:
            self.stdout.write(
                f"La rama {branch or '(sin rama)'} no carga contenido de ejemplo."
            )
            return

        # la carga va en una transacción: si algo falla no queda nada a medias, y el
        # despliegue sigue con lo que ya había
        try:
            self.load()
        except Exception as e:  # ruff: ignore[blind-except]
            self.stderr.write(f"No se cargó el contenido de ejemplo: {e}")

    def load(self) -> None:
        cities: dict[str, City] = {str(city.name): city for city in City.objects.all()}
        pillars: dict[str, CulturalPillar] = {
            str(pillar.label): pillar for pillar in CulturalPillar.objects.all()
        }

        with atomic():
            self.load_team()
            points = self.load_points(cities, pillars)
            circuits = self.load_circuits(cities, points)
            self.load_events(cities)
            guides = self.load_providers(cities)
            self.load_departures(circuits, guides)
            self.load_businesses(cities)

    ####################################################################################
    # Equipo

    # Los superusuarios del equipo de K'Plan. Sin contraseña: entran al portal con
    # Google (sin proveedor de correo no hay forma de recuperar una).
    def load_team(self) -> None:
        rows: list[dict[str, Any]] = read("team.json")

        for row in rows:
            user: ApiUser | None = ApiUser.objects.filter(email=row["email"]).first()

            if user is None:
                ApiUser.objects.create_superuser(
                    email=row["email"],
                    first_name=row["firstName"],
                    last_name=row["lastName"],
                    verified_at=now(),
                )
            elif not user.is_superuser:
                promote(user)

        self.stdout.write(f"Superusuarios del equipo: {len(rows)}")

    ####################################################################################
    # Lugares y circuitos

    def load_points(
        self,
        cities: dict[str, City],
        pillars: dict[str, CulturalPillar],
    ) -> dict[str, PointOfInterest]:
        points: dict[str, PointOfInterest] = {}
        skipped: set[str] = set()

        for row in read("stops.json"):
            city: City | None = cities.get(row["city"])

            if city is None:
                skipped.add(row["city"])
                continue

            point, created = PointOfInterest.objects.get_or_create(
                city=city,
                name=row["name"],
                defaults={
                    "address": row.get("address", "")[:140],
                    "closes_at": clock(row.get("closesAt")),
                    "description": row.get("description", ""),
                    "has_badge": bool(row.get("hasBadge")),
                    "latitude": Decimal(str(row["coordinates"]["latitude"])),
                    "longitude": Decimal(str(row["coordinates"]["longitude"])),
                    "opens_at": clock(row.get("opensAt")),
                    "pillar": pillars[row["category"]],
                    "rating": Decimal(str(row.get("rating", 0))),
                    "reviews_count": int(row.get("reviewsCount", 0)),
                    "tip": row.get("tip", "")[:140],
                    "visit_minutes": minutes(row.get("duration", "")),
                },
            )

            if created:
                replace_photos("point", point, row.get("images", []))

            sync_badge(point)
            points[row["id"]] = point

        City.objects.filter(pk__in={point.city_id for point in points.values()}).update(  # ty: ignore[unresolved-attribute]
            active=True
        )

        for name in sorted(skipped):
            self.stdout.write(f"Sin ciudad en el catálogo, se salta: {name}")

        self.stdout.write(f"Lugares: {len(points)}")

        return points

    def load_circuits(
        self,
        cities: dict[str, City],
        points: dict[str, PointOfInterest],
    ) -> list[Circuit]:
        published: CircuitStatus = CircuitStatus.objects.get(code="publicado")
        circuits: list[Circuit] = []

        for row in read("circuits.json"):
            city: City | None = cities.get(row["city"])

            if city is None or any(stop not in points for stop in row["stopIds"]):
                self.stdout.write(f"Se salta el circuito {row['title']!r}")
                continue

            creative: bool = bool(row.get("isCreativeCircuit"))
            location: dict[str, float] = row["location"]

            circuit, created = Circuit.objects.get_or_create(
                city=city,
                title=row["title"],
                defaults={
                    "booking_mode": "group" if creative else "private",
                    "bonus_badges": 3 if creative else 0,
                    "category": CIRCUIT_CATEGORIES[row["category"]],
                    "description": row["description"],
                    "difficulty": DIFFICULTIES[row["difficulty"]],
                    "includes": row.get("includes", ""),
                    "kind": "creative" if creative else "private",
                    "meeting_latitude": Decimal(str(location["latitude"])),
                    "meeting_longitude": Decimal(str(location["longitude"])),
                    "meeting_point": row.get("meetingPoint", "")[:200],
                    "municipality": (
                        organizer(city, row.get("organizer", "")) if creative else None
                    ),
                    "notes": row.get("notes", ""),
                    "price_adult": int(row.get("priceAdult", 0)),
                    "price_child": int(row.get("priceChild", 0)),
                    "published_at": now(),
                    "rating": Decimal(str(row.get("rating", 0))),
                    "recommendations": row.get("recommendations", ""),
                    "reviews_count": int(row.get("reviewsCount", 0)),
                    "short_title": row["shortTitle"][:28],
                    "start_times": [
                        value
                        for value in (clock(text) for text in row.get("startTimes", []))
                        if value is not None
                    ],
                    "status": published,
                    "subtitle": row["subtitle"][:60],
                    "travel_mode": row.get("travelMode", "walking"),
                },
            )

            if created:
                legs: dict[str, int] = row.get("legMinutes", {})

                CircuitStop.objects.bulk_create(
                    CircuitStop(
                        circuit=circuit,
                        leg_minutes=legs.get(stop),
                        order=order,
                        point=points[stop],
                    )
                    for order, stop in enumerate(row["stopIds"])
                )
                replace_photos("circuit", circuit, row.get("images", []))

            circuits.append(circuit)

        self.stdout.write(f"Circuitos: {len(circuits)}")

        return circuits

    ####################################################################################
    # Agenda

    def load_events(self, cities: dict[str, City]) -> None:
        scheduled: EventStatus = EventStatus.objects.get(code="programado")
        categories: dict[str, EventCategory] = {
            str(category.label): category for category in EventCategory.objects.all()
        }
        count: int = 0

        for row in read("events.json"):
            city: City | None = cities.get(row["city"])

            if city is None:
                self.stdout.write(f"Se salta el evento {row['name']!r}")
                continue

            kind: str | None = row.get("organizerKind")
            event, created = Event.objects.get_or_create(
                city=city,
                name=row["name"],
                start_date=date.fromisoformat(row["startDate"]),
                defaults={
                    "address": row.get("address", "")[:200],
                    "category": categories[row["category"]],
                    "description": row.get("description", ""),
                    "end_date": date.fromisoformat(row["endDate"]),
                    "end_time": time.fromisoformat(row["endTime"]),
                    "entry_price": int(row.get("entryPrice") or 0),
                    "featured": bool(row.get("featured")),
                    "institution": (
                        institution(
                            city,
                            row["organizer"],
                            row.get("institutionType", "casa_cultura"),
                        )
                        if kind == "institution"
                        else None
                    ),
                    "latitude": Decimal(str(row["coordinates"]["latitude"])),
                    "longitude": Decimal(str(row["coordinates"]["longitude"])),
                    "municipality": (
                        organizer(city, row["organizer"])
                        if kind == "municipality"
                        else None
                    ),
                    "start_time": time.fromisoformat(row["startTime"]),
                    "status": scheduled,
                    "venue": row["venue"][:150],
                },
            )

            if created:
                replace_photos("event", event, row.get("images", []))

            count += 1

        self.stdout.write(f"Eventos: {count}")

    ####################################################################################
    # Guías y traductores

    # Devuelve los guías por ciudad (nula: todo el país), para publicar sus salidas.
    def load_providers(
        self, cities: dict[str, City]
    ) -> dict[Any, list[ProviderProfile]]:
        guides: dict[Any, list[ProviderProfile]] = {}
        count: int = 0

        for row in read("providers.json"):
            city: City | None = cities.get(row["city"]) if row["city"] else None
            user: ApiUser | None = ApiUser.objects.filter(email=row["email"]).first()

            if user is None:
                user = ApiUser.objects.create_user(
                    birth_date=date.fromisoformat(row["birthDate"]),
                    email=row["email"],
                    first_name=row["firstName"],
                    last_name=row["lastName"],
                    nationality="NI",
                    verified_at=now(),
                )

            provider: ProviderProfile | None = ProviderProfile.objects.filter(
                user=user
            ).first()

            if provider is None:
                # una cuenta que ya existe con otro papel no se convierte en prestador
                if ApiUserGroups.objects.filter(api_user=user).exists():
                    self.stdout.write(f"Se salta {row['email']}: ya tiene otro papel")
                    continue

                provider = create_provider(row, user, city)

            count += 1

            if SERVICE_GUIDE in row["services"]:
                found: Any = provider
                guides.setdefault(found.city_id, []).append(provider)

        self.stdout.write(f"Guías y traductores: {count}")

        return guides

    # Las salidas que los guías de la ciudad publican en cada circuito; la de un
    # circuito privado se la queda la primera reserva.
    def load_departures(
        self,
        circuits: list[Circuit],
        guides: dict[Any, list[ProviderProfile]],
    ) -> None:
        today: date = localdate()
        count: int = 0

        for index, circuit in enumerate(circuits):
            found: Any = circuit
            candidates: list[ProviderProfile] = guides.get(found.city_id) or guides.get(
                None, []
            )

            if not candidates or not found.start_times:
                continue

            for turn, offset in enumerate(DEPARTURE_DAYS):
                provider: ProviderProfile = candidates[(index + turn) % len(candidates)]
                # cada circuito corre un día para que los guías compartidos no choquen
                day: date = today + timedelta(days=offset + index % 3)
                start: time = found.start_times[turn % len(found.start_times)]

                if GuidedDeparture.objects.filter(
                    cancelled_at__isnull=True,
                    date=day,
                    provider=provider,
                    start_time=start,
                ).exists():
                    continue

                GuidedDeparture.objects.create(
                    capacity=DEPARTURE_CAPACITY,
                    circuit=circuit,
                    date=day,
                    exclusive=found.booking_mode == "private",
                    provider=provider,
                    start_time=start,
                    transport_included=found.travel_mode == "vehicle",
                )
                count += 1

        self.stdout.write(f"Salidas nuevas: {count}")

    ####################################################################################
    # Comercios y cupones

    def load_businesses(self, cities: dict[str, City]) -> None:
        active: CampaignStatus = CampaignStatus.objects.get(code="activa")
        benefits: dict[str, BenefitType] = {
            str(benefit.code): benefit for benefit in BenefitType.objects.all()
        }
        cordobas: Currency = Currency.objects.get(code="NIO")
        campaigns: int = 0

        for row in read("businesses.json"):
            city: City | None = cities.get(row["city"])

            if city is None:
                self.stdout.write(f"Se salta el comercio {row['name']!r}")
                continue

            business: Business | None = Business.objects.filter(ruc=row["ruc"]).first()

            if business is None:
                business = Business.objects.create(
                    address=row["address"],
                    business_type=BusinessType.objects.get(code=row["businessType"]),
                    city=city,
                    latitude=Decimal(str(row["coordinates"]["latitude"])),
                    longitude=Decimal(str(row["coordinates"]["longitude"])),
                    name=row["name"],
                    phone=row["phone"],
                    ruc=row["ruc"],
                )
                Business.objects.filter(pk=business.pk).update(verified_at=now())

            for campaign in row["campaigns"]:
                benefit: BenefitType = benefits[campaign["benefitType"]]
                amount: int | None = campaign.get("benefitAmount")

                CouponCampaign.objects.get_or_create(
                    business=business,
                    title=campaign["title"],
                    defaults={
                        "benefit_amount": None if amount is None else Decimal(amount),
                        "benefit_type": benefit,
                        "cost_badges": campaign["costBadges"],
                        "currency": (
                            cordobas if benefit.code == "descuento_monto" else None
                        ),
                        "description": campaign.get("description", ""),
                        "expires_at": datetime.combine(
                            date.fromisoformat(campaign["expiresOn"]),
                            time(23, 59),
                            tzinfo=get_current_timezone(),
                        ),
                        "image_key": campaign.get("image", ""),
                        "status": active,
                        "stock_total": campaign["stock"],
                        "terms": campaign.get("terms", ""),
                    },
                )
                campaigns += 1

        self.stdout.write(f"Campañas de cupones: {campaigns}")
