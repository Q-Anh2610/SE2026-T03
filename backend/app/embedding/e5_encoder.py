"""E5 query/passage encoder thử nghiệm #91; không nạp weights khi import."""

from collections.abc import Sequence

import torch
from transformers import AutoModel, AutoTokenizer


MODEL_ID = "intfloat/multilingual-e5-small"
MODEL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
DIMENSION = 384
MAX_TEXT_TOKENS = 512
QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "
PREPROCESSING_VERSION = "e5-fast-right-truncate512-mask-mean-fp32-l2-v1"


class E5Encoder:
    """Caller tạo một instance rồi dùng lại; mặc định chỉ đọc cache local.

    encode_passages nhận nội dung passage chưa có prefix. Việc chọn/ghép các
    trường metadata thuộc corpus recipe riêng, chưa được quyết định ở đây.
    """

    def __init__(self, *, device: str = "cpu", local_files_only: bool = True):
        if not isinstance(local_files_only, bool):
            raise ValueError("local_files_only phải là boolean.")
        self.model_id = MODEL_ID
        self.revision = MODEL_REVISION
        self.tokenizer_revision = MODEL_REVISION
        self.preprocessing_version = PREPROCESSING_VERSION
        self.dimension = DIMENSION
        self.max_text_tokens = MAX_TEXT_TOKENS
        self.device = torch.device(device)
        self.tokenizer = AutoTokenizer.from_pretrained(
            MODEL_ID, revision=MODEL_REVISION, use_fast=True,
            padding_side="right", truncation_side="right",
            local_files_only=local_files_only,
        )
        if not self.tokenizer.is_fast:
            raise ValueError("E5 preprocessing yêu cầu fast tokenizer đã pin.")
        self.model = AutoModel.from_pretrained(
            MODEL_ID, revision=MODEL_REVISION, use_safetensors=True,
            local_files_only=local_files_only,
        )
        if (self.model.config.hidden_size != DIMENSION
                or self.model.config.max_position_embeddings < MAX_TEXT_TOKENS):
            raise ValueError("E5 model config không khớp dimension/token policy.")
        self.model.to(self.device)
        self.model.eval()

    def encode_text(self, query: str) -> list[float]:
        """Query cùng giới hạn 1–500 ký tự sau trim của text search hiện có."""
        if not isinstance(query, str):
            raise TypeError("query phải là chuỗi.")
        query = query.strip()
        if not 1 <= len(query) <= 500:
            raise ValueError("query sau trim phải có từ 1 đến 500 ký tự.")
        return self._encode([query], prefix=QUERY_PREFIX, batch_size=1)[0]

    def encode_passages(self, passages: Sequence[str], *, batch_size: int = 32
                        ) -> list[list[float]]:
        """Batch nội dung không rỗng; không bịa text thay metadata thiếu."""
        if isinstance(passages, (str, bytes)) or not isinstance(passages, Sequence):
            raise TypeError("passages phải là sequence các chuỗi.")
        if any(not isinstance(passage, str) for passage in passages):
            raise TypeError("Mỗi passage phải là chuỗi.")
        cleaned = [passage.strip() for passage in passages]
        if any(not passage for passage in cleaned):
            raise ValueError("Passage rỗng cần được xử lý bằng corpus recipe.")
        return self._encode(cleaned, prefix=PASSAGE_PREFIX, batch_size=batch_size)

    @torch.inference_mode()
    def _encode(self, texts: Sequence[str], *, prefix: str, batch_size: int
                ) -> list[list[float]]:
        if (isinstance(batch_size, bool) or not isinstance(batch_size, int)
                or batch_size < 1):
            raise ValueError("batch_size phải là số nguyên dương.")
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = [prefix + text for text in texts[start:start + batch_size]]
            inputs = self.tokenizer(
                batch, max_length=MAX_TEXT_TOKENS, padding=True,
                truncation=True, return_tensors="pt",
            ).to(self.device)
            hidden = self.model(**inputs).last_hidden_state.float()
            mask = inputs["attention_mask"]
            if (hidden.ndim != 3 or hidden.shape[0] != len(batch)
                    or hidden.shape[2] != DIMENSION
                    or tuple(mask.shape) != tuple(hidden.shape[:2])
                    or not torch.all((mask == 0) | (mask == 1))
                    or torch.any(mask.sum(dim=1) <= 0)):
                raise RuntimeError("E5 hidden state hoặc attention mask sai shape/giá trị.")
            # masked_fill loại cả NaN ở vị trí padding, không dùng hidden * mask.
            unpadded = hidden.masked_fill(~mask[..., None].bool(), 0.0)
            features = unpadded.sum(dim=1) / mask.sum(dim=1)[:, None]
            norms = torch.linalg.vector_norm(features, dim=1, keepdim=True)
            if (not torch.isfinite(features).all() or not torch.isfinite(norms).all()
                    or torch.any(norms <= 0)):
                raise RuntimeError("E5 embedding chứa vector không hợp lệ.")
            vectors.extend((features / norms).cpu().tolist())
        return vectors
