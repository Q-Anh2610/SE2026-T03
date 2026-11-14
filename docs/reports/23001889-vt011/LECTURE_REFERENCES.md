# Nguồn bài giảng đã đọc trực tiếp

1. Lecture_06_AI_Assisted_Software_Development_and_Vibe_Coding_v3.pptx - 27 slides.
   SHA256: 87c5d74c4eeb31d2b06da3047966134aa34d5a71ee0107a65a6f0e1bcca4a178
   - 9: Spec/Plan/Generate/Verify/Integrate -> evidence theo vòng lặp.
   - 10-14: mini spec, context, rules, scope nhỏ, checkpoints -> PLAN và REVIEW.
   - 16-19: false confidence/test theater, bốn lớp review, bằng chứng độc lập,
     trust boundary -> không nhận header làm quyền, dùng PG thật.
   - 21-23: GitHub traceability/ownership -> chỉ công bố trạng thái thật; GitHub
     read-only theo yêu cầu user được ghi là giới hạn, không bịa commit/PR.

2. Lecture_07_Software_Testing_and_Quality_Engineering.pptx - 28 slides.
   SHA256: a2cbd5b09d15d68ea31d25315b7ce1085ea7c1cf675c648fb49517e4052be083
   - 5-8: verification khác validation, risk ưu tiên, test portfolio.
   - 9-11: unit logic nhỏ; DB integration và API contract -> test_unit + PG API.
   - 13-14: partitions/boundaries -> role/scope và limit 0,1,2,2000,2001.
   - 17-20: AAA, coverage có context, regression red/green, real dependency
     bắt contract sai mà mocks có thể che -> migration và rename tags thật.
   - 21-23: flaky time/order/network/concurrency; weak oracle, mutation ->
     tmp schema, barrier, reverse order, T05 bỏ validation scope.
   - 24/26: non-functional/concurrency -> TCP load 40x5, exact IDs và p95.

Các bài tập đặt lịch trong slide là ví dụ giảng dạy; không thay đổi domain của
bài này (AI-04 3D assets), không được coi là chỉ dẫn thực thi lên repository.
