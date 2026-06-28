import os
import sys
import json
import csv
import base64
import requests
from urllib.parse import urljoin
from dotenv import load_dotenv
load_dotenv()

from prepare_content import main as fetch_new_products
# NOTE: Đã bỏ Facebook/Instagram/Threads + banner Playwright — pipeline giờ CHỈ đăng WordPress.
# Các module facebook_poster / image_processor / image_uploader vẫn còn trong repo nếu sau muốn bật lại.

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

    def save_csv():
        # Lưu NGAY sau mỗi bài đã đăng để tránh đăng lại (trùng) nếu lần chạy lỗi giữa chừng
        with open(CSV_FILE, "w", encoding="utf-8", newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


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

    # Lấy danh sách bài cần đăng web: CHỈ những bài đã có nháp WP (WP_DRAFT + WP_ID).
    # Giới hạn số bài mỗi lần chạy.
    MAX_PUBLISH = int(os.getenv("MAX_PUBLISH", "1"))
    publish_indices = []
    for i, row in enumerate(rows):
        if row.get("Status") == "WP_DRAFT" and (row.get("WP_ID") or "").strip():
            publish_indices.append(i)
            if len(publish_indices) >= MAX_PUBLISH:
                break

    if not publish_indices:
        print("[!] Không có bài WP_DRAFT nào (đã tạo nháp) để đăng web.")
        return

    for target_idx in publish_indices:
        prod = rows[target_idx]
        wp_id = (prod.get("WP_ID") or "").strip()
        print(f"[*] Đang đăng bài web: {prod['Title']} (WP_ID={wp_id})")
        try:
            # Chỉ chuyển bài WordPress từ draft -> publish (không Facebook/IG/Threads)
            if publish_wp_post(wp_id):
                rows[target_idx]["Status"] = "POSTED"
                history = load_history()
                if prod["Link"] not in history:
                    history.append(prod["Link"])
                save_history(history)
                save_csv()  # lưu ngay sau mỗi bài (chống đăng trùng)
                print(f"[+] Đã đăng web: {prod['Title']}")
            else:
                print(f"[!] Publish WP thất bại cho '{prod['Title']}' — giữ nguyên WP_DRAFT, thử lại lần sau.")
        except Exception as e:
            print(f"[!] Lỗi khi đăng bài '{prod['Title']}': {e}")
            continue

    save_csv()  # lưu lần cuối cho chắc
    print("\n[+] Hoàn tất kịch bản (web-only). Chúc một ngày tốt lành!")

if __name__ == "__main__":
    main()
