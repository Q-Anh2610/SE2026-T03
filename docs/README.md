# Tài liệu dự án

- `requirements/`: yêu cầu, use cases và acceptance criteria.
- `architecture/`: kiến trúc và luồng dữ liệu.
- `contracts/`: API/schema dùng chung giữa backend, frontend và evaluation.
- `adr/`: quyết định kỹ thuật đã chốt, có lý do và tradeoff.
- `guides/`: hướng dẫn dựng/chạy/vận hành dựa trên lệnh thực tế.
- `evaluation/`: báo cáo thí nghiệm có kết quả thật.
- [Benchmark W2/W3](evaluation/home-interior-text-v2-keyword-baseline.md): trạng thái bộ query/qrels đã khóa, phép đo keyword diagnostic và phần CLIP text retrieval còn chờ trên snapshot nội thất.
- [Quy trình gán nhãn benchmark](evaluation/benchmark-labeling.md): tiêu chí relevance, split và cách khóa benchmark.
- [Tiến độ theo tuần](weekly-progress.md): phần đã hoàn thành và việc chuyển tiếp giữa các tuần.
- `contributions.md`: ghi đóng góp thực tế khi có; không tạo thành tích mẫu.
- `BRANCHING.md`: quy trình Git.
- `STRUCTURE.md`: cấu trúc repository.

Benchmark `home-interior-text-v2` đã khóa 70 query tiếng Anh và 14.000 qrels trên snapshot `home-interior-clear-200-v3`. Phép đo keyword trong báo cáo benchmark là diagnostic, không phải kết quả CLIP text retrieval. Phần retrieval thật và ranked results đủ 70 query vẫn đang chờ, được chuyển tiếp sang W3 và theo dõi tại Issue #46.
