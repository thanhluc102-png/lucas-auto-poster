import os
import json
import csv
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
load_dotenv()

from scraper import get_new_products
import wc_api

HISTORY_FILE = "history.json"
CSV_FILE = "content_plan.csv"
STATE_FILE = "last_scan.txt"   # mốc thời gian quét toàn shop (chỉ lấy sp publish SAU mốc này)


def load_cutoff():
    """Mốc quét toàn shop. Nếu chưa có file -> mặc định 24h trước (an toàn)."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                return v
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")


def save_cutoff(dt_iso):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(dt_iso)

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
    
    history = load_history()
    csv_links = load_csv_links()

    # 1. Quét sản phẩm
    products = []
    if wc_api.enabled():
        # TOÀN SHOP qua WooCommerce: chỉ lấy sản phẩm publish SAU mốc cutoff (kể từ hôm nay)
        cutoff = load_cutoff()
        print(f"[*] Quét toàn shop qua WooCommerce, sản phẩm publish sau: {cutoff}")
        products, newest = wc_api.list_products_after(cutoff)
        print(f"[*] WC trả về {len(products)} sản phẩm sau mốc.")
        if newest:
            save_cutoff(newest)   # đẩy mốc tới sp mới nhất -> lần sau chỉ lấy cái mới hơn
            print(f"[*] Cập nhật mốc quét -> {newest}")
    else:
        # Fallback: quét theo brand bằng scrape HTML (khi chưa cấu hình WC)
        print("[*] WC chưa bật -> fallback quét theo brand (scrape HTML).")
        for brand in ["lisen", "aulumu", "inateck"]:
            os.environ["TARGET_CATEGORY_URL"] = f"https://lucas.vn/thuong-hieu/{brand}"
            products.extend(get_new_products())

    # 2. Lọc sản phẩm đã đăng / đã có trong CSV (chống trùng)
    new_products = [p for p in products if p['link'] not in history and p['link'] not in csv_links]

    print(f"[*] Tìm thấy {len(new_products)} sản phẩm mới cần thêm vào hàng chờ.")
    
    if not new_products:
        print("[+] Không có sản phẩm mới nào.")
        return

    # 3. Mở file CSV để append (nếu chưa có thì tạo header)
    file_exists = os.path.exists(CSV_FILE)
    
    with open(CSV_FILE, "a", encoding="utf-8", newline='') as f:
        # Giữ đúng thứ tự cột như pipeline (có WP_ID) để hàng append không lệch cột
        fieldnames = ["Status", "Title", "Link", "ImageURL", "Caption", "Tag", "WP_ID"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        for i, prod in enumerate(new_products):
            print(f"\n--- Đang xử lý sản phẩm {i+1}/{len(new_products)} ---")
            print(f"Tên: {prod['title']}")

            try:
                # Web-only: KHÔNG sinh caption mạng xã hội nữa (tiết kiệm gọi AI + bớt điểm lỗi)
                writer.writerow({
                    "Status": "DRAFT",
                    "Title": prod['title'],
                    "Link": prod['link'],
                    "ImageURL": prod['thumbnail'],
                    "Caption": "",
                    "Tag": "lucas.vn",
                    "WP_ID": ""
                })
                print("[+] Đã lưu vào content_plan.csv với trạng thái DRAFT và Tag lucas.vn")
            except Exception as e:
                print(f"[!] Lỗi khi lưu sản phẩm {prod['title']}: {e}")

    print(f"\n[+] Đã hoàn tất! Vui lòng mở file '{CSV_FILE}' để xem lại nội dung.")
    print("[*] Đổi Status thành 'APPROVED' cho những bài bạn muốn đăng.")

if __name__ == "__main__":
    main()
