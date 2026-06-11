import os
import requests

def post_to_facebook(image_path: str, caption: str) -> dict:
    """
    Đăng ảnh cục bộ kèm caption lên Facebook Fanpage thông qua Graph API.
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
        "caption": caption,
        "access_token": page_token
    }
    
    print("[*] Đang gửi yêu cầu lên Facebook Graph API...")
    with open(image_path, "rb") as img_file:
        response = requests.post(url, data=payload, files={"source": img_file})
    
    if response.status_code != 200:
        print(f"[!] Lỗi khi đăng bài lên Facebook: {response.text}")
        return None
    
    post_id = response.json().get("post_id")
    print(f"[+] Đã đăng thành công lên Facebook! Post ID: {post_id}")
    return post_id

def comment_on_post(post_id: str, comment_text: str) -> bool:
    """
    Bình luận vào một bài viết đã đăng trên Fanpage.
    """
    page_token = os.getenv("FB_PAGE_TOKEN")
    if not page_token:
        return False
        
    url = f"https://graph.facebook.com/v20.0/{post_id}/comments"
    payload = {
        "message": comment_text,
        "access_token": page_token
    }
    
    print("[*] Đang tự động comment link sản phẩm...")
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        print("[+] Đã comment link thành công!")
        return True
    else:
        print(f"[!] Lỗi khi comment: {response.text}")
        return False

if __name__ == "__main__":
    pass
