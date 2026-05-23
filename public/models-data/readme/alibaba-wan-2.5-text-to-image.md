# Alibaba WAN 2.5 Text-to-Image

**Alibaba WAN 2.5 Text-to-Image** là mô hình sinh ảnh chất lượng cao thế hệ mới của Alibaba Cloud (Tongyi/Qwen team), cung cấp qua nền tảng DashScope. Tối ưu cho prompt-first workflow, hỗ trợ đa tỷ lệ và đa phong cách.

## Điểm nổi bật

- **Prompt-first generation:** Sinh ảnh từ mô tả văn bản tự nhiên, không cần ảnh tham chiếu.
- **Đa tỷ lệ khung hình:** Hỗ trợ `1:1`, `16:9`, `9:16`, `4:3`, `3:4` và các tỷ lệ phổ biến khác.
- **Độ phân giải linh hoạt:** 1024px đến 2048px theo cạnh dài nhất.
- **Phong cách đa dạng:** Photorealistic, anime, oil painting, 3D render, vector art.
- **Deterministic reruns:** Tái lập kết quả bằng seed cố định.

## Dành cho ai

- Designer cần tạo concept art nhanh
- Marketer làm ảnh quảng cáo / social media
- Developer prototype giao diện sản phẩm
- Content creator làm thumbnail / cover

## Cách dùng

1. **Mô tả chi tiết** đối tượng, bối cảnh, ánh sáng, phong cách trong prompt.
2. Chọn **tỷ lệ khung hình** phù hợp (16:9 cho banner, 1:1 cho social).
3. Tinh chỉnh **seed** để giữ phong cách nhất quán giữa các lần chạy.
4. Dùng **negative prompt** loại bỏ artifact không mong muốn.

## Mẹo prompt

- Ngôn ngữ tả thực giúp ảnh chân thực hơn
- Chỉ định lens (50mm, 85mm) cho ảnh photorealistic
- Mention từ khoá phong cách (cinematic, studio lighting, golden hour)
- Tránh chữ thừa lặp lại — câu ngắn rõ ràng tốt hơn câu dài lủng củng
