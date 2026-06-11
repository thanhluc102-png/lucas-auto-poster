import os
import json
import csv
from dotenv import load_dotenv
load_dotenv()

from image_processor import create_product_banner
from facebook_poster import post_to_facebook, comment_on_post

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
    
    if not os.path.exists(CSV_FILE):
        print(f"[!] File {CSV_FILE} không tồn tại. Hãy chạy prepare_content.py trước.")
        return

    # Đọc toàn bộ nội dung CSV
    rows = []
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)
            
    # Tìm bài đầu tiên có trạng thái PENDING hoặc APPROVED
    target_idx = -1
    prod = None
    for i, row in enumerate(rows):
        if row.get("Status") in ["APPROVED", "PENDING"]:
            prod = row
            target_idx = i
            break
            
    if not prod:
        print("[!] Không tìm thấy bài viết nào đang ở trạng thái chờ duyệt (PENDING/APPROVED).")
        print("[*] Hãy chạy lại lệnh python3 prepare_content.py để quét thêm sản phẩm mới.")
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
                
                rows[target_idx]["Status"] = "POSTED"
                
                # Cập nhật history
                history = load_history()
                if prod['Link'] not in history:
                    history.append(prod['Link'])
                save_history(history)
            else:
                print("[!] Quá trình đăng bài thất bại.")
                
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
