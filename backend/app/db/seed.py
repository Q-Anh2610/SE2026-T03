"""Seed 7 fixture assets; chạy lại không ghi đè hay tạo bản ghi trùng."""

import hashlib

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.session import create_db_engine
from app.models import Asset


def sample_assets() -> list[dict]:
    names = ["Ghế gỗ", "Bàn tròn", "Đèn bàn", "Kệ sách", "Bình hoa", "Ghế sofa", "Chậu cây"]
    return [
        {
            "asset_id": f"mock-asset-{i:03d}",
            "source": "mock",
            "source_id": f"mock-{i:03d}",
            "name": name,
            "description": "Fixture tự tạo để thử DB; không phải asset 3D hoặc metadata nguồn thật.",
            "tags": ["mock", "nội thất"],
            "category": "Nội thất",
            "formats": [],
            "checksum": hashlib.sha256(f"fixture-v1:{i}:{name}".encode()).hexdigest(),
            "ingestion_status": "pending",
        }
        for i, name in enumerate(names, start=1)
    ]


def seed_assets(session: Session) -> int:
    statement = (
        insert(Asset)
        .values(sample_assets())
        .on_conflict_do_nothing(index_elements=["asset_id"])
        .returning(Asset.asset_id)
    )
    return len(session.scalars(statement).all())


def main() -> None:
    engine = create_db_engine()
    try:
        with Session(engine) as session, session.begin():
            inserted = seed_assets(session)
        print(f"Seed completed: inserted {inserted} mock assets; existing rows retained.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
