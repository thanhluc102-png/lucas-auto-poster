import os
import json
import csv
from dotenv import load_dotenv
load_dotenv()

from scraper import get_new_products
from ai_generator import generate_facebook_post

HISTORY_FILE = "history.json"
CSV_FILE = "content_plan.csv"

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_csv_links():
    if not os.path.exists(CSV_FILE):
        return []
    links = []
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            links.append(row["Link"])
    return links

def main():
    print("==================================================")
    print("📋 CHUẨN BỊ NỘI DUNG AUTO POSTER (Duyệt qua CSV)")
    print("==================================================")
    
    # 1. Quét web
    products = get_new_products()
    
    # 2. Lọc sản phẩm đã đăng hoặc đã có trong CSV
    history = load_history()
    csv_links = load_csv_links()
    
    new_products = [p for p in products if p['link'] not in history and p['link'] not in csv_links]
    
    print(f"[*] Tìm thấy {len(new_products)} sản phẩm mới cần sinh nội dung.")
    
    if not new_products:
        print("[+] Không có sản phẩm mới nào.")
        return

    # 3. Mở file CSV để append (nếu chưa có thì tạo header)
    file_exists = os.path.exists(CSV_FILE)
    
    with open(CSV_FILE, "a", encoding="utf-8", newline='') as f:
        fieldnames = ["Status", "Title", "Link", "ImageURL", "Caption"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
        
        for i, prod in enumerate(new_products):
            print(f"\n--- Đang xử lý sản phẩm {i+1}/{len(new_products)} ---")
            print(f"Tên: {prod['title']}")
            
            try:
                caption = generate_facebook_post(prod['title'], prod['link'])
                writer.writerow({
                    "Status": "PENDING", # Mặc định là chờ duyệt
                    "Title": prod['title'],
                    "Link": prod['link'],
                    "ImageURL": prod['thumbnail'],
                    "Caption": caption
                })
                print("[+] Đã lưu vào content_plan.csv với trạng thái PENDING")
            except Exception as e:
                print(f"[!] Lỗi AI khi xử lý sản phẩm {prod['title']}: {e}")

    print(f"\n[+] Đã hoàn tất! Vui lòng mở file '{CSV_FILE}' để xem lại nội dung.")
    print("[*] Đổi Status thành 'APPROVED' cho những bài bạn muốn đăng.")

if __name__ == "__main__":
    main()
