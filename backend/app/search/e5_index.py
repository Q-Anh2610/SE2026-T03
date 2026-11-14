"""Build/audit index metadata E5 riêng; không nối API hoặc chạy benchmark."""

from dataclasses import asdict, dataclass
from contextlib import closing
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isclose, isfinite, sqrt
from pathlib import Path
import re
from typing import Literal, Self
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator
from qdrant_client import QdrantClient

from app.embedding.e5_encoder import (
    DIMENSION, MAX_TEXT_TOKENS, MODEL_ID, MODEL_REVISION, PASSAGE_PREFIX,
    PREPROCESSING_VERSION, QUERY_PREFIX,
)
from app.schemas.text_search import TextSearchHit
from app.search.index_manifest import _portable_path
from app.search.qdrant_store import IndexConfig, QdrantStore, index_vector_name


SNAPSHOT = "home-interior-clear-200-v3"
SOURCE_SHA256 = "9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd"
CORPUS_SHA256 = "66efd87e34447c23b4171e13ac77d78a9c193519141d0dd6a31985c01e65b4f5"
RECIPE_VERSION = "e5-metadata-passage-v1-draft"
SERIALIZATION = {
    "format": "JSONL", "encoding": "UTF-8 without BOM",
    "record_order": "asset_id ascending", "json_sort_keys": True,
    "json_ensure_ascii": False, "json_separators": [",", ":"],
    "record_newline": "LF", "final_newline": True,
}


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def json_bytes(value, *, pretty=False) -> bytes:
    options = {"indent": 2} if pretty else {"separators": (",", ":")}
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       allow_nan=False, **options) + "\n").encode("utf-8")


def read_member(root: Path, relative: str) -> bytes:
    _portable_path(relative)
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Input không tồn tại hoặc nằm ngoài gói corpus/index.")
    return path.read_bytes()


@dataclass(frozen=True)
class MetadataCorpus:
    source_bytes: bytes
    corpus_bytes: bytes
    manifest_bytes: bytes
    manifest: dict
    rows: list[dict]
    metadata: dict[str, dict]


def load_metadata_corpus(root: Path, source_bytes: bytes, *,
                         expected_source_sha256: str,
                         expected_corpus_sha256: str,
                         expected_recipe_version: str,
                         manifest_name: str = "manifest.json") -> MetadataCorpus:
    """Đọc artifact đã tiếp nhận; không ghép passage lần hai hoặc đọc qrels.

    Caller phải cung cấp pin đã được xác nhận. Không lấy checksum kỳ vọng chỉ
    từ chính file manifest do bên ngoài truyền vào.
    """
    manifest_bytes = read_member(root, manifest_name)
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict):
        raise ValueError("Corpus manifest phải là object.")
    required = {
        "snapshot": SNAPSHOT,
        "source_path": "data/manifests/objaverse_200.json",
        "source_hash_basis": "raw Git blob bytes",
        "source_manifest_sha256": expected_source_sha256,
        "corpus_sha256": expected_corpus_sha256,
        "recipe_version": expected_recipe_version,
        "fields": ["name", "description", "tags", "category"],
        "text_policy": "Python str.split then join with one ASCII space",
        "tags_policy": "clean; drop empty; exact dedup; preserve first order",
        "tags_separator": ", ", "field_separator": "\n",
        "empty_policy": "omit empty fields; reject empty passage",
        "prefix_in_corpus": False, "serialization": SERIALIZATION,
        "asset_count": 200, "nonempty_passage_count": 200,
        "corpus_file": "corpus.jsonl", "errors": [],
        "checkout_matches_source_json": True,
    }
    for key, expected in required.items():
        if key not in manifest or json_bytes(manifest[key]) != json_bytes(expected):
            raise ValueError(f"Corpus manifest không khớp pin/policy: {key}")
    if not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("source_commit", ""))):
        raise ValueError("Corpus source_commit phải là Git SHA đầy đủ.")
    raw = read_member(root, "corpus.jsonl")
    if digest(source_bytes) != expected_source_sha256 or digest(raw) != expected_corpus_sha256:
        raise ValueError("SHA-256 source/corpus không khớp pin đã tiếp nhận.")
    source = json.loads(source_bytes.decode("utf-8-sig"))
    if not isinstance(source, list) or len(source) != 200:
        raise ValueError("Source cần đúng 200 records.")
    metadata = {}
    for record in source:
        if not isinstance(record, dict):
            raise ValueError("Source record phải là object.")
        aid = TextSearchHit(asset_id=record.get("asset_id"), score=0.0).asset_id
        if aid in metadata:
            raise ValueError("Source trùng asset_id.")
        metadata[aid] = record
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
        raise ValueError("Corpus phải UTF-8 không BOM và LF cuối file.")
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    ids = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"asset_id", "passage"}:
            raise ValueError("Corpus row cần đúng asset_id và passage.")
        aid = TextSearchHit(asset_id=row["asset_id"], score=0.0).asset_id
        passage = row["passage"]
        if not isinstance(passage, str) or not passage.strip() or passage != passage.strip():
            raise ValueError(f"Passage rỗng hoặc thừa whitespace biên: {aid}")
        ids.append(aid)
    if ids != sorted(metadata) or manifest.get("asset_ids") != ids:
        raise ValueError("Corpus/manifest/source không cùng đúng 200 IDs duy nhất đã sắp.")
    canonical = b"".join(json_bytes(row) for row in rows)
    if canonical != raw:
        raise ValueError("Corpus serialization không khớp recipe đã ghi.")
    return MetadataCorpus(source_bytes, raw, manifest_bytes, manifest, rows, metadata)


def corpus_index_config(corpus: MetadataCorpus) -> IndexConfig:
    # Cả manifest corpus (recipe/commit/policy) và bytes corpus đều tham gia version.
    binding = digest(corpus.manifest_bytes + b"\0" + corpus.corpus_bytes)
    return IndexConfig(
        model_id=MODEL_ID, model_revision=MODEL_REVISION, dimension=DIMENSION,
        preprocessing_version=PREPROCESSING_VERSION,
        dataset_snapshot=f"{SNAPSHOT}-sha256:{digest(corpus.source_bytes)}",
        index_version=f"issue91-e5-metadata-{binding[:20]}",
    )


def check_e5_encoder(encoder) -> None:
    actual = tuple(getattr(encoder, key, None) for key in (
        "model_id", "revision", "dimension", "preprocessing_version",
        "tokenizer_revision", "max_text_tokens",
    ))
    expected = (MODEL_ID, MODEL_REVISION, DIMENSION, PREPROCESSING_VERSION,
                MODEL_REVISION, MAX_TEXT_TOKENS)
    tokenizer = getattr(encoder, "tokenizer", None)
    if (actual != expected or not getattr(tokenizer, "is_fast", False)
            or getattr(tokenizer, "padding_side", None) != "right"
            or getattr(tokenizer, "truncation_side", None) != "right"):
        raise ValueError("E5 encoder/model/tokenizer/token policy không tương thích.")


class E5IndexManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["e5-metadata-index-manifest-v1"] = "e5-metadata-index-manifest-v1"
    created_at_utc: datetime
    observed_at_utc: datetime
    index_config: dict[str, StrictStr | StrictInt]
    collection: Literal["issue91_e5_metadata"] = "issue91_e5_metadata"
    vector_name: str
    tokenizer_revision: Literal[MODEL_REVISION] = MODEL_REVISION
    max_text_tokens: Literal[512] = 512
    query_prefix: Literal["query: "] = QUERY_PREFIX
    passage_prefix: Literal["passage: "] = PASSAGE_PREFIX
    normalization: Literal["L2"] = "L2"
    similarity: Literal["Cosine"] = "Cosine"
    source_manifest: Literal["source.json"] = "source.json"
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    corpus_file: Literal["corpus.jsonl"] = "corpus.jsonl"
    corpus_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    corpus_manifest: Literal["corpus-manifest.json"] = "corpus-manifest.json"
    corpus_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    corpus_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    recipe_version: str = Field(min_length=1)
    asset_ids: tuple[StrictStr, ...]
    asset_count: Literal[200] = 200
    point_count: Literal[200] = 200
    code_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    working_tree_dirty: StrictBool
    module_sha256: dict[str, str] = Field(min_length=1)
    package_versions: dict[str, str] = Field(min_length=1)

    @field_validator("index_config", mode="before")
    @classmethod
    def valid_config(cls, value):
        if not isinstance(value, dict):
            raise ValueError("index_config phải là object.")
        try:
            return asdict(IndexConfig(**value))
        except (TypeError, ValueError):
            raise ValueError("index_config thiếu trường, sai kiểu hoặc có trường lạ.") from None

    @field_validator("created_at_utc", "observed_at_utc")
    @classmethod
    def utc(cls, value):
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("Timestamp cần UTC.")
        return value

    @field_validator("module_sha256")
    @classmethod
    def module_hashes(cls, value):
        for path, checksum in value.items():
            _portable_path(path)
            if not re.fullmatch(r"[0-9a-f]{64}", checksum):
                raise ValueError("Module hash cần SHA-256.")
        return value

    @model_validator(mode="after")
    def compatible(self) -> Self:
        config = IndexConfig(**self.index_config)
        if (config.model_id, config.model_revision, config.dimension, config.preprocessing_version) != (
            MODEL_ID, MODEL_REVISION, DIMENSION, PREPROCESSING_VERSION,
        ):
            raise ValueError("Index không phải E5 theo pin đã hỗ trợ.")
        if config.dataset_snapshot != f"{SNAPSHOT}-sha256:{self.source_manifest_sha256}":
            raise ValueError("Snapshot không khớp source hash.")
        if self.vector_name != index_vector_name(config):
            raise ValueError("Named vector không khớp cấu hình.")
        if len(self.asset_ids) != 200 or list(self.asset_ids) != sorted(set(self.asset_ids)):
            raise ValueError("Manifest cần đúng 200 IDs duy nhất đã sắp.")
        for aid in self.asset_ids:
            TextSearchHit(asset_id=aid, score=0.0)
        if self.observed_at_utc > self.created_at_utc:
            raise ValueError("Observation không được sau creation.")
        return self

    def make_store(self, client) -> QdrantStore:
        return QdrantStore(client, collection_name=self.collection,
                           config=IndexConfig(**self.index_config))

    def check_encoder(self, encoder) -> None:
        check_e5_encoder(encoder)

    def verify_inputs(self, root: Path) -> MetadataCorpus:
        root = Path(root)
        source = read_member(root, self.source_manifest)
        raw = read_member(root, self.corpus_file)
        manifest_raw = read_member(root, self.corpus_manifest)
        if (digest(source), digest(raw), digest(manifest_raw)) != (
            self.source_manifest_sha256, self.corpus_sha256, self.corpus_manifest_sha256,
        ):
            raise ValueError("Input SHA-256 không khớp index manifest.")
        # Alias tên manifest trong gói index; không tạo/sửa file khi đọc.
        corpus = load_metadata_corpus(
            root, source, expected_source_sha256=self.source_manifest_sha256,
            expected_corpus_sha256=self.corpus_sha256,
            expected_recipe_version=self.recipe_version, manifest_name=self.corpus_manifest,
        )
        if (asdict(corpus_index_config(corpus)) != self.index_config
                or tuple(row["asset_id"] for row in corpus.rows) != self.asset_ids
                or corpus.manifest["source_commit"] != self.corpus_source_commit):
            raise ValueError("Index không khớp corpus/recipe/IDs/provenance.")
        return corpus


def _metadata(corpus: MetadataCorpus, aid: str) -> dict:
    return {**corpus.metadata[aid], "_corpus": {
        "sha256": digest(corpus.corpus_bytes),
        "manifest_sha256": digest(corpus.manifest_bytes),
        "recipe_version": corpus.manifest["recipe_version"],
    }}


def audit_metadata_index(manifest: E5IndexManifest, client, root: Path) -> dict:
    """Chỉ đọc: IDs, payload, vectors và fingerprint của toàn bộ index."""
    corpus = manifest.verify_inputs(root)
    store = manifest.make_store(client)
    store.validate_collection()
    if client.count(manifest.collection, exact=True).count != 200:
        raise ValueError("Index cần đúng 200 points.")
    records, offset = [], None
    while True:
        page, offset = client.scroll(manifest.collection, limit=256, offset=offset,
                                     with_payload=True, with_vectors=True)
        records.extend(page)
        if len(records) > 200 or (offset is not None and not page):
            raise ValueError("Index thay đổi hoặc scroll không hợp lệ.")
        if offset is None:
            break
    ids, serialized = set(), []
    for point in records:
        payload = point.payload or {}
        aid = payload.get("asset_id")
        if not isinstance(aid, str) or aid not in corpus.metadata or aid in ids:
            raise ValueError("Index có ID thiếu/thừa/trùng.")
        ids.add(aid)
        expected = {**_metadata(corpus, aid),
                    "model_version": f"{MODEL_ID}@{MODEL_REVISION}",
                    "index_version": store.config.index_version,
                    "_index": {**asdict(store.config), "distance": "Cosine"}}
        if payload != expected or str(point.id) != str(uuid5(NAMESPACE_URL, f"ai04/asset/{aid}")):
            raise ValueError("Index payload/provenance/point ID không tương thích.")
        if not isinstance(point.vector, dict) or set(point.vector) != {store.vector_name}:
            raise ValueError("Index named vector không tương thích.")
        vector = point.vector[store.vector_name]
        if (len(vector) != DIMENSION or any(not isfinite(x) for x in vector)
                or not isclose(sqrt(sum(x*x for x in vector)), 1.0, rel_tol=0, abs_tol=1e-5)):
            raise ValueError("Index vector sai dimension/finite/L2.")
        serialized.append({"point_id": str(point.id), "payload": payload, "vector": point.vector})
    if ids != set(manifest.asset_ids):
        raise ValueError("Index không đủ candidate IDs.")
    serialized.sort(key=lambda row: row["point_id"])
    return {"point_count": len(records), "asset_count": len(ids),
            "point_payload_vector_sha256": digest(json_bytes(serialized))}


def build_metadata_index(encoder, corpus: MetadataCorpus, output: Path, *,
                         batch_size: int, code_commit: str, working_tree_dirty: bool,
                         module_sha256: dict, package_versions: dict) -> E5IndexManifest:
    """Chỉ tạo gói/storage mới. Lỗi build không để lại manifest thành công."""
    check_e5_encoder(encoder)
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or not 1 <= batch_size <= 200:
        raise ValueError("batch_size cần integer 1–200.")
    output = Path(output)
    if output.exists():
        raise FileExistsError("Output đã tồn tại; chọn thư mục mới.")
    config = corpus_index_config(corpus)
    # Provenance Git/packages do CLI quan sát, không suy ra từ thời gian file.
    provenance = dict(code_commit=code_commit, working_tree_dirty=working_tree_dirty,
                      module_sha256=module_sha256, package_versions=package_versions)
    vectors = encoder.encode_passages([row["passage"] for row in corpus.rows], batch_size=batch_size)
    if len(vectors) != len(corpus.rows):
        raise ValueError("Encoder không trả đủ vectors; không bỏ asset lỗi.")
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in (("source.json", corpus.source_bytes), ("corpus.jsonl", corpus.corpus_bytes),
                      ("corpus-manifest.json", corpus.manifest_bytes)):
        with (output / name).open("xb") as stream:
            stream.write(raw)
    client = QdrantClient(path=str(output / "qdrant"))
    try:
        store = QdrantStore(client, collection_name="issue91_e5_metadata", config=config)
        store.upsert([{"asset_id": row["asset_id"], "metadata": _metadata(corpus, row["asset_id"]),
                       "vector": vector} for row, vector in zip(corpus.rows, vectors, strict=True)])
        observed = datetime.now(timezone.utc)
        manifest = E5IndexManifest(
            created_at_utc=datetime.now(timezone.utc), observed_at_utc=observed,
            index_config=asdict(config), vector_name=store.vector_name,
            source_manifest_sha256=digest(corpus.source_bytes), corpus_sha256=digest(corpus.corpus_bytes),
            corpus_manifest_sha256=digest(corpus.manifest_bytes),
            corpus_source_commit=corpus.manifest["source_commit"], recipe_version=corpus.manifest["recipe_version"],
            asset_ids=tuple(row["asset_id"] for row in corpus.rows), **provenance,
        )
        in_memory_audit = audit_metadata_index(manifest, client, output)
    finally:
        client.close()

    # qdrant-client 1.15 local: RAM chuẩn hóa float32 khi upsert, persistence
    # giữ vector đã submit và load_vectors đọc lại nguyên các giá trị đó.
    # Đối chiếu chính xác persisted data với input, không round hash/nới tolerance.
    expected_records = [{
        "point_id": str(uuid5(NAMESPACE_URL, f"ai04/asset/{row['asset_id']}")),
        "payload": {
            **_metadata(corpus, row["asset_id"]),
            "model_version": f"{MODEL_ID}@{MODEL_REVISION}",
            "index_version": config.index_version,
            "_index": {**asdict(config), "distance": "Cosine"},
        },
        "vector": {store.vector_name: [float(value) for value in vector]},
    } for row, vector in zip(corpus.rows, vectors, strict=True)]
    expected_records.sort(key=lambda row: row["point_id"])
    expected_audit = {"point_count": 200, "asset_count": 200,
                      "point_payload_vector_sha256": digest(json_bytes(expected_records))}
    with closing(QdrantClient(path=str(output / "qdrant"))) as reopened:
        persisted_audit = audit_metadata_index(manifest, reopened, output)
    if persisted_audit != expected_audit:
        raise RuntimeError("Persisted index không khớp chính xác IDs/payload/vectors đã submit.")
    persistence = {
        "policy": "qdrant-local-submitted-vectors-exact-v1",
        "in_memory_after_upsert": in_memory_audit,
        "expected_submitted": expected_audit,
        "persisted_after_reopen": persisted_audit,
    }
    for name, value in (("persistence-audit.json", persistence), ("audit.json", persisted_audit),
                        ("index-manifest.json", manifest.model_dump(mode="json"))):
        with (output / name).open("xb") as stream:
            stream.write(json_bytes(value, pretty=True))
    return manifest


def load_e5_index_manifest(path: Path) -> E5IndexManifest:
    return E5IndexManifest.model_validate_json(Path(path).read_bytes())
