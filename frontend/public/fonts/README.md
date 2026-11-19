# Font giao diện

Font tự host dạng WOFF2 cho Latin, Latin mở rộng và tiếng Việt. Font chạy local, không cần tải từ CDN.

- Be Vietnam Pro: weights 100/300/400/500/700/900; https://github.com/google/fonts/tree/main/ofl/bevietnampro
- Noto Serif: Thin Italic 100; https://github.com/google/fonts/tree/main/ofl/notoserif
- Google Sans Flex v23: variable weight; subsets Latin/Latin mở rộng/tiếng Việt từ `@fontsource-variable/google-sans-flex@5.3.2`; metadata nguồn `https://github.com/google/fonts`.

Giữ license SIL Open Font License trong các file OFL kèm theo, gồm `Google-Sans-Flex-OFL.txt`. Không sửa glyph/font. Định nghĩa `font-face` và `unicode-range` nằm tại `src/app/fonts.css`.
