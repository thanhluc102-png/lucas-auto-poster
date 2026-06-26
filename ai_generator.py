import os
import json
import anthropic

def generate_social_posts(product_title: str, product_link: str) -> dict:
    """
    Sử dụng Anthropic (Claude) để tạo nội dung bài post Facebook, Instagram, Threads
    dựa trên tên sản phẩm.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Chưa cấu hình ANTHROPIC_API_KEY trong file .env")
        
    client = anthropic.Anthropic(api_key=api_key)
    
    prompt = f"""Bạn là một chuyên gia viết content mạng xã hội (Facebook, Instagram, Threads).
Hãy viết 3 phiên bản giới thiệu cho sản phẩm sau đây.
Tên sản phẩm: {product_title}
Link (nếu cần tham khảo): {product_link}

Quy tắc BẮT BUỘC:
1. TRẢ VỀ DUY NHẤT MỘT KHỐI JSON, không kèm bất kỳ giải thích nào bên ngoài.
2. Cấu trúc JSON phải chính xác như sau:
{{
  "facebook": "Content vô cùng ngắn gọn (tối đa 3-4 câu), cách dòng thoáng, có emoji. KHÔNG chứa link. BẮT BUỘC có câu kết thúc: '👉 Xem chi tiết sản phẩm dưới phần Bình Luận nhé!'",
  "instagram": "Content siêu ngắn (1-2 câu), tập trung vào lối sống, kèm 3-4 hashtag xịn xò cuối bài.",
  "threads": "Content cực ngắn gọn, châm biếm hoặc review giật gân, dưới 100 chữ."
}}
3. Trong JSON, tuyệt đối dùng chuỗi hợp lệ (escaped string).

Hãy tạo nội dung JSON ngay bây giờ:"""

    print(f"[*] Đang yêu cầu AI tạo nội dung 3 nền tảng cho: {product_title[:30]}...")
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2500,
            temperature=0.7,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        raw_text = response.content[0].text.strip()
        
        # Tìm khối JSON an toàn bằng regex để bỏ qua các câu giới thiệu thừa
        import re
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            raw_text = match.group(0)
            
        result = json.loads(raw_text)
        return result
    except json.JSONDecodeError as e:
        print(f"[!] Lỗi khi Parse JSON AI: {e}\nRaw Text trả về: {raw_text}")
        return None
    except Exception as e:
        print(f"[!] Lỗi khi gọi AI: {e}")
        return None

if __name__ == "__main__":
    pass
