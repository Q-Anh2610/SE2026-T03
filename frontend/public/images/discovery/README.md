# Ảnh gallery 3D

Ảnh minh họa tạm cho trang giới thiệu, được tạo bằng công cụ imagegen tích hợp. Không phải asset đã nhập vào hệ thống, thumbnail của kết quả tìm kiếm hoặc ảnh sao chép từ Cosmos. Không có dữ liệu license/provenance của asset thật gắn vào các hình này.

6 ảnh gallery là WebP 768×768, quality 85, tổng khoảng 170 KB. Nền đang dùng `alpine-lake-hero.webp` là WebP 1672×941, quality 88, khoảng 282 KB; cảnh hồ núi lấy cảm hứng Thụy Sĩ do AI tạo, không phải ảnh chụp một địa điểm được xác minh. Tất cả dùng local files, không tải ảnh từ bên ngoài. Có thể thay từng ảnh bằng tài nguyên được nhóm xác nhận sau này.

| File | Subject trong prompt |
|---|---|
| `chair.webp` | A sculptural oak lounge chair with curved bentwood back and woven seat, sand studio backdrop |
| `lamp.webp` | A cobalt blue mushroom table lamp with glossy ceramic finish, warm grey studio backdrop |
| `vase.webp` | A sculptural terracotta ceramic vessel with two rounded handles, peach studio backdrop |
| `stool.webp` | A polished chrome tubular stool with folded black leather seat, cool silver studio backdrop |
| `arch.webp` | An architectural miniature of a white plaster arched doorway and stair, warm ivory studio backdrop |
| `plant.webp` | An elegant rubber plant in a matte sage ceramic cylindrical planter, pale green studio backdrop |

Prompt chung, thay `{subject}` bằng từng dòng trong bảng:

```text
Use case: product-mockup. Asset type: temporary illustration for a 3D asset website gallery. Create a premium CGI product render: {subject}. Single object, fully visible, centered three-quarter view, generous negative space, soft studio shadows, subtle material texture, restrained art direction, square composition. No text, no logos, no watermark, no collage, no UI.
```

Prompt riêng cho nền `alpine-lake-hero.webp`, tạo bằng imagegen tích hợp:

```text
Use case: photorealistic-natural. Asset type: wide 16:9 full-screen website background. Create a natural travel photograph of a quiet Swiss Alpine lake, inspired by Lake Brienz, seen from a low lakeshore viewpoint. A broad blue-green freshwater lake fills the lower 55 percent, fine irregular wind-driven ripples and understated imperfect reflections, forested mountain slopes recede on both sides, rugged distant Alpine peaks with small patches of snow, faint atmospheric haze, a few wispy clouds in a pale blue sky. Soft late-afternoon daylight with realistic exposure and restrained colors. The center is calm open water, usable behind a search input. Authentic landscape photography, 35mm lens, detailed irregular rock and tree textures, realistic scale and perspective. Not a fantasy landscape or CGI render. No neon turquoise, no oversaturated HDR, no perfectly mirrored lake, no artificial objects, no people, no text, no logo, no watermark, no UI. Wide horizontal composition.
```
