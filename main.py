import os
import json
from dotenv import load_dotenv

from scraper import get_new_products
from ai_generator import generate_facebook_post
from facebook_poster import post_to_facebook

HISTORY_FILE = "history.json"
# DRY_RUN = True sẽ KHÔNG đăng lên Facebook, chỉ in ra màn hình
DRY_RUN = True

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def main():
    print("="*50)
    print("🚀 BẮT ĐẦU CHẠY AUTO POSTER LUCAS.VN")
    print("="*50)
    
    # Load biến môi trường
    load_dotenv()
    
    # 1. Quét sản phẩm mới
    products = get_new_products()
    if not products:
        print("[-] Không tìm thấy sản phẩm nào trên trang web.")
        return
        
    # 2. Đọc lịch sử để lọc sản phẩm đã đăng
    history = load_history()
    new_products = [p for p in products if p['link'] not in history]
    
    print(f"[*] Có {len(new_products)} sản phẩm MỚI chưa được đăng.")
    
    if not new_products:
        print("[+] Đã cập nhật xong. Hẹn gặp lại lần sau!")
        return

    # 3. Chỉ xử lý 2 sản phẩm mỗi lần chạy để tránh spam Facebook
    MAX_POSTS_PER_RUN = 2
    products_to_post = new_products[:MAX_POSTS_PER_RUN]
    
    for idx, prod in enumerate(products_to_post, 1):
        print(f"\n--- Đang xử lý sản phẩm {idx}/{len(products_to_post)} ---")
        print(f"Tên: {prod['title']}")
        print(f"Link: {prod['link']}")
        print(f"Ảnh: {prod['thumbnail']}")
        
        try:
            # 4. Sinh nội dung bằng AI
            caption = generate_facebook_post(prod['title'], prod['link'])
            print("\n>>> KẾT QUẢ AI SINH RA:")
            print(caption)
            print("<<<\n")
            
            # 5. Đăng lên Facebook
            if DRY_RUN:
                print("[!] Đang ở chế độ DRY_RUN = True -> KHÔNG đăng lên Facebook.")
            else:
                post_to_facebook(prod['thumbnail'], caption)
            
            # 6. Lưu vào lịch sử (chỉ lưu khi post thành công hoặc chạy dry run OK)
            history.append(prod['link'])
            save_history(history)
            
        except Exception as e:
            print(f"[!] Lỗi khi xử lý sản phẩm {prod['title']}: {e}")
            
    print("\n[+] Hoàn tất kịch bản. Chúc một ngày tốt lành!")

if __name__ == "__main__":
    main()
