# Evaluation — TV5 phối hợp TV3

- `metrics/`: công thức metric thuần và có tests bằng ví dụ biết đáp án.
- `configs/`: cấu hình benchmark có phiên bản.
- `results/`: kết quả nhỏ, có provenance, versions/configs/seed và mô tả máy.
- `tests/`: kiểm thử metric và runner khi được triển khai.

Runner/CLI sẽ được thêm khi có nhiệm vụ. Dùng cùng search implementation/API của sản phẩm; không sao chép thuật toán retrieval vào đây. Query/nhãn nằm tại `data/benchmark/`; báo cáo diễn giải nằm trong `docs/evaluation/`. Không commit model, index hay bulk dữ liệu vào `results/`.
