"""Smoke CLIP text retrieval chỉ đọc; chạy từ gốc repo bằng Python backend."""

from pathlib import Path
import os
import sys


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
# Chỉ ảnh hưởng tiến trình smoke này; Qdrant localhost vẫn được truy cập.
os.environ["HF_HUB_OFFLINE"] = "1"

from app.search.smoke import main


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Không in URL, paths input hoặc exception gốc có thể chứa secrets.
        print(f"Smoke could not finish: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
