"""Giải thích tín hiệu baseline đã dùng; không suy diễn thuộc tính hình học/độ chính xác."""

CLIP_EXPLANATIONS = {
    "clip_text_to_preview": (
        "CLIP so khớp văn bản truy vấn với ảnh preview; xếp hạng theo cosine giảm dần. "
        "Điểm cosine không phải xác suất hay phần trăm chính xác."
    ),
    "clip_image_to_preview": (
        "CLIP so khớp ảnh truy vấn với ảnh preview; xếp hạng theo cosine giảm dần. "
        "Điểm cosine không phải xác suất hay phần trăm chính xác."
    ),
}


def clip_explanation(retrieval_source: str) -> str:
    try:
        return CLIP_EXPLANATIONS[retrieval_source]
    except KeyError:
        # Không gán lời giải thích CLIP cho nguồn mới chưa được tích hợp.
        raise ValueError("Unsupported explanation retrieval source.") from None
