import os
import requests
from dotenv import load_dotenv

# Load biến môi trường từ .env
load_dotenv()

def upload_image_to_wordpress(file_path: str) -> str:
    """
    Đọc file ảnh tĩnh trên máy và Upload lên thư viện ảnh của WordPress.
    Trả về đường dẫn Public URL của bức ảnh.
    """
    wp_site_url = os.getenv("WP_SITE_URL", "https://lucas.vn")
    wp_username = os.getenv("WP_USERNAME")
    wp_app_password = os.getenv("WP_APP_PASSWORD")

    if not wp_username or not wp_app_password:
        print("[!] Thiếu WP_USERNAME hoặc WP_APP_PASSWORD trong file .env")
        return None

    if not os.path.exists(file_path):
        print(f"[!] Không tìm thấy file ảnh: {file_path}")
        return None

    print(f"[*] Đang đẩy ảnh {file_path} lên hệ thống Website...")
    
    try:
        with open(file_path, "rb") as f:
            img_bytes = f.read()

        import time
        # Tạo tên file chỉ chứa ASCII để tránh lỗi 'latin-1' codec can't encode của Python requests
        filename = f"lucas_banner_{int(time.time())}.png"
        content_type = "image/png" if file_path.endswith(".png") else "image/jpeg"

        auth = (wp_username, wp_app_password)
        r = requests.post(
            f"{wp_site_url}/wp-json/wp/v2/media",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": content_type,
            },
            data=img_bytes,
            auth=auth,
            timeout=90,
        )

        if r.status_code not in (200, 201):
            print(f"[!] Media upload HTTP {r.status_code}: {r.text[:200]}")
            return None

        media = r.json()
        public_url = media.get("source_url")
        if not public_url:
            print(f"[!] Tải ảnh lên thành công nhưng không lấy được source_url")
            return None

        print(f"[+] Lấy link ảnh Public thành công: {public_url}")
        return public_url

    except Exception as e:
        print(f"[!] Lỗi khi đẩy ảnh lên Website: {e}")
        return None

if __name__ == "__main__":
    pass
