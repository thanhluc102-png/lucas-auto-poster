import os
from google import genai
from google.genai import types

def generate_facebook_post(product_title: str, product_link: str) -> str:
    """
    Sử dụng Google GenAI (Gemini) để tạo nội dung bài post Facebook dựa trên tên sản phẩm.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError("Chưa cấu hình GEMINI_API_KEY trong file .env")
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""Bạn là một chuyên gia Content Marketing và Copywriter chuyên nghiệp, đặc biệt chuyên mảng phụ kiện Apple, đồ công nghệ.
Hãy viết một bài đăng Facebook Fanpage cho sản phẩm sau: '{product_title}'.

Yêu cầu:
1. Dòng đầu tiên phải là một Tiêu Đề (Title) cực kỳ thu hút, giật tít, khơi gợi sự tò mò hoặc đánh đúng vào nỗi đau của khách hàng. Hãy in hoa hoặc dùng ngoặc vuông để làm nổi bật. (Độ dài < 15 chữ).
2. Phần thân bài dài khoảng 3-4 câu, giới thiệu ngắn gọn lợi ích nổi bật của sản phẩm.
3. Tạo sự khan hiếm (ví dụ: "Số lượng có hạn", "Chỉ còn vài chiếc",...).
4. Dòng cuối cùng là Call-to-Action, hướng dẫn khách bấm vào link để mua hàng.
5. Sử dụng emoji phù hợp nhưng đừng lạm dụng quá nhiều.
6. Kết thúc bằng hashtag: #LucasCombo #LucasVN #PhuKienApple #DoCongNghe

Link sản phẩm để chèn vào bài: {product_link}
"""

    print(f"[*] Đang yêu cầu AI tạo nội dung cho: {product_title[:30]}...")
    response = client.models.generate_content(
        model='gemini-2.5-pro',
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
        ),
    )
    
    return response.text.strip()

if __name__ == "__main__":
    # Test thử nếu có API key
    from dotenv import load_dotenv
    load_dotenv()
    if os.getenv("GEMINI_API_KEY") and os.getenv("GEMINI_API_KEY") != "your_gemini_api_key_here":
        print(generate_facebook_post("Túi Hành lý Thule Chasm Recycled Duffel 30L", "https://lucas.vn/..."))
    else:
        print("Chưa có API Key để test.")
