import json
import re

from datetime import time
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, override

from django.core.management.base import BaseCommand, CommandError
from django.db.transaction import atomic
from django.utils.timezone import now

from api_catalogs.models import CulturalPillar
from api_core.config import CONFIG
from api_rewards.services.badges import sync_badge
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


########################################################################################


class Command(BaseCommand):
    help = (
        "Carga los lugares y circuitos de ejemplo de la app (solo desarrollo y demo). "
        "Crea las alcaldías verificadas que organizan los circuitos creativos."
    )

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Correr aunque DEPLOY esté activo (no se recomienda).",
        )

    @override
    def handle(self, *args: object, **options: Any) -> None:
        if CONFIG.DEPLOY and not options["force"]:
            raise CommandError(
                "Es contenido de ejemplo: con DEPLOY=True hace falta --force."
            )

        cities: dict[str, City] = {str(city.name): city for city in City.objects.all()}
        pillars: dict[str, CulturalPillar] = {
            str(pillar.label): pillar for pillar in CulturalPillar.objects.all()
        }

        with atomic():
            points = self.load_points(cities, pillars)
            self.load_circuits(cities, points)

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
    ) -> None:
        published: CircuitStatus = CircuitStatus.objects.get(code="publicado")
        count: int = 0

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

            count += 1

        self.stdout.write(f"Circuitos: {count}")
