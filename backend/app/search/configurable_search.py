"""Optional VT-009 slice; not wired to the production HTTP application.

The caller supplies an authenticated, server-side role. Configuration is held
in one JSON file using the existing RetrievalConfig contract.
"""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock

from app.search.retrieval_config import RetrievalConfig


class ConfigurableSearch:
    def __init__(self, service, config_path: Path):
        self.service = service
        self.config_path = config_path
        self.lock = RLock()

    def snapshot(self) -> RetrievalConfig:
        with self.lock:
            return RetrievalConfig.model_validate_json(
                self.config_path.read_text(encoding="utf-8")
            )

    def change_limit(self, role: str, value: int) -> RetrievalConfig:
        if role != "admin":
            raise PermissionError("Administrator required.")
        config = RetrievalConfig.for_limit(value)
        with self.lock:
            temporary = None
            try:
                with NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".tmp",
                                        dir=self.config_path.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(config.model_dump_json())
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.config_path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return config

    def search(self, query, filters):
        config = self.snapshot()
        return self.service.search_text(
            query, filters, candidate_limit=config.candidate_limit
        )
