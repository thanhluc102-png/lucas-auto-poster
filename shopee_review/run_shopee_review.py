#!/usr/bin/env python3
"""
run_shopee_review.py — Job hằng sáng (GitHub Actions):
  1. shopee_reviews.daily(): nạp review mới có ảnh thật (Gemini duyệt) vào kho,
     chọn 1 ảnh cũ nhất (1/ngày), render card Shopee (Be Vietnam Pro).
  2. Đăng card lên Facebook (+ Instagram + Threads) — DÙNG LẠI tầng poster của repo
     (facebook_poster.py), KHÔNG đụng luồng đăng sản phẩm.

State (kho, seen, ngày đăng, token) nằm trong thư mục này, được workflow commit ngược lại.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)           # repo root (chứa facebook_poster.py)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import shopee_reviews
from facebook_poster import post_to_facebook, comment_on_post, post_to_instagram, post_to_threads

ENABLE_IG = os.getenv("FB_ENABLE_IG", "1") != "0"
ENABLE_THREADS = os.getenv("FB_ENABLE_THREADS", "1") != "0"
SHOP_URL = os.getenv("SHOPEE_SHOP_URL", "https://s.shopee.vn/70IBlq1v0D")


def build_caption(item):
    stars = "⭐" * int(item.get("stars") or 5)
    buyer = item.get("buyer") or "Khách hàng"
    text = (item.get("text") or "").strip()
    cat = (item.get("category") or "").split(",")[0].strip()   # gọn như trên card
    cat_line = f"\n🛍️ {cat}" if cat else ""
    return (f"{stars} {buyer} vừa để lại đánh giá cho Lucas trên Shopee!{cat_line}\n\n"
            f"“{text}”\n\n"
            f"Cảm ơn bạn đã tin tưởng Lucas Combo 🧡\n"
            f"#LucasCombo #Shopee #ĐánhGiáKháchHàng #Apple")


def main():
    item = shopee_reviews.daily()      # enqueue + post_today(render=True)
    if not item:
        print("[+] Không có card để đăng hôm nay (kho rỗng hoặc đã đăng).")
        return
    card = item.get("card_path")
    if not card or not os.path.exists(card):
        print("[!] Render card thất bại -> không đăng.")
        sys.exit(1)

    caption = build_caption(item)
    print(f"=== Đăng card Shopee review của {item.get('buyer')} ===")

    post_id = post_to_facebook(card, caption)
    if not post_id:
        print("[!] Đăng Facebook thất bại.")
        sys.exit(1)
    comment_on_post(post_id, f"👉 Ghé shop Lucas trên Shopee: {SHOP_URL}")

    # IG + Threads (cần public URL) — lỗi cũng không sao
    if ENABLE_IG or ENABLE_THREADS:
        try:
            from image_uploader import upload_image_to_wordpress
            public_url = upload_image_to_wordpress(card)
        except Exception as e:
            print(f"[!] Upload ảnh public lỗi: {e}")
            public_url = None
        if public_url:
            if ENABLE_IG:
                try:
                    post_to_instagram(public_url, caption)
                except Exception as e:
                    print(f"[!] IG lỗi: {e}")
            if ENABLE_THREADS:
                try:
                    post_to_threads(public_url, caption)
                except Exception as e:
                    print(f"[!] Threads lỗi: {e}")

    print("[+] Hoàn tất đăng card review Shopee.")


if __name__ == "__main__":
    main()
