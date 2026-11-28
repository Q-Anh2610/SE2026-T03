# Docker trên môi trường sạch — W7 / Issue #148

## Phạm vi

Owner: Đoàn Thị Minh Khuê. Stack local gồm frontend nginx/React, FastAPI,
PostgreSQL 17, Qdrant 1.15.1 và container migration chạy một lần. Không thay
API/schema/model/index. Backend dùng PyTorch `2.8.0+cpu`, cùng dòng phiên bản
`2.8.0` đã pin; chỉ image CPU loại dependencies NVIDIA/triton khỏi requirements
tạm khi build. Lockfile host và manifest/config W6 giữ nguyên. `pip check` phải đạt.

Metadata package của image là `2.8.0+cpu`, khác chuỗi pin nghiêm ngặt `2.8.0`
trong protocol #135. Không dùng image hạ tầng này làm bằng chứng đã qua gate
rebuild/benchmark đó; môi trường và binding đánh giá cần được đối chiếu riêng.

Frontend dùng Node 22.14.0 (đáp ứng engine của dependencies đã khóa), `npm ci` theo lockfile, build production rồi phục vụ
qua nginx 1.28. Build context chỉ cho phép source/public/config cần thiết;
không COPY `.env`, dependencies host hoặc artifact dữ liệu vào image.

## Checklist máy sạch

1. Dùng checkout riêng của branch/commit cần kiểm chứng; ghi commit và dirty status.
2. Docker Engine Linux containers chạy được; Docker Compose v2 hỗ trợ `up --wait`.
3. Có mạng cho images và package registry ở lần build đầu; không cần tải weights.
4. Tạo `.env` theo README, đổi password mẫu; không dùng lại `.env`/volumes của project khác.
5. Chọn tên project mới, ví dụ `issue148-clean`; kiểm tra cổng trước khi chạy.

Các lệnh dưới chạy từ repo root. Dùng cùng `-p` và danh sách `-f` cho toàn lượt:

```powershell
docker compose -p issue148-clean -f docker-compose.yml config --quiet
docker compose -p issue148-clean -f docker-compose.yml up --build -d --wait --wait-timeout 180
docker compose -p issue148-clean -f docker-compose.yml ps --all
powershell -NoProfile -File scripts/verify_docker_stack.ps1 -ProjectName issue148-clean
```

Script không dựng/xóa dữ liệu. Nó kiểm bốn dịch vụ healthy, migration exit 0 và
revision ở head, HTML UI, liveness trực tiếp/qua nginx, list assets đọc PostgreSQL
qua nginx và Qdrant `/readyz`/collections. Report JSON mới nằm trong
`data/runtime/issue148/` (ngoài Git); lỗi trả exit khác 0 và report status failed.
Không ghi credentials hoặc nội dung `.env` trong report. `config --quiet` tránh
in cấu hình đã nội suy có chứa mật khẩu.

Không seed tự động: DB mới rỗng là hợp lệ. Seed fixture nếu muốn xem UI là thao tác
riêng theo [guide DB](database.md), không phải dữ liệu thật hay chứng cứ retrieval.

Chạy `up` và script lần hai để kiểm migration chạy lại an toàn, dịch vụ vẫn ready.
Ghi OS, Docker/Compose versions, commands/exit codes, revision, project, commit,
dirty status và checks thực tế. Report từ code local phải giữ dirty=true; không gán
commit tương lai cho lượt chạy trước. Checkout sạch không đồng nghĩa máy vật lý mới;
phải ghi rõ mức cô lập, images/dependency cache đã tái sử dụng và giới hạn còn lại.

## Chế độ semantic search thật — tùy chọn có đầu vào

Compose mặc định giữ các nguồn của `.env.example`: assets từ DB, search/feedback
mock phát triển. Không dùng kết quả mock hoặc Qdrant rỗng để nghiệm thu #149/#150.
Muốn chạy service, owner phải chuẩn bị trước:

- Metadata PostgreSQL và collection **server Qdrant** khớp manifest; không ghi
  đè active/reference index hoặc tự đổi snapshot/config/model đã khóa.
- Handoff root đã kiểm checksum với text/image manifests đúng baseline API hiện có.
- Cache Hugging Face có CLIP đúng revision; quyền đọc cho UID backend 10001.
- Review mapping/binding nếu dùng index rebuild của #135. API hiện tại không tự
  chuyển sang E5/RRF chỉ vì cấu hình W6 đã khóa.

Qdrant local storage SQLite trong gói #114/#135 **không phải** storage/snapshot
của Qdrant server: không mount nó vào volume server và không tự chuyển định dạng.
Việc tạo/khôi phục collection phải theo pipeline và hướng dẫn owner đã review.

Bổ sung vào `.env` local theo paths thực tế:

```dotenv
SEARCH_HANDOFF_ROOT=C:/path/to/checked-handoff-root
SEARCH_MODEL_CACHE=C:/path/to/huggingface
SEARCH_TEXT_MANIFEST=/handoff/path/to/text-index-manifest.json
SEARCH_IMAGE_MANIFEST=/handoff/path/to/image-index-manifest.json
```

Đây là placeholders, cần thay bằng artifact thật; manifests dùng **đường dẫn trong
container**. Root/cache phải tồn tại; bind không tự tạo thư mục. Handoff/cache chỉ
đọc, `HF_HUB_OFFLINE=1` và `TRANSFORMERS_OFFLINE=1`; không tự tải weights. Xóa các
biến `APP_TEXT_QDRANT_LOCAL_PATH`/`APP_IMAGE_QDRANT_LOCAL_PATH` kiểu host khỏi `.env`
nếu đã cấu hình: overlay này dùng server `http://qdrant:6333`. Giữ `DATABASE_URL`
trống hoặc trỏ đúng `postgres:5432`, không trỏ DB host/chung.

```powershell
docker compose -p issue148-clean -f docker-compose.yml -f docker-compose.search.yml config --quiet
docker compose -p issue148-clean -f docker-compose.yml -f docker-compose.search.yml up --build -d --wait --wait-timeout 180
./scripts/verify_docker_stack.ps1 -ProjectName issue148-clean -ComposeFiles docker-compose.yml,docker-compose.search.yml
```

Overlay tắt mock, chọn text/image service và feedback database; không đổi default
API hay frozen config trong repo. Thiếu/mismatch cache/index có thể vẫn liveness
200 nhưng search trả 503 theo contract. Cần smoke retrieval thật riêng tại #149,
ghi versions/nguồn và kiểm request thực sự qua model/index; hạ tầng healthy chưa đủ.
Không công bố overlay đã chạy model thật nếu chưa có đủ đầu vào/evidence.

## Lỗi thường gặp

- Không kết nối được Docker: mở Docker Desktop/Engine, chờ Linux engine ready.
- Cổng bị chiếm: sửa bốn biến port trong `.env`; giữ host bindings `127.0.0.1`.
- Migration fail: xem `logs migrate`, kiểm DB URL/credentials, giữ nguyên volume;
  không `stamp`, không xóa volume để che lỗi. Backend/frontend bị chặn là đúng.
- Password đã đổi sau khi khởi tạo volume: DB không tự cập nhật password; phối hợp
  quản trị DB hoặc dùng project mới cho lượt sạch, không xóa DB đang dùng.
- UI/API lỗi 502: kiểm backend health/logs, khởi động lại frontend sau khi backend
  được recreate nếu nginx còn giữ IP upstream cũ.
- Search service 503: đối chiếu input/cache/collection/manifest theo guide retrieval;
  không bật mock để ghi thành công. Qdrant ready không xác nhận collection có dữ liệu.

Chỉ chia sẻ logs sau khi kiểm thông tin nhạy cảm; không gửi `docker compose config`
đã resolve, `.env`, output `env` hoặc toàn bộ inspect container.

### Script PowerShell bị chặn trên Windows

Nếu Windows báo `PSSecurityException` hoặc `running scripts is disabled` trước
khi verifier chạy, mở PowerShell tại repo root và dùng checkout đã kiểm tra:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_docker_stack.ps1 -ProjectName issue148-clean
```

Thay `issue148-clean` bằng tên project của lượt kiểm chứng. `-ExecutionPolicy Bypass`
chỉ áp dụng cho tiến trình PowerShell con này, không đổi policy lâu dài của máy;
không cần chạy `Set-ExecutionPolicy` cho User/Machine. Verifier vẫn kiểm đầy đủ
các dịch vụ và trả exit khác 0 khi lỗi. Lỗi policy xảy ra trước khi script thực thi
chưa tạo bằng chứng smoke; sau khi chạy lại cần giữ report và kết quả thật.

Chi đã dùng cách gọi này ở cả hai lượt [kiểm chứng độc lập](https://github.com/Q-Anh2610/SE2026-T03/issues/148#issuecomment-7224043872).
Với PowerShell 7/CI hoặc máy cho phép chạy script, giữ lệnh gọi ban đầu.

## Dừng và dọn

Giữ dữ liệu (mặc định khi bàn giao):

```powershell
docker compose -p issue148-clean -f docker-compose.yml down
```

Lệnh không xóa named volumes. Không xóa images/cache/model/artifact của người khác.
Chỉ khi **tự xác nhận** `issue148-clean` là project test riêng, không còn dữ liệu cần
giữ và đã lưu evidence, mới chạy lệnh xóa cả volumes của đúng project này:

```powershell
docker compose -p issue148-clean -f docker-compose.yml down --volumes
```

Đây là lệnh có mất dữ liệu; không dùng với project phát triển/chung. Bind handoff/cache
không bị xóa bởi Compose. Không tự đóng #148 hoặc ghi milestone hoàn thành trước
khi có bằng chứng máy sạch, review/tích hợp phù hợp.
