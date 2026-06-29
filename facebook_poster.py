import os
import requests
import time

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
        "message": caption,
        "access_token": page_token
    }
    
    print("[*] Đang gửi yêu cầu lên Facebook Graph API...")
    with open(image_path, "rb") as img_file:
        response = requests.post(url, data=payload, files={"source": img_file}, timeout=30)
    
    if response.status_code != 200:
        print(f"[!] Lỗi khi đăng bài lên Facebook: {response.text}")
        return None
    
    res_data = response.json()
    post_id = res_data.get("post_id") or res_data.get("id")
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
    response = requests.post(url, data=payload, timeout=30)
    if response.status_code == 200:
        print("[+] Đã comment link thành công!")
        return True
    else:
        print(f"[!] Lỗi khi comment: {response.text}")
        return False

def post_to_instagram(image_url: str, caption: str) -> str:
    """
    Đăng ảnh lên Instagram bằng link Public.
    """
    ig_account_id = os.getenv("IG_ACCOUNT_ID")
    page_token = os.getenv("FB_PAGE_TOKEN") # Thường dùng chung token với Page
    
    if not ig_account_id or not page_token:
        print("[!] Thiếu IG_ACCOUNT_ID hoặc FB_PAGE_TOKEN trong .env")
        return None
        
    print("[*] Đang đẩy ảnh lên Instagram Container...")
    url_media = f"https://graph.facebook.com/v20.0/{ig_account_id}/media"
    payload_media = {
        "image_url": image_url,
        "caption": caption,
        "access_token": page_token
    }
    
    res = requests.post(url_media, data=payload_media, timeout=30)
    if res.status_code != 200:
        print(f"[!] Lỗi khi tạo IG Media Container: {res.text}")
        return None
        
    creation_id = res.json().get("id")
    
    print("[*] Đang chờ 10 giây để Instagram xử lý ảnh...")
    time.sleep(10)
    
    print("[*] Đang Publish Instagram Post...")
    url_publish = f"https://graph.facebook.com/v20.0/{ig_account_id}/media_publish"
    payload_publish = {
        "creation_id": creation_id,
        "access_token": page_token
    }
    
    res_pub = requests.post(url_publish, data=payload_publish, timeout=30)
    if res_pub.status_code != 200:
        print(f"[!] Lỗi khi Publish IG Post: {res_pub.text}")
        return None
        
    post_id = res_pub.json().get("id")
    print(f"[+] Đã đăng thành công lên Instagram! Post ID: {post_id}")
    return post_id

def post_to_threads(image_url: str, text: str) -> str:
    """
    Đăng bài lên Threads.
    """
    threads_user_id = os.getenv("THREADS_USER_ID")
    threads_token = os.getenv("THREADS_TOKEN")
    
    if not threads_user_id or not threads_token:
        print("[!] Thiếu THREADS_USER_ID hoặc THREADS_TOKEN trong .env")
        return None
        
    # Đảm bảo caption Threads không vượt quá 500 ký tự theo chuẩn API
    if len(text) > 495:
        text = text[:495] + "..."
        
    print("[*] Đang đẩy ảnh lên Threads Container...")
    url_media = f"https://graph.threads.net/v1.0/{threads_user_id}/threads"
    payload_media = {
        "media_type": "IMAGE",
        "image_url": image_url,
        "text": text,
        "access_token": threads_token
    }
    
    res = requests.post(url_media, data=payload_media, timeout=30)
    if res.status_code != 200:
        print(f"[!] Lỗi khi tạo Threads Container: {res.text}")
        return None
        
    creation_id = res.json().get("id")
    
    print("[*] Đang Publish Threads Post...")
    url_publish = f"https://graph.threads.net/v1.0/{threads_user_id}/threads_publish"
    payload_publish = {
        "creation_id": creation_id,
        "access_token": threads_token
    }
    
    res_pub = requests.post(url_publish, data=payload_publish, timeout=30)
    if res_pub.status_code != 200:
        print(f"[!] Lỗi khi Publish Threads Post: {res_pub.text}")
        return None
        
    post_id = res_pub.json().get("id")
    print(f"[+] Đã đăng thành công lên Threads! Post ID: {post_id}")
    return post_id

if __name__ == "__main__":
    pass
