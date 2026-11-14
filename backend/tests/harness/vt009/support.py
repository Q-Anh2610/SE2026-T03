"""Real search/Qdrant, synthetic 3D encoder and server-side test identities."""

from contextlib import contextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from qdrant_client import QdrantClient

from app.schemas.text_search import TextSearchFilters
from app.search.configurable_search import ConfigurableSearch
from app.search.qdrant_store import IndexConfig, QdrantStore
from app.search.retrieval_config import RetrievalConfig
from app.search.text_search import TextSearchService
from app.services.text_search import SearchUnavailable
from app.services.text_search_runtime import CLIPTextSearchAdapter


class FixtureEncoder:
    model_id = "fixture-clip"
    revision = "fixture-v1"
    dimension = 3
    preprocessing_version = "fixture-l2"

    def encode_text(self, query):
        return [1.0, 0.0, 0.0]


class LimitInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_limit: int = Field(strict=True, ge=1, le=200)


class QueryInput(BaseModel):
    query: str = "chair"
    filters: TextSearchFilters = Field(default_factory=TextSearchFilters)


def make_app(boundary):
    app = FastAPI(title="VT-009 sandbox - test credentials only")
    # Fixed fake credentials for local tests, never real tokens or user-supplied roles.
    identities = {"fixture-admin": "admin", "fixture-viewer": "viewer"}

    def identity(authorization: str | None = Header(default=None)):
        role = identities.get((authorization or "").removeprefix("Bearer "))
        if role is None or not (authorization or "").startswith("Bearer "):
            raise HTTPException(401, "Unknown test credential")
        return role

    @app.put("/harness/config")
    def change(value: LimitInput, role=Depends(identity)):
        try:
            return boundary.change_limit(role, value.candidate_limit).model_dump(mode="json")
        except PermissionError:
            raise HTTPException(403, "Forbidden") from None
        except OSError:
            raise HTTPException(503, "Configuration not saved") from None

    @app.post("/harness/search")
    def search(value: QueryInput):
        try:
            return boundary.search(value.query, value.filters).model_dump(mode="json")
        except (OSError, ValidationError, SearchUnavailable):
            raise HTTPException(503, "Search unavailable") from None

    return app


AUTH_ADMIN = {"Authorization": "Bearer fixture-admin"}
AUTH_VIEWER = {"Authorization": "Bearer fixture-viewer"}


@contextmanager
def environment(directory: Path, count: int = 205):
    path = directory / "retrieval.json"
    path.write_text(RetrievalConfig().model_dump_json(), encoding="utf-8")
    client = QdrantClient(location=":memory:")
    config = IndexConfig("fixture-clip", "fixture-v1", 3, "fixture-l2",
                         "fixture-205", "fixture-index-v1")
    store = QdrantStore(client, collection_name="vt009", config=config)
    store.upsert([
        {"asset_id": f"a{i:03}", "vector": [1.0, 0.0, 0.0], "metadata": {
            "asset_id": f"a{i:03}", "category": "chair" if i < 200 else "lamp",
            "license": "by", "formats": ["glb"], "face_count": i,
        }} for i in range(count)
    ])
    adapter = CLIPTextSearchAdapter(TextSearchService(FixtureEncoder(), store), client)
    boundary = ConfigurableSearch(adapter, path)
    try:
        with TestClient(make_app(boundary)) as http:
            yield boundary, http, store
    finally:
        adapter.close()
