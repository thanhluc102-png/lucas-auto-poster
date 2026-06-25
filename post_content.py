import os
import sys
import json
import csv
from dotenv import load_dotenv
load_dotenv()

from image_processor import create_product_banner
from image_uploader import upload_image_to_wordpress
from facebook_poster import post_to_facebook, comment_on_post, post_to_instagram, post_to_threads
from prepare_content import main as fetch_new_products

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

    # Tìm brand của bài cuối cùng đã POSTED
    last_posted_brand = None
    for row in reversed(rows):
        if row.get("Status") == "POSTED":
            last_posted_brand = get_brand(row.get("Title", ""))
            break

    # Tìm bài đầu tiên có trạng thái PENDING hoặc APPROVED
    target_idx = -1
    prod = None
    
    # Ưu tiên tìm bài có brand khác với bài vừa đăng
    for i, row in enumerate(rows):
        if row.get("Status") in ["APPROVED", "PENDING"]:
            if get_brand(row.get("Title", "")) != last_posted_brand:
                prod = row
                target_idx = i
                break
                
    # Nếu không có brand khác (hoặc đây là bài đầu tiên), lấy bài PENDING đầu tiên
    if not prod:
        for i, row in enumerate(rows):
            if row.get("Status") in ["APPROVED", "PENDING"]:
                prod = row
                target_idx = i
                break
            
    if not prod:
        print("[!] Không tìm thấy bài viết nào đang ở trạng thái chờ duyệt (PENDING/APPROVED).")
        print("[*] Đã quét hết sản phẩm hiện có trên website. Hãy chờ web cập nhật thêm sản phẩm mới.")
        return
        
    print(f"[*] Đang chuẩn bị đăng sản phẩm: {prod['Title']}")
    
    try:
        # 1. Thiết kế ảnh
        banner_path = create_product_banner(prod['ImageURL'], prod['Title'], "temp_banner_post.png")
        
        # 2. Đăng lên Facebook
        if DRY_RUN:
            print(f"[!] Đang ở chế độ DRY_RUN = True -> KHÔNG đăng lên Facebook. Bạn có thể xem thử ảnh tại {banner_path}")
            # Giả lập post thành công
            rows[target_idx]["Status"] = "POSTED"
        else:
            post_id = post_to_facebook(banner_path, prod['Caption'])
            if post_id:
                comment_text = f"👉 Xem chi tiết và đặt mua sản phẩm tại đây: {prod['Link']}"
                comment_on_post(post_id, comment_text)
                
                # Bơm ảnh lên public URL để đăng sang Insta / Threads
                public_url = upload_image_to_wordpress(banner_path)
                if public_url:
                    ig_caption = f"{prod['Caption']}\n\n👉 Mua ngay tại: {prod['Link']}"
                    post_to_instagram(public_url, ig_caption)
                    post_to_threads(public_url, ig_caption)
                
                rows[target_idx]["Status"] = "POSTED"
                
                # Cập nhật history
                history = load_history()
                if prod['Link'] not in history:
                    history.append(prod['Link'])
                save_history(history)
            else:
                print("[!] Quá trình đăng bài thất bại.")
                sys.exit(1)
                
        # Dọn dẹp ảnh tạm
        if os.path.exists(banner_path):
            os.remove(banner_path)
            
    except Exception as e:
        print(f"[!] Lỗi khi xử lý đăng bài: {e}")

    # Ghi lại CSV với Status mới
    with open(CSV_FILE, "w", encoding="utf-8", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        
    print("\n[+] Hoàn tất kịch bản. Chúc một ngày tốt lành!")

if __name__ == "__main__":
    main()
