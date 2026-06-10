import os
import requests

def post_to_facebook(image_url: str, caption: str) -> dict:
    """
    Đăng ảnh kèm caption lên Facebook Fanpage thông qua Graph API.
    Ảnh sẽ được upload trực tiếp từ URL mà không cần tải xuống máy.
    """
    page_token = os.getenv("FB_PAGE_TOKEN")
    page_id = os.getenv("FB_PAGE_ID")
    
    if not page_token or page_token == "your_facebook_page_token_here":
        raise ValueError("Chưa cấu hình FB_PAGE_TOKEN trong file .env")
    if not page_id or page_id == "your_facebook_page_id_here":
        raise ValueError("Chưa cấu hình FB_PAGE_ID trong file .env")

    # API Endpoint để post ảnh
    url = f"https://graph.facebook.com/v20.0/{page_id}/photos"
    
    payload = {
        "url": image_url,
        "caption": caption,
        "access_token": page_token
    }
    
    print("[*] Đang gửi yêu cầu lên Facebook Graph API...")
    response = requests.post(url, data=payload)
    
    if response.status_code != 200:
        print(f"[!] Lỗi khi đăng bài lên Facebook: {response.text}")
    
    response.raise_for_status()
    result = response.json()
    post_id = result.get("post_id", result.get("id", "?"))
    
    print(f"[+] Đã đăng thành công lên Facebook! Post ID: {post_id}")
    return result

if __name__ == "__main__":
    pass
