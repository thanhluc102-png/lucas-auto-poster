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
    
    prompt = f"""Bạn là một copywriter đỉnh cao chuyên viết content viral/giật tít mạng xã hội (Facebook, Instagram, Threads) cho shop phụ kiện lucas.vn.
Hãy viết 3 phiên bản content siêu cuốn hút, GIẬT TÍT MẠNH MẼ cho sản phẩm dưới đây:
Tên sản phẩm: {product_title}
Link sản phẩm: {product_link}

Yêu cầu GIẬT TÍT & NỘI DUNG BẮT BUỘC:
1. CÂU OPENING HOOK (GIẬT TÍT): BẮT BUỘC VIẾT HOA TOÀN BỘ (IN HOA 100%), cực kỳ giật gân/tò mò 🔥 (đánh vào nỗi sợ ướt laptop, rạch túi, hỏng máy, hoặc so sánh vượt tầm giá).
2. XUỐNG DÒNG CÁCH THOÁNG: Ngay sau câu Hook in hoa, BẮT BUỘC xuống 2 lần dòng (tạo 1 dòng trống) rồi mới đến phần nội dung mô tả chi tiết.
3. Từ ngữ ngắn gọn, đắt giá, trình bày thoáng mắt, dùng emoji hợp lý.
4. Cấu trúc JSON bắt buộc:
{{
  "facebook": "CÂU HOOK IN HOA 100% 🔥\\n\\n2-3 câu ngắn nêu bật tính năng đáng đồng tiền bát gạo (chống nước, đệm chống sốc, đựng Mac 16 inch...). KHÔNG chứa link trong bài.\\n\\n👉 Xem chi tiết sản phẩm và ưu đãi dưới phần Bình Luận nhé!",
  "instagram": "CÂU HOOK IN HOA 100% ✨\\n\\nContent sang xịn mịn cho dân mê tech/lifestyle + 4 hashtag chuẩn viral.",
  "threads": "CÂU HOOK IN HOA 100% 💥\\n\\nNội dung châm biếm/gây tranh cãi nhẹ hoặc review chân thực giật gân, dưới 80 chữ."
}}
5. Chỉ trả về DUY NHẤT 1 khối JSON hợp lệ, không có văn bản nào ngoài JSON.

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
