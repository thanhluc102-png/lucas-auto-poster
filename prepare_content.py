import os
import json
import csv
from dotenv import load_dotenv
load_dotenv()

from scraper import get_new_products
from ai_generator import generate_social_posts

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
    
    # 1. Quét web cho các danh mục mục tiêu
    TARGET_BRANDS = ["lisen", "aulumu", "inateck"]
    products = []
    for brand in TARGET_BRANDS:
        # Thiết lập tạm thời URL danh mục cho scraper
        os.environ["TARGET_CATEGORY_URL"] = f"https://lucas.vn/thuong-hieu/{brand}"
        products.extend(get_new_products())
    
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
        fieldnames = ["Status", "Title", "Link", "ImageURL", "Caption", "Tag"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
        
        for i, prod in enumerate(new_products):
            print(f"\n--- Đang xử lý sản phẩm {i+1}/{len(new_products)} ---")
            print(f"Tên: {prod['title']}")
            
            try:
                ai_result = generate_social_posts(prod['title'], prod['link'])
                caption = ai_result.get("facebook", "") if isinstance(ai_result, dict) else str(ai_result)
                writer.writerow({
                    "Status": "DRAFT",
                    "Title": prod['title'],
                    "Link": prod['link'],
                    "ImageURL": prod['thumbnail'],
                    "Caption": caption,
                    "Tag": "lucas.vn"
                })
                print("[+] Đã lưu vào content_plan.csv với trạng thái DRAFT và Tag lucas.vn")
            except Exception as e:
                print(f"[!] Lỗi AI khi xử lý sản phẩm {prod['title']}: {e}")

    print(f"\n[+] Đã hoàn tất! Vui lòng mở file '{CSV_FILE}' để xem lại nội dung.")
    print("[*] Đổi Status thành 'APPROVED' cho những bài bạn muốn đăng.")

if __name__ == "__main__":
    main()
