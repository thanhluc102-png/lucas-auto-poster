#!/usr/bin/env python3
"""
facebook_post.py — TOOL ĐỘC LẬP: tự động đăng sản phẩm từ web lên Facebook (+ Instagram + Threads).

Hoàn toàn tách biệt với pipeline đăng web (post_content.py):
- Nguồn sản phẩm: WooCommerce API (mới nhất trước), fallback scrape.
- State riêng: fb_history.json (link sản phẩm ĐÃ đăng FB) -> không đụng history.json của web.
- Mỗi lần chạy đăng FB_MAX_POSTS sản phẩm mới nhất chưa từng đăng FB.

Caption do Claude viết (ai_generator). Ảnh banner dựng bằng Playwright (image_processor).
"""
import os
import sys
import json
from dotenv import load_dotenv
load_dotenv()

from ai_generator import generate_social_posts
from image_processor import create_product_banner
from image_uploader import upload_image_to_wordpress
from facebook_poster import post_to_facebook, comment_on_post, post_to_instagram, post_to_threads

FB_HISTORY_FILE = "fb_history.json"
FB_MAX_POSTS = int(os.getenv("FB_MAX_POSTS", "1"))   # số sản phẩm đăng FB mỗi lần chạy
# Bật/tắt từng nền tảng (mặc định bật cả 3)
ENABLE_IG = os.getenv("FB_ENABLE_IG", "1") != "0"
ENABLE_THREADS = os.getenv("FB_ENABLE_THREADS", "1") != "0"


def load_fb_history() -> list:
    if os.path.exists(FB_HISTORY_FILE):
        try:
            with open(FB_HISTORY_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_fb_history(h: list):
    with open(FB_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)


def get_candidate_products(limit=30) -> list:
    """Lấy sản phẩm mới nhất từ shop. Ưu tiên WooCommerce API, fallback scrape."""
    target_url = os.getenv("TARGET_CATEGORY_URL", "https://lucas.vn/danh-muc/tui-xach-tui-chong-soc-ba-lo").strip()
    target_kw = os.getenv("TARGET_KEYWORD", "balo").strip()

    try:
        import wc_api
        if wc_api.enabled():
            prods = wc_api.list_recent_products(brand_keyword=target_kw, max_items=limit)
            if prods:
                return prods
    except Exception as e:
        print(f"[!] WC lỗi ({e}) -> fallback scrape.")
    # fallback: scrape trang sản phẩm theo danh mục
    from scraper import get_new_products
    os.environ["TARGET_CATEGORY_URL"] = target_url
    return get_new_products()


def post_one(prod: dict) -> bool:
    """Đăng 1 sản phẩm lên FB (+ IG + Threads). Trả True nếu FB thành công."""
    title = prod["title"]
    link = prod["link"]
    image = prod.get("thumbnail") or ""
    print(f"\n=== Đăng FB: {title} ===")

    # 1. Caption do Claude viết
    try:
        ai = generate_social_posts(title, link) or {}
    except Exception as e:
        print(f"[!] Lỗi tạo caption: {e}")
        ai = {}
    fb_caption = (ai.get("facebook") if isinstance(ai, dict) else "") or f"🔥 {title}"
    ig_caption = (ai.get("instagram") if isinstance(ai, dict) else "") or fb_caption
    th_caption = (ai.get("threads") if isinstance(ai, dict) else "") or fb_caption

    # 2. Dựng banner
    banner = None
    try:
        banner = create_product_banner(image, title, "temp_fb_banner.jpg")
    except Exception as e:
        print(f"[!] Lỗi dựng banner: {e}")
    if not banner or not os.path.exists(banner):
        print("[!] Không có banner -> bỏ qua sản phẩm này.")
        return False

    # 3. Đăng Facebook (bắt buộc)
    post_id = post_to_facebook(banner, fb_caption)
    if not post_id:
        print("[!] Đăng Facebook thất bại.")
        if os.path.exists(banner):
            os.remove(banner)
        return False
    comment_on_post(post_id, f"👉 Xem chi tiết & đặt mua: {link}")

    # 4. Instagram + Threads (không bắt buộc — lỗi cũng không sao)
    if ENABLE_IG or ENABLE_THREADS:
        public_url = upload_image_to_wordpress(banner)
        if public_url:
            if ENABLE_IG:
                try:
                    post_to_instagram(public_url, f"{ig_caption}\n\n👉 Mua tại: {link}")
                except Exception as e:
                    print(f"[!] IG lỗi: {e}")
            if ENABLE_THREADS:
                try:
                    post_to_threads(public_url, f"{th_caption}\n\n👉 {link}")
                except Exception as e:
                    print(f"[!] Threads lỗi: {e}")

    if os.path.exists(banner):
        os.remove(banner)
    return True


def main():
    print("=" * 55)
    print("📣 FACEBOOK AUTO POSTER (độc lập) — lucas.vn")
    print("=" * 55)

    history = load_fb_history()
    print(f"[*] Đã đăng FB trước đó: {len(history)} sản phẩm")

    candidates = get_candidate_products()
    new = [p for p in candidates if p.get("link") and p["link"] not in history]
    print(f"[*] Sản phẩm chưa đăng FB: {len(new)}")

    if not new:
        print("[+] Không có sản phẩm mới để đăng FB hôm nay.")
        return

    posted = 0
    for prod in new:
        if posted >= FB_MAX_POSTS:
            break
        if post_one(prod):
            history.append(prod["link"])
            save_fb_history(history)   # lưu ngay sau mỗi bài (chống đăng trùng)
            posted += 1
            print(f"[+] Đã đăng FB: {prod['title']}")

    print(f"\n[+] Hoàn tất: đăng {posted} sản phẩm lên Facebook.")
    if posted == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
