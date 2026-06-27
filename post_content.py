import os
import sys
import json
import csv
import base64
import requests
from urllib.parse import urljoin
from dotenv import load_dotenv
load_dotenv()

from image_processor import create_product_banner
from image_uploader import upload_image_to_wordpress
from facebook_poster import post_to_facebook, comment_on_post, post_to_instagram, post_to_threads
from prepare_content import main as fetch_new_products

def publish_wp_post(post_id):
    wp_site_url = os.getenv("WP_SITE_URL", "https://lucas.vn").strip().strip('"').strip("'")
    wp_username = os.getenv("WP_USERNAME").strip().strip('"').strip("'")
    wp_app_password = os.getenv("WP_APP_PASSWORD").strip().strip('"').strip("'")
    
    if not all([wp_site_url, wp_username, wp_app_password]):
        print("[!] Thiếu thông tin cấu hình WordPress trong .env để publish bài viết.")
        return False
        
    url = urljoin(wp_site_url, f"/wp-json/wp/v2/posts/{post_id}")
    auth = base64.b64encode(f"{wp_username}:{wp_app_password}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
    }
    payload = {
        "status": "publish"
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        if r.status_code == 200:
            print(f"[+] Đã chuyển trạng thái bài viết WP {post_id} thành PUBLISHED công khai.")
            return True
        else:
            print(f"[!] Lỗi chuyển trạng thái bài viết WP {post_id}: {r.status_code} {r.text}")
    except Exception as e:
        print(f"[!] Lỗi kết nối khi chuyển trạng thái bài viết WP {post_id}: {e}")
    return False

HISTORY_FILE = "history.json"
CSV_FILE = "content_plan.csv"
DRY_RUN = False # Nếu True sẽ không đăng thật lên Facebook

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)

def main():
    print("==================================================")
    print("🚀 BẮT ĐẦU CHẠY POSTER TỪ FILE CSV")
    print("==================================================")
    
    # TỰ ĐỘNG QUÉT SẢN PHẨM MỚI TỪ WEBSITE VÀO CSV
    print("[*] Đang kiểm tra xem có sản phẩm nào mới trên Website không...")
    fetch_new_products()

    # TỰ ĐỘNG TẠO BÀI VIẾT SEO NHÁP TRÊN WORDPRESS CHO CÁC SẢN PHẨM MỚI
    print("[*] Đang tự động tạo bài viết SEO nháp trên WordPress...")
    try:
        from create_wp_drafts import main as create_wp_drafts
        create_wp_drafts()
    except Exception as e:
        print(f"[!] Lỗi khi tự động tạo nháp trên WordPress: {e}")
    
    if not os.path.exists(CSV_FILE):
        print(f"[!] Vẫn không tìm thấy file {CSV_FILE}.")
        return

    # Đọc toàn bộ nội dung CSV
    rows = []
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)
            
    BRANDS = ['Thule', 'Ulanzi', 'Inateck', 'LISEN', 'WiWU', 'HyperWork', 'Anker', 'Sharge', 'Tomtoc', 'Spigen', 'MOFT', 'Zagg']
    def get_brand(title):
        title_lower = title.lower()
        for b in BRANDS:
            if b.lower() in title_lower:
                return b
        return "Other"

    # Tìm brand của bài cuối cùng đã POSTED (giữ lại cho các mục tiêu future, không dùng hiện tại)
    last_posted_brand = None
    for row in reversed(rows):
        if row.get("Status") == "POSTED":
            last_posted_brand = get_brand(row.get("Title", ""))
            break

    # Lấy danh sách các bài cần publish (status DRAFT hoặc WP_DRAFT). Giới hạn số bài mỗi lần chạy
    MAX_PUBLISH = int(os.getenv("MAX_PUBLISH", "2"))
    publish_indices = []
    for i, row in enumerate(rows):
        if row.get("Status") in ("DRAFT", "WP_DRAFT"):
            publish_indices.append(i)
            if len(publish_indices) >= MAX_PUBLISH:
                break

    if not publish_indices:
        print("[!] Không có bài DRAFT nào để publish.")
        return

    for target_idx in publish_indices:
        prod = rows[target_idx]
        print(f"[*] Đang chuẩn bị đăng sản phẩm: {prod['Title']}")
        # Tái tạo caption bằng AI
        try:
            from ai_generator import generate_social_posts
            ai_result = generate_social_posts(prod["Title"], prod["Link"])
            caption = ai_result.get("facebook", "") if isinstance(ai_result, dict) else str(ai_result)
            prod["Caption"] = caption
        except Exception as e:
            print(f"[!] Lỗi tạo caption cho {prod['Title']}: {e}")
            continue

        try:
            # 1. Thiết kế ảnh banner (JPEG)
            banner_path = create_product_banner(prod["ImageURL"], prod["Title"], "temp_banner_post.jpg")

            # 2. Đăng lên Facebook (hoặc DRY_RUN)
            if DRY_RUN:
                print(f"[!] DRY_RUN: sẽ không đăng lên Facebook, banner tại {banner_path}")
                rows[target_idx]["Status"] = "POSTED"
            else:
                post_id = post_to_facebook(banner_path, prod["Caption"])
                if post_id:
                    comment_text = f"👉 Xem chi tiết và đặt mua sản phẩm tại đây: {prod['Link']}"
                    comment_on_post(post_id, comment_text)

                    # Đăng lên Instagram & Threads
                    public_url = upload_image_to_wordpress(banner_path)
                    if public_url:
                        ig_caption = f"{prod['Caption']}\n\n👉 Mua ngay tại: {prod['Link']}"
                        post_to_instagram(public_url, ig_caption)
                        post_to_threads(public_url, ig_caption)

                    # Chuyển trạng thái bài viết WordPress thành công khai nếu có WP_ID
                    wp_id = prod.get("WP_ID")
                    if wp_id:
                        publish_wp_post(wp_id)

                    rows[target_idx]["Status"] = "POSTED"

                    # Cập nhật history
                    history = load_history()
                    if prod["Link"] not in history:
                        history.append(prod["Link"])
                    save_history(history)
                else:
                    print("[!] Đăng Facebook thất bại, bỏ qua bài này.")
                    continue

            # Dọn dẹp ảnh tạm
            if os.path.exists(banner_path):
                os.remove(banner_path)

        except Exception as e:
            print(f"[!] Lỗi khi xử lý bài {prod['Title']}: {e}")
            continue
    # Ghi lại CSV với Status mới
    with open(CSV_FILE, "w", encoding="utf-8", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        
    print("\n[+] Hoàn tất kịch bản. Chúc một ngày tốt lành!")

if __name__ == "__main__":
    main()
