import os
import requests
import base64
from io import BytesIO
from playwright.sync_api import sync_playwright

WIDTH = 1080
HEIGHT = 1080

def get_base64_image(image_url_or_path: str):
    """Tải ảnh và chuyển thành chuỗi Base64 để nhúng thẳng vào HTML"""
    try:
        if image_url_or_path.startswith("http"):
            response = requests.get(image_url_or_path, timeout=10)
            response.raise_for_status()
            img_data = response.content
            content_type = response.headers.get("Content-Type", "image/png")
        else:
            with open(image_url_or_path, "rb") as f:
                img_data = f.read()
            content_type = "image/png"
            if image_url_or_path.endswith(".jpg") or image_url_or_path.endswith(".jpeg"):
                content_type = "image/jpeg"
                
        return f"data:{content_type};base64," + base64.b64encode(img_data).decode("utf-8")
    except Exception as e:
        print(f"Lỗi tải ảnh {image_url_or_path}: {e}")
        return ""

def create_product_banner(image_url: str, title: str, output_path: str = "temp_banner_post.jpg"):
    output_path = output_path.replace(".png", ".jpg")
    """
    Sử dụng Playwright để chụp ảnh màn hình từ file HTML/CSS siêu đẹp.
    """
    print(f"[*] Đang thiết kế ảnh HTML cho: {title[:30]}...")
    
    # 1. Đọc file template.html
    template_path = "template.html"
    if not os.path.exists(template_path):
        print("[!] Không tìm thấy file template.html!")
        return None
        
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    # 2. Chuẩn bị ảnh dạng Base64
    product_b64 = get_base64_image(image_url)
    logo_b64 = get_base64_image("logo.png") if os.path.exists("logo.png") else ""
    
    # 3. Trộn dữ liệu vào HTML
    html_content = html_content.replace("{{ TITLE }}", title)
    html_content = html_content.replace("{{ IMAGE_BASE64 }}", product_b64)
    html_content = html_content.replace("{{ LOGO_BASE64 }}", logo_b64)
    
    # 4. Render và chụp ảnh bằng Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        page.set_content(html_content, wait_until="networkidle")
        page.screenshot(path=output_path, type="jpeg", quality=80, clip={"x": 0, "y": 0, "width": WIDTH, "height": HEIGHT})
        browser.close()
        
    print(f"[+] Đã tạo xong banner xịn xò: {output_path}")
    return output_path

if __name__ == "__main__":
    pass
