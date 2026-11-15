# Admin Reindex UI — Issue #104

Phần local trên nhánh `feat/104-admin-reindex-ui`, kế thừa jobs/status #103 / PR
#121. Contract tham chiếu là backend #117 / PR #122 tại `7a43d79`:
[reindex-w5.md trên nhánh backend](https://github.com/Q-Anh2610/SE2026-T03/blob/7a43d79a9af1545c7a9ebd4900671c311bec420e/docs/contracts/reindex-w5.md).
Không sao chép hoặc tự thay contract backend. Khi backend được bàn giao ở commit
mới, đối chiếu thay đổi trước khi nghiệm thu.

## Hành vi

- Mở `/#admin-status`, nhập khóa quản trị; thao tác reindex chỉ được bật sau khi
  tải danh sách thành công. Khóa dùng lại trong state, không vào URL/storage/Vite.
- Chọn **Yêu cầu reindex**, đọc phạm vi rồi **Xác nhận reindex** hoặc hủy. POST
  chỉ gửi `request_id` UUID và profile `clip-candidate200-v1`, kèm `X-Admin-Key`.
- Loading không cho bấm gửi lần nữa. 202 là đã nhận job, chưa xác nhận hoàn thành;
  200/reused là job cũ, kể cả failed, không có nghĩa chạy lại operation.
- Timeout/mất response/JSON không hợp lệ: không báo thành công; **Gửi lại cùng
  yêu cầu** giữ UUID. Không tự retry POST. 409 dẫn sang danh sách jobs/status;
  không tự gửi lặp để chờ tài nguyên.
- **Chuẩn bị lượt mới** sau phản hồi hợp lệ tạo UUID mới và cần xác nhận lại.
  Backend vẫn chặn nếu tài nguyên đang bận.
- **Theo dõi job này** mở `/#admin-status/job/<UUID>`, giữ phiên khi chuyển trong
  khu vực Admin. Mở bookmark/tải lại trang yêu cầu nhập khóa lại.
- Chi tiết gọi GET cùng job ID mỗi 3 giây, không có request chồng nhau. Dừng ở
  succeeded/failed hoặc lỗi HTTP; retry đọc không chạy lại operation. Rời job,
  rời Admin hoặc reset phiên hủy GET và dọn timer, bỏ kết quả đến muộn.
- Progress null là chưa xác định. Result hiển thị index/model/snapshot, số đếm,
  tham chiếu opaque, hash và kiểm chứng search. Job cũ thiếu trường mới hoặc có
  null vẫn được chấp nhận; trường mới có giá trị sai kiểu bị từ chối.
- Dựng index riêng chưa chuyển active index. Không gửi path/URL/model/command tùy
  ý. Rời trang hoặc reset khóa không hủy job backend đã nhận; UUID chỉ giữ trong
  bộ nhớ của phiên hiện tại. Nếu rời phiên khi POST chưa rõ kết quả, kiểm tra
  lịch sử jobs trước khi yêu cầu lượt mới.

Danh sách lịch sử vẫn tải lại thủ công, không tự polling toàn bộ danh sách.
Thay đổi route trong App cần owner UI chung review. Không thay API, schema,
index, dependencies hoặc lockfile trong #104.

## Kiểm tra local và E2E giả lập

Các kết quả sau do người dùng chạy và cung cấp output ngày 15/11/2026:

| Kiểm tra | Kết quả |
|---|---|
| Unit/component/contract toàn frontend | 580/580 tests, 26 files đạt |
| Coverage | Statements 99,35%, branches 98,55%, functions/lines 100%; ngưỡng 95% từng file đạt |
| Lint | Đạt |
| Typecheck/build | `tsc --noEmit && vite build` đạt; Vite 7.3.7 |
| E2E đầy đủ trước sửa fixture | 45/46 đạt; một ca Admin desktop lỗi do fixture chuyển trạng thái theo số GET, kể cả GET đã hủy |
| E2E Admin sau sửa fixture | 10/10 đạt trên api-desktop và production-mobile, 22,5 giây; build trước E2E đạt |

Fixture nay giữ running đến khi test đã xác nhận progress null và không có
progressbar, sau đó mới cho chuyển succeeded. Không đổi code sản phẩm hoặc
tăng timeout để bỏ qua lỗi này. Các ca ngoài Admin đã đạt ở lượt đầy đủ trước;
chưa có lượt chạy toàn bộ 46 ca sau sửa fixture.

E2E dùng HTTP interception, tách khỏi smoke backend thật bên dưới. Các lệnh tái
lập từ thư mục frontend:

```powershell
rtk proxy npm.cmd test -- src/features/admin src/app/App.test.tsx
rtk proxy npm.cmd run typecheck
rtk proxy npm.cmd run lint
rtk proxy npm.cmd run test:coverage
$env:VITE_API_BASE_URL = ''
rtk proxy npm.cmd run test:e2e
```

E2E build trước khi chạy; `admin.spec.ts` được cấu hình cho API desktop và
production mobile. Ca mới kiểm confirmation/cancel, mất response và UUID replay,
điều hướng giữ phiên, polling running→succeeded, 409 và failed replay, reset khóa
và không lưu khóa. Đây là HTTP interception, không phải smoke backend thật.
Giữ ngưỡng coverage 95% từng file theo repo; bổ sung tests nếu còn nhánh thiếu.

## Smoke UI với backend thật

Lượt 12:57 ngày 15/11/2026: người dùng cung cấp ảnh UI job
`b1125421-c1c3-48b3-96fb-2e97d09bbe65` thành công, 200/200 asset, exit_code=0.
Artifact local của đúng job ghi 200 assets/points, pinned CLIP, snapshot/hash
đúng contract, search-check passed và versions khớp. Agent đã tính lại hash
source/ready và đối chiếu. Xem [bằng chứng smoke thật](../evidence/issue104-admin-reindex.md)
cho môi trường, SHA, kết quả và các trường hợp chưa smoke. Người dùng đã đối
chiếu PostgreSQL: revision `0004`, cùng job succeeded, 200/200, result/hash khớp
artifact, search_verified=true, error=null. Ảnh UI xác nhận khóa sai bị từ chối
và nhập lại khóa đúng xem được cùng job cũ. Không dùng kết quả này thay tests
lỗi/replay/409 riêng hoặc benchmark.

Tại thời điểm kiểm tra GitHub sau lượt E2E ban đầu ngày 15/11/2026, PR #122 còn Draft tại `7a43d79`,
5 checks đạt, chưa approve/merge. Chi và Huyền đã xác nhận bàn giao qua comment
riêng (runner/model/config và frozen input/cache); Khuê đã tiếp nhận POST contract.
Các xác nhận này không thay approve PR hoặc smoke UI. Lượt smoke ban đầu dùng
checkout riêng cho backend. PR #122 sau đó đã merge vào develop và được tích hợp
vào nhánh #104 như phần đối chiếu bên dưới.

Trước smoke cần owner bàn giao SHA/API origin, CORS, PostgreSQL test/local,
migration `0004`, khóa admin, `APP_REINDEX_ENABLED=true`, preview cache hợp lệ,
model pinned có sẵn và output root riêng. Backend hiện có giới hạn Docker;
dùng môi trường Uvicorn đã chuẩn bị theo hướng dẫn #117. Không tự tải model,
mở quyền ghi index chung hoặc thay active index để kiểm thử UI.

1. Cấu hình `VITE_API_BASE_URL` tới backend được bàn giao, chạy `dev:api`; nhập
   khóa lúc chạy. Không chụp/in giá trị khóa trong bằng chứng.
2. Hủy xác nhận: không có POST. Xác nhận: POST đúng body/header, loading rồi
   202/job ID. Theo dõi link, đối chiếu UUID và trạng thái với GET detail/DB.
3. Quan sát queued/running với progress null đến terminal. Nếu succeeded, đối
   chiếu index/model/snapshot/count/search_verified với report backend; ghi rõ
   index đang phục vụ chưa được chuyển.
4. Kiểm tra khóa sai, API tắt/chưa sẵn sàng và lỗi kết nối: không báo đã nhận
   job. Kiểm tra replay/409 trong môi trường riêng đã thống nhất với owner;
   không cố chạy nhiều lượt hoặc sửa cache của người khác để tạo lỗi.
5. Ghi thời điểm, SHA frontend/backend, UUID job, status, versions/count và kết
   quả quan sát. Không dùng fixture hoặc kết quả smoke CLI #117 thay smoke UI.

## Đối chiếu sau tích hợp backend

Người dùng đã fast-forward nhánh #104 từ `ff77f0a` lên `89c2ba6`, gồm merge PR
#122 tại `66d60f8` và backend `7a43d79`; không có conflict. Agent so sánh byte
giữa checkout đã tích hợp và worktree backend đã smoke: hai contracts
reindex/jobs-status, API reindex, hai schemas reindex/jobs, service reindex,
main/config/model job và script prepare_text_search_index đều giống nhau.
Không có thay đổi contract/runner cần Chi/Huyền xác nhận lại ở bước này.

Bằng chứng smoke 200/200 trước đó dùng đúng nội dung backend đã đối chiếu này.
Người dùng chạy hồi quy sau merge ngày 15/11/2026 lúc 23:03: Admin/App đạt
225/225 tests trên 11 files; build/typecheck đạt (Vite 7.3.7); backend unit
reindex API/builder, jobs API và OpenAPI đạt 38/38 tests (13,16 giây).
Sau khi chuyển backend sang checkout đã tích hợp, UI báo lỗi tải job do PostgreSQL
đang dừng. Người dùng khởi động lại DB, xác nhận container `healthy` và cung cấp ảnh
UI tải lại đúng job cũ: succeeded, 100%, 200/200, exit_code=0 cùng index/model/
snapshot/hash đã đối chiếu. Kiểm tra này xác nhận đọc lại dữ liệu đã lưu và phục hồi
sau gián đoạn DB; không tạo POST/reindex mới hoặc chuyển active index.

## Checklist bàn giao

- [x] Unit/component/contract tests và hồi quy Admin/App đã chạy đạt (580 tests).
- [x] Typecheck/lint/build/coverage đạt; E2E desktop/mobile đạt (10/10 Admin sau sửa fixture; các ca ngoài Admin đạt ở lượt trước).
- [x] Đối chiếu contract `7a43d79` và các comment xác nhận của Chi/Huyền/Khuê trên PR #122; nếu backend đổi commit cần đối chiếu lại.
- [x] Smoke UI với backend thật được ghi riêng, có SHA/job ID/kết quả; đối chiếu DB/artifact và xác thực khóa sai/đúng.
- [x] Draft PR [#123](https://github.com/Q-Anh2610/SE2026-T03/pull/123) vào develop; lượt CI 5/5 trước tích hợp đã được quan sát.
- [x] Đọc lại job qua backend từ checkout đã tích hợp và phục hồi sau gián đoạn PostgreSQL.
- [ ] Xác minh CI trên commit hiện tại, reviewer khác approve và merge theo quyền.

Code/tests/docs ban đầu đã commit/push tại `ff77f0a`, Draft PR #123 vào develop;
sau đó nhánh đã đồng bộ `89c2ba6` như trên. Ghi nhận đối chiếu sau tích hợp này
là thay đổi tài liệu local tiếp theo, chưa commit. Review và nghiệm thu tích hợp
cuối còn riêng; không tự đóng Issue.
