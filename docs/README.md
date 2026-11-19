# Tài liệu dự án

- `requirements/`: yêu cầu, use cases và acceptance criteria.
- `architecture/`: kiến trúc và luồng dữ liệu.
- `contracts/`: API/schema dùng chung giữa backend, frontend và evaluation.
- `adr/`: quyết định kỹ thuật đã chốt, có lý do và tradeoff.
- `guides/`: hướng dẫn dựng/chạy/vận hành dựa trên lệnh thực tế.
- `evaluation/`: báo cáo thí nghiệm có kết quả thật.
- [Benchmark W2/W3](evaluation/home-interior-text-v2-keyword-baseline.md): trạng thái bộ query/qrels đã khóa, phép đo keyword diagnostic và phần CLIP text retrieval còn chờ trên snapshot nội thất.
- [Báo cáo so sánh ban đầu W5 — #105](evaluation/issue105-w5-initial-comparison.md): CLIP/E5/RRF trên validation đã bàn giao ở #91, giới hạn ảnh và checklist kiểm chứng; xem [các bước thực hiện](guides/issue105-w5-evaluation-report.md).
- [ADR W6 — cấu hình CLIP/E5 RRF k=20](adr/0001-w6-retrieval-config.md): lựa chọn từ validation, latency tradeoff và pins; [kiểm tra/bàn giao trước test](guides/issue114-w6-freeze.md).
- [Quy trình gán nhãn benchmark](evaluation/benchmark-labeling.md): tiêu chí relevance, split và cách khóa benchmark.
- [Tiến độ theo tuần](weekly-progress.md): phần đã hoàn thành và việc chuyển tiếp giữa các tuần.
- `contributions.md`: ghi đóng góp thực tế khi có; không tạo thành tích mẫu.
- `BRANCHING.md`: quy trình Git.
- `STRUCTURE.md`: cấu trúc repository.

Benchmark `home-interior-text-v2` đã khóa 70 query tiếng Anh và 14.000 qrels trên snapshot `home-interior-clear-200-v3`. Phép đo keyword trong báo cáo benchmark là diagnostic, không phải kết quả CLIP text retrieval. Phần retrieval thật và ranked results đủ 70 query vẫn đang chờ, được chuyển tiếp sang W3 và theo dõi tại Issue #46.
