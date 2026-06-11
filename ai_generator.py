import os
import anthropic

def generate_facebook_post(product_title: str, product_link: str) -> str:
    """
    Sử dụng Anthropic (Claude) để tạo nội dung bài post Facebook dựa trên tên sản phẩm.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Chưa cấu hình ANTHROPIC_API_KEY trong file .env")
        
    client = anthropic.Anthropic(api_key=api_key)
    
    prompt = f"""Bạn là một chuyên gia viết content quảng cáo bán hàng trên Facebook (Facebook Copywriter).
Hãy viết 1 đoạn status giới thiệu sản phẩm sau đây:
Tên sản phẩm: {product_title}

Quy tắc BẮT BUỘC (rất quan trọng, nếu vi phạm sẽ bị lỗi hệ thống):
1. TUYỆT ĐỐI KHÔNG SỬ DỤNG ký tự Markdown như ** (để in đậm), * (để in nghiêng), hay # (tiêu đề). Hãy viết text thuần túy như người bình thường gõ trên điện thoại.
2. Bạn ĐƯỢC PHÉP dùng hashtag ở cuối bài viết (ví dụ #LucasVN #PhuKienApple).
3. KHÔNG đưa bất kỳ link trang web hay URL nào vào trong bài viết.
4. Viết ngắn gọn 3-4 câu. ĐẶC BIẸT: Phải XUỐNG DÒNG VÀ ĐỂ TRỐNG 1 DÒNG giữa các ý để đoạn văn trông thoáng, dễ đọc trên điện thoại. Tránh viết thành một cục text dính liền nhau.
5. Sử dụng 2-3 emoji phù hợp cho sinh động.

Nội dung bài đăng:"""

    print(f"[*] Đang yêu cầu AI tạo nội dung cho: {product_title[:30]}...")
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        temperature=0.7,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return response.content[0].text.strip()

if __name__ == "__main__":
    pass
