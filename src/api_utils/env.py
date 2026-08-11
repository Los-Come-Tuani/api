from pathlib import Path
from tomllib import loads
from typing import TYPE_CHECKING

from dmr.openapi import OpenAPIConfig

if TYPE_CHECKING:
    from typing import Final

########################################################################################

ROOT: Final[Path] = Path(__file__).resolve().parents[2]

########################################################################################

PYPROJECT: Final[dict] = loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

OPENAPI: Final[OpenAPIConfig] = OpenAPIConfig(
    description=PYPROJECT["project"]["description"],
    title=PYPROJECT["project"]["name"],
    version=PYPROJECT["project"]["version"],
)
