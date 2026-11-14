"""Prepare an isolated 200-asset PostgreSQL fixture; keep it alive for audit.

Run from Git Bash with the repository's backend virtual environment.
This script does not read or update the business database or Qdrant.
"""

import argparse
from datetime import datetime, timezone
from getpass import getpass
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4


DATABASE = "test_issue101"
SOURCE = "data/manifests/objaverse_200.json"
SOURCE_HASH = "9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd"


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=True
    )
    return result.stdout


def read_source(repo):
    source_bytes = git(repo, "show", f"HEAD:{SOURCE}")
    if hashlib.sha256(source_bytes).hexdigest() != SOURCE_HASH:
        raise ValueError("Frozen source manifest hash does not match.")
    rows = json.loads(source_bytes.decode("utf-8-sig"))
    if json.loads((repo / SOURCE).read_text(encoding="utf-8-sig")) != rows:
        raise ValueError("Checkout metadata differs from the committed source.")
    if not isinstance(rows, list) or len(rows) != 200:
        raise ValueError("Expected 200 source records.")
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("Source records must be objects.")
    ids = [row.get("asset_id") for row in rows]
    if any(not isinstance(aid, str) or not aid for aid in ids):
        raise ValueError("Invalid source asset ID.")
    if len(set(ids)) != 200:
        raise ValueError("Duplicate source asset IDs.")
    return source_bytes, rows


def save_report(path, report):
    path.write_bytes(
        (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--host", choices=["127.0.0.1", "localhost", "::1"], default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--user", default="postgres")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        raise ValueError("Invalid PostgreSQL port.")
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "backend"))

    import psycopg
    from psycopg import sql
    from sqlalchemy import URL, func, select, text
    from app.ingestion.source_adapter import SourceAdapter
    from app.models import Asset
    from scripts.asset_api_test_support import isolated_asset_database

    # Validate the complete input before any database mutation.
    source_bytes, raw = read_source(repo)
    valid, invalid = SourceAdapter(repo / SOURCE).normalize_and_validate(raw)
    if invalid or len(valid) != 200:
        raise ValueError("SourceAdapter rejected source metadata; no DB preparation performed.")
    if valid != raw:
        raise ValueError("SourceAdapter changes this source; inspect differences before loading.")
    if any(row.get("model_version") is not None or row.get("index_version") is not None for row in valid):
        raise ValueError("Unexpected source model/index versions; inspect before loading.")
    print("Source validation passed: frozen hash, 200 unique IDs, 200 valid records.")
    print("Target database: test_issue101; a new UUID schema will be used.")
    password = getpass("PostgreSQL password (hidden): ")

    # Only create the explicitly named test DB. Never drop/recreate an existing DB.
    with psycopg.connect(
        host=args.host, port=args.port, user=args.user, password=password,
        dbname="postgres", autocommit=True, connect_timeout=5,
    ) as admin:
        found = admin.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (DATABASE,)
        ).fetchone()
        created_database = found is None
        if created_database:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DATABASE)))

    url = URL.create(
        "postgresql+psycopg", username=args.user, password=password,
        host=args.host, port=args.port, database=DATABASE,
    )
    output = repo / "work" / "issue101-db-preparation" / uuid4().hex
    output.mkdir(parents=True, exist_ok=False)
    report_path = output / "preparation.json"
    report = {
        "issue": 101,
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "isolated_fixture_from_frozen_manifest_not_business_db_sync_or_qdrant_audit",
        "source_path": SOURCE,
        "source_commit": git(repo, "rev-parse", "HEAD").decode().strip(),
        "source_manifest_sha256": SOURCE_HASH,
        "database": DATABASE,
        "database_created_this_run": created_database,
        "host": args.host,
        "port": args.port,
        "status": "preparing",
        "python": sys.version.split()[0],
    }

    schema_started = False
    try:
        # Helper creates and later removes ONLY its own UUID-named schema.
        with isolated_asset_database(url.render_as_string(hide_password=False)) as db:
            schema_started = True
            report["schema"] = db.schema
            report["schema_lifecycle"] = "open"
            save_report(report_path, report)
            db.migrate()
            with db.engine.begin() as connection:
                if connection.scalar(select(func.count()).select_from(Asset)) != 0:
                    raise ValueError("New isolated assets table is not empty.")
                connection.execute(Asset.__table__.insert(), valid)

            # Read back in a separate read-only transaction. No Qdrant involved.
            with db.engine.begin() as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                stored = [dict(row) for row in connection.execute(select(Asset.__table__)).mappings()]
                revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
                actual_schema = connection.scalar(text("SELECT current_schema()"))
                actual_database = connection.scalar(text("SELECT current_database()"))
            expected = {row["asset_id"]: row for row in valid}
            stored_by_id = {row["asset_id"]: row for row in stored}
            if actual_database != DATABASE or actual_schema != db.schema:
                raise ValueError("Read-back database/schema does not match the isolated target.")
            if len(stored) != 200 or set(stored_by_id) != set(expected):
                raise ValueError("Read-back count/IDs do not match source.")
            mismatches = [
                {"asset_id": aid, "field": field}
                for aid, record in expected.items()
                for field, value in record.items()
                if stored_by_id[aid][field] != value
            ]
            if mismatches:
                report["metadata_mismatches"] = mismatches
                raise ValueError("Read-back metadata differs from source.")
            (output / "source.json").write_bytes(source_bytes)
            report.update(
                status="prepared",
                asset_count=200,
                unique_asset_ids=200,
                migration_revision=revision,
                source_adapter_normalization_changes=0,
                metadata_mismatches=[],
                ingestion_statuses=sorted({row["ingestion_status"] for row in stored}),
                model_versions_set=sum(row["model_version"] is not None for row in stored),
                index_versions_set=sum(row["index_version"] is not None for row in stored),
                payload_audit="not_run",
                business_database_sync="not_verified",
            )
            save_report(report_path, report)
            print("PREPARED: 200 assets, 200 unique IDs, metadata read-back matched.")
            print("Database:", DATABASE)
            print("Schema:", db.schema)
            print("Migration revision:", revision)
            print("Report:", report_path)
            print("No downloaded/searchable or model/index versions were assigned.")
            print("KEEP THIS TERMINAL OPEN while another terminal runs the audit.")
            print("The schema is temporary. Leaving this program removes this schema.")
            print("Type CLEANUP only after saving all audit reports; it removes this run's schema.")
            while input("Command: ").strip() != "CLEANUP":
                print("Schema is still available. Type CLEANUP when audit/report saving is complete.")
    finally:
        if schema_started:
            report["schema_lifecycle"] = "context_closed_check_database_if_cleanup_failed"
            save_report(report_path, report)
    print("Helper finished cleanup of its own test schema. Database test_issue101 remains.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("Stopped; the helper attempts cleanup of its own temporary schema.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as error:
        # Avoid dumping connection strings, SQL parameters, or password-bearing exceptions.
        print(f"Preparation stopped ({type(error).__name__}). No success is claimed.", file=sys.stderr)
        if isinstance(error, (ValueError, FileNotFoundError, ModuleNotFoundError)):
            print(str(error), file=sys.stderr)
        if hasattr(error, "sqlstate") and error.sqlstate:
            print("PostgreSQL SQLSTATE:", error.sqlstate, file=sys.stderr)
        raise SystemExit(1)
