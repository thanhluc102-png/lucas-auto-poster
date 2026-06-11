import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import textwrap

WIDTH = 1080
HEIGHT = 1080

def create_gradient_background(width, height, color1, color2):
    """Tạo nền gradient dọc từ color1 sang color2"""
    base = Image.new('RGB', (width, height), color1)
    top = Image.new('RGB', (width, height), color2)
    mask = Image.new('L', (width, height))
    mask_data = []
    for y in range(height):
        # Tạo mask gradient (0-255)
        mask_data.extend([int(255 * (y / height))] * width)
    mask.putdata(mask_data)
    base.paste(top, (0, 0), mask)
    return base.convert("RGBA")

def create_product_banner(image_url: str, title: str, output_path: str = "temp_banner.png"):
    """
    Tải ảnh từ URL, chèn vào canvas 1080x1080 có màu nền gradient cao cấp,
    thêm bóng đổ (shadow), nhãn mới về, logo và tên sản phẩm nổi bật.
    """
    print(f"[*] Đang thiết kế ảnh cho: {title[:30]}...")
    
    # 1. Tải ảnh sản phẩm
    response = requests.get(image_url)
    response.raise_for_status()
    prod_img = Image.open(BytesIO(response.content)).convert("RGBA")
    
    # 2. Khởi tạo Canvas với nền Gradient Vàng Sang Trọng
    canvas = create_gradient_background(WIDTH, HEIGHT, (255, 230, 0), (255, 170, 0)) # Vàng rực sang cam vàng
    
    # 3. Kích thước thiệp (card)
    card_width, card_height = 920, 720
    card_x, card_y = (WIDTH - card_width) // 2, 140
    
    # Đổ bóng (Drop Shadow)
    shadow = Image.new('RGBA', (WIDTH, HEIGHT), (0,0,0,0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_offset = 20
    shadow_draw.rounded_rectangle(
        [(card_x + shadow_offset, card_y + shadow_offset), 
         (card_x + card_width + shadow_offset, card_y + card_height + shadow_offset)],
        radius=40, fill=(0, 0, 0, 80)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(15))
    canvas.paste(shadow, (0, 0), shadow)
    
    # Vẽ tấm thiệp trắng bo góc
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        [(card_x, card_y), (card_x + card_width, card_y + card_height)],
        radius=30, fill="white"
    )
    
    # 4. Chèn ảnh sản phẩm vào trung tâm thiệp
    prod_img.thumbnail((850, 650), Image.Resampling.LANCZOS)
    paste_x = card_x + (card_width - prod_img.width) // 2
    paste_y = card_y + (card_height - prod_img.height) // 2
    canvas.paste(prod_img, (paste_x, paste_y), prod_img)
    
    # 5. Thêm nhãn "MỚI VỀ" (Badge)
    try:
        font_badge = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 32)
    except:
        font_badge = ImageFont.load_default()
    
    badge_width, badge_height = 200, 60
    badge_x, badge_y = card_x - 10, card_y + 30
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + badge_width, badge_y + badge_height)],
        radius=10, fill="#E63946" # Màu đỏ đậm
    )
    # Căn giữa chữ "MỚI VỀ" trong badge
    draw.text((badge_x + 30, badge_y + 12), "MỚI VỀ", fill="white", font=font_badge)
    
    # 6. Chèn Logo
    logo_path = "logo.png"
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((220, 80), Image.Resampling.LANCZOS)
        canvas.paste(logo, (50, 30), logo)
    
    # 7. Ghi Tên sản phẩm ở phần dưới (cân đối 2 dòng và chữ to hơn)
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 55)
    except:
        font_title = ImageFont.load_default()
        
    y_text = card_y + card_height + 45
    
    # Thuật toán chia dòng sao cho độ dài 2 dòng cân bằng nhất có thể
    words = title.split()
    lines = [title]
    
    if len(words) > 3:
        # Nếu toàn bộ dòng dài hơn chiều rộng cho phép, bắt buộc chia 2 dòng
        if draw.textbbox((0, 0), title, font=font_title)[2] > WIDTH - 100 or len(words) >= 5:
            best_diff = float('inf')
            best_split = 1
            for i in range(1, len(words)):
                l1 = " ".join(words[:i])
                l2 = " ".join(words[i:])
                w1 = draw.textbbox((0, 0), l1, font=font_title)[2]
                w2 = draw.textbbox((0, 0), l2, font=font_title)[2]
                diff = abs(w1 - w2)
                if diff < best_diff:
                    best_diff = diff
                    best_split = i
            lines = [" ".join(words[:best_split]), " ".join(words[best_split:])]

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        text_width = bbox[2] - bbox[0]
        text_x = (WIDTH - text_width) // 2
        # Chữ đen xám đậm dễ đọc trên nền vàng
        draw.text((text_x, y_text), line, fill="#111827", font=font_title)
        y_text += 70
        
    final_image = canvas.convert("RGB")
    final_image.save(output_path, format="PNG")
    print(f"[+] Đã tạo xong banner ảnh: {output_path}")
    return output_path

if __name__ == "__main__":
    pass
