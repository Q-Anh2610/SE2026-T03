"""Bootstrap + service #60 + persistent Qdrant + HTTP/DB; encoder fixture 3D."""

from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest
from qdrant_client import QdrantClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.main import create_app
from app.models import Asset, SearchEvent
from app.search.index_manifest import IndexManifest, save_index_manifest
from app.search.qdrant_store import IndexConfig, QdrantStore
from app.search.retrieval_config import RetrievalConfig
from app.services import text_search_runtime as runtime
from scripts.asset_api_test_support import isolated_asset_database

pytestmark = pytest.mark.integration


def test_actual_bootstrap_retrieval_pagination_events_and_chi_error_mapping(tmp_path, monkeypatch):
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set TEST_DATABASE_URL to isolated PostgreSQL test_* database.")
    metadata = [dict(asset_id="bootstrap-" + x, source="fixture", source_id=x, name=x,
                     formats=["glb"], tags=[], category="chair", license="fixture-only") for x in ("a", "b")]
    source = tmp_path / "source.json"
    source.write_text(json.dumps(metadata), encoding="utf-8")
    ready = tmp_path / "ready.json"
    ready.write_text("[]", encoding="utf-8")
    digest = lambda path: sha256(path.read_bytes()).hexdigest()
    config = IndexConfig("fixture-clip", "fixture-revision", 3, "fixture-rgb-l2",
                         "fixture-sha256:" + digest(source), "fixture-index-v1")
    storage = tmp_path / "qdrant"
    with closing(QdrantClient(path=str(storage))) as client:
        store = QdrantStore(client, collection_name="bootstrap", config=config)
        store.upsert([dict(asset_id=row["asset_id"], metadata=row, vector=vector)
                      for row, vector in zip(metadata, ([1., 0., 0.], [0., 1., 0.]), strict=True)])
    now = datetime.now(timezone.utc)
    manifest = IndexManifest(created_at_utc=now, observed_at_utc=now, index_config=asdict(config),
        collection="bootstrap", vector_name=store.vector_name, processor_revision=config.model_revision,
        tokenizer_revision=config.model_revision, max_text_tokens=77,
        source_manifest="source.json", source_manifest_sha256=digest(source),
        ready_manifest="ready.json", ready_manifest_sha256=digest(ready), asset_count=2, point_count=2,
        code_commit="0" * 40, working_tree_dirty=False, module_sha256={"fixture.py": "0" * 64},
        retrieval_config=RetrievalConfig())
    save_index_manifest(manifest, tmp_path / "index.json")
    calls = []

    def encoder():
        calls.append("load")
        return SimpleNamespace(model_id=config.model_id, revision=config.model_revision, dimension=3,
            preprocessing_version=config.preprocessing_version,
            model=SimpleNamespace(config=SimpleNamespace(text_config=SimpleNamespace(max_position_embeddings=77))),
            encode_text=lambda query: [1., 0., 0.])

    monkeypatch.setattr(runtime, "load_encoder", encoder)
    settings = Settings(_env_file=None, env="test", text_search_source="service",
        text_index_manifest=tmp_path / "index.json", text_index_root=tmp_path, text_qdrant_local_path=storage)
    with isolated_asset_database(value) as db:
        db.migrate()
        with Session(db.engine) as session, session.begin():
            session.add_all([Asset(**row) for row in metadata])
        app = create_app(settings)
        app.state.db_engine = db.engine
        with TestClient(app) as client:
            for page in (1, 2):
                response = client.post("/api/v1/search/text", json={"query": "chair", "page": page, "limit": 1})
                assert response.status_code == 200, response.text
                body = response.json()
                assert body["results"][0]["asset"]["asset_id"] == metadata[page - 1]["asset_id"]
                assert body["versions"] == manifest.execution_versions().model_dump()
            assert calls == ["load"]
            # Own fixture index only: missing collection must map Chi's error to 503.
            app.state.text_search_service.client.delete_collection("bootstrap")
            unavailable = client.post("/api/v1/search/text", json={"query": "chair"})
            assert unavailable.status_code == 503
            assert unavailable.json()["error"]["code"] == "SEARCH_UNAVAILABLE"
            with Session(db.engine) as session:
                assert session.scalar(select(func.count()).select_from(SearchEvent)) == 2
            assert db.engine.pool.checkedout() == 0
        assert app.state.text_search_service.closed
    with closing(QdrantClient(path=str(storage))) as client:
        assert not client.collection_exists("bootstrap")  # File lock released by lifespan.
