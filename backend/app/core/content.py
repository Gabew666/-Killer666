"""Identity and path of the reviewed institutional curriculum draft."""

from pathlib import Path

REAL_PACKAGE_ID = "uniasselvi-ia-simbolica-2026-2"
REAL_CURRICULUM_PATH = (
    Path(__file__).resolve().parents[3]
    / "curricula/uniasselvi/inteligencia_artificial_simbolica_2026-2.v0.1.0.json"
)
