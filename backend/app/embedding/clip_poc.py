import time
import requests
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

# 1. Khai báo model baseline theo đúng tiêu chí nghiệm thu
model_id = "openai/clip-vit-base-patch32"
print(f"Đang tải model {model_id}...")

# Tải model và bộ tiền xử lý
model = CLIPModel.from_pretrained(model_id)
processor = CLIPProcessor.from_pretrained(model_id)

# 2. Danh sách các URL ảnh có sẵn trên mạng (Mock data online)
image_urls = [
    "https://images.unsplash.com/photo-1593642632823-8f785ba67e45?w=500", # Ảnh bàn làm việc
    "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=500", # Ảnh con mèo
    "https://images.unsplash.com/photo-1494438639946-1ebd1d20bf85?w=500"  # Ảnh ghế sofa
]
# Bạn có thể copy paste thêm các URL khác vào danh sách này để đủ 20-50 ảnh theo yêu cầu Issue

print(f"Bắt đầu trích xuất đặc trưng cho {len(image_urls)} ảnh từ Internet...")

# 3. Bắt đầu đo thời gian chạy
start_time = time.time()

for idx, url in enumerate(image_urls):
    try:
        # Tải ảnh từ URL trực tiếp vào bộ nhớ, không lưu file ra máy
        response = requests.get(url, stream=True)
        response.raise_for_status()
        image = Image.open(response.raw).convert("RGB")
        
        # Tiền xử lý và chạy qua model CLIP
        inputs = processor(images=image, return_tensors="pt")
        outputs = model.get_image_features(**inputs)
        
        # Lấy vector đầu ra
        image_embeds = outputs[0]
        print(f" - [Ảnh {idx+1}] Thành công -> Vector kích thước {image_embeds.shape}")
        
    except Exception as e:
        print(f" - [Ảnh {idx+1}] Lỗi khi tải hoặc xử lý: {e}")

# 4. In kết quả thời gian
end_time = time.time()
print(f"\nHoàn thành! Tổng thời gian chạy: {end_time - start_time:.2f} giây.")