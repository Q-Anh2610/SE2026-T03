"""RRF thuần theo rank cho #91; kiểu nội bộ, chưa phải shared API contract."""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from fractions import Fraction
from hashlib import sha256
import json


CLIP_SOURCE = "clip_text_to_preview"
E5_SOURCE = "e5_text_to_metadata"


@dataclass(frozen=True)
class RRFConfig:
    """Mọi tham số phải được truyền rõ; chưa có cấu hình validation được chọn."""

    rank_constant: int
    clip_candidate_limit: int
    e5_candidate_limit: int
    cutoff: int

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            minimum = 0 if name == "rank_constant" else 1
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise ValueError(f"{name} phải là integer >= {minimum}.")
            if name != "rank_constant" and value > 200:
                raise ValueError(f"{name} không vượt quá candidate snapshot 200 của #91.")

    def parameters(self) -> dict[str, object]:
        return {
            "schema_version": "rrf-config-v1",
            **asdict(self),
            "sources": [CLIP_SOURCE, E5_SOURCE],
            "weights": [1, 1],
            "rank_origin": 1,
            "deduplication": "first_occurrence_then_contiguous_unique_rank",
            "ordering": ["rrf_score_desc", "asset_id_asc"],
            "missing_source_contribution": 0,
        }

    @property
    def config_version(self) -> str:
        encoded = json.dumps(self.parameters(), sort_keys=True, separators=(",", ":"))
        return "rrf-v1-" + sha256(encoded.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class RRFContribution:
    source: str
    rank: int
    contribution: float


@dataclass(frozen=True)
class RRFHit:
    asset_id: str
    score: float
    contributions: tuple[RRFContribution, ...]


@dataclass(frozen=True)
class RRFResult:
    hits: tuple[RRFHit, ...]
    config_version: str


def _unique_candidates(asset_ids: Sequence[str], limit: int) -> list[str]:
    if isinstance(asset_ids, (str, bytes)) or not isinstance(asset_ids, Sequence):
        raise TypeError("Mỗi luồng phải là sequence các asset ID đã xếp hạng.")
    seen: set[str] = set()
    unique: list[str] = []
    for asset_id in asset_ids:
        if (not isinstance(asset_id, str) or not 1 <= len(asset_id) <= 128
                or asset_id != asset_id.strip() or asset_id in {".", ".."}
                or any(char in asset_id for char in "/\\?#%")):
            raise ValueError("asset_id không hợp lệ.")
        if asset_id not in seen:
            seen.add(asset_id)
            unique.append(asset_id)
    return unique[:limit]


def reciprocal_rank_fusion(clip_asset_ids: Sequence[str], e5_asset_ids: Sequence[str],
                           *, config: RRFConfig) -> RRFResult:
    """Tổng 1/(rank_constant + rank), không nhận cosine hoặc vector.

    Caller phải retrieval hai luồng trên cùng candidate snapshot và filters
    trước gọi hàm này. Hàm chỉ fusion các ID; không chứng minh precondition đó.
    Duplicate trong một luồng được gom ở vị trí đầu rồi đánh rank 1..N trước
    candidate limit. Mỗi asset góp tối đa một lần/luồng; thiếu thì góp 0.
    """
    if not isinstance(config, RRFConfig):
        raise TypeError("config phải là RRFConfig.")
    streams = (
        (CLIP_SOURCE, _unique_candidates(clip_asset_ids, config.clip_candidate_limit)),
        (E5_SOURCE, _unique_candidates(e5_asset_ids, config.e5_candidate_limit)),
    )
    scores: dict[str, Fraction] = {}
    provenance: dict[str, list[RRFContribution]] = {}
    for source, asset_ids in streams:
        for rank, asset_id in enumerate(asset_ids, start=1):
            contribution = Fraction(1, config.rank_constant + rank)
            scores[asset_id] = scores.get(asset_id, Fraction(0)) + contribution
            provenance.setdefault(asset_id, []).append(
                RRFContribution(source, rank, float(contribution)))
    # Fraction bảo đảm tie toán học không bị thứ tự cộng float phá vỡ.
    ordered = sorted(scores, key=lambda asset_id: (-scores[asset_id], asset_id))
    return RRFResult(
        hits=tuple(RRFHit(asset_id, float(scores[asset_id]), tuple(provenance[asset_id]))
                   for asset_id in ordered[:config.cutoff]),
        config_version=config.config_version,
    )
