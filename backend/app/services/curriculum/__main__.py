"""Explicit offline entry point: python -m app.services.curriculum validate|import FILE."""

import argparse
import json
from pathlib import Path

from app.core.config import Settings
from app.db.database import create_database, initialize_database
from app.services.curriculum import CurriculumImporter, CurriculumValidator


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida/importa um pacote de currículo JSON")
    parser.add_argument("action", choices=["validate", "import"])
    parser.add_argument("file", type=Path)
    parser.add_argument("--database-url", default=None, help="URL do banco; omitir usa ATLAS_DATABASE_URL")
    args = parser.parse_args()
    payload = json.loads(args.file.read_text(encoding="utf-8"))
    package = CurriculumValidator().validate(payload)
    if args.action == "validate":
        print(json.dumps({"status": "VALID", "package_id": package.package_id, "version": package.version}))
        return
    engine, factory = create_database(args.database_url or Settings.from_env().database_url)
    try:
        initialize_database(engine)
        with factory.begin() as db:
            result = CurriculumImporter().import_package(db, package)
        print(json.dumps(result, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
