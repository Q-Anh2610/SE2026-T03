"""Quản lý kết nối và transaction ghi PostgreSQL cho từng asset."""


class PersistenceError(Exception):
    """Lỗi ghi DB an toàn để đưa vào báo cáo."""


class DatabaseWriter:
    def __enter__(self):
        from app.db.session import create_db_engine

        self.engine = create_db_engine()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.engine.dispose()
        return False

    def __call__(self, asset, preview):
        from sqlalchemy.exc import SQLAlchemyError
        from sqlalchemy.orm import Session

        from app.ingestion.repository import upsert_downloaded_asset

        try:
            with Session(self.engine) as session:
                with session.begin():
                    upsert_downloaded_asset(session, asset, preview)

        except ValueError as exc:
            raise PersistenceError(str(exc)) from exc

        except SQLAlchemyError as exc:
            # Không đưa SQL, tham số hoặc credentials vào báo cáo.
            raise PersistenceError(
                "Không ghi được PostgreSQL; transaction asset đã rollback."
            ) from exc