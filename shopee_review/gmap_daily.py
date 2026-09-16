#!/usr/bin/env python3
"""Mỗi ngày đăng 1 card đánh giá Google (cũ) lên Facebook.

  python3 shopee_review/gmap_daily.py            # đăng thật
  python3 shopee_review/gmap_daily.py --dry-run  # render card, KHÔNG đăng

Bốc từ gmap_pool.json (kho review cũ đã kéo sẵn), bỏ cái đã đăng, render card BẰNG
CHÍNH bộ dựng của shopee (shopee_card.render_card) cho đồng bộ thương hiệu, rồi đăng
qua facebook_poster của repo. Không gọi Google API — kho đã commit sẵn.
"""
import os, sys, json, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except Exception:
    pass

import shopee_card
from facebook_poster import post_to_facebook, comment_on_post

POOL = os.path.join(HERE, "gmap_pool.json")
SEEN = os.path.join(HERE, "gmap_seen.json")        # id review đã đăng
STATE = os.path.join(HERE, "gmap_post_state.json") # ngày đăng gần nhất
DRY = "--dry-run" in sys.argv


def _load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def build_caption(rv):
    # Ghi RÕ năm thật — review cũ, không giả tươi. "Nhìn lại" là khung trung thực.
    return (f"⭐ Nhìn lại đánh giá của khách năm {rv['year']} 💙\n\n"
            f"\"{rv['text']}\"\n— {rv['buyer']}\n\n"
            f"Cảm ơn anh/chị đã tin tưởng Lucas Combo. "
            f"Ghé lucas.vn hoặc cửa hàng để được tư vấn phụ kiện Apple chính hãng nhé!\n"
            f"#LucasCombo #Apple #đánhgiákháchhàng")


def main():
    today = datetime.date.today().isoformat()
    st = _load(STATE, {})
    if st.get("last_post_date") == today and not DRY:
        print(f"[+] Hôm nay ({today}) đã đăng 1 card Google review rồi. Bỏ qua.")
        return

    pool = _load(POOL, {}).get("reviews", [])
    if not pool:
        print("[!] Kho gmap_pool.json rỗng — chạy gmap_build_pool.py trước.")
        sys.exit(1)

    seen = set(_load(SEEN, []))
    nxt = next((r for r in pool if r["id"] not in seen), None)
    if not nxt:
        # Hết vòng (đã đăng cả 956 cái, ~3 năm) -> quay lại từ đầu
        print("[*] Đã đăng hết kho, quay vòng lại từ review cũ nhất.")
        seen = set()
        nxt = pool[0]

    print(f"=== Card Google review {nxt['date']} ⭐{nxt['stars']} — {nxt['buyer']} ===")
    print(f"    \"{nxt['text'][:80]}\"")

    card = os.path.join(HERE, f"gmap_card_{nxt['id']}.jpg")
    shopee_card.render_card({
        "buyer": nxt["buyer"],
        "stars": nxt["stars"],
        "text": nxt["text"],
        "category": f"Đánh giá thật · {nxt['year']}",         # năm hiện ngay trên card
        "image": None,                                        # review Google không có ảnh sp
        "badge": "✓ Khách đã mua",
        "footer": "Khách hàng đánh giá trên Google Maps",     # đúng nguồn, không phải Shopee
    }, card)
    if not os.path.exists(card):
        print("[!] Render card thất bại -> không đăng.")
        sys.exit(1)

    caption = build_caption(nxt)
    if DRY:
        print(f"[DRY-RUN] đã render {card}, KHÔNG đăng.\n---\n{caption}")
        return

    res = post_to_facebook(card, caption)
    post_id = res.get("post_id") or res.get("id") if isinstance(res, dict) else res
    if not post_id:
        print(f"[!] Đăng FB thất bại: {res}")
        sys.exit(1)
    print(f"[+] Đã đăng FB: {post_id}")

    seen.add(nxt["id"])
    json.dump(sorted(seen), open(SEEN, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump({"last_post_date": today, "last_id": nxt["id"]},
              open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
    try:
        os.remove(card)          # card đã lên FB, không cần giữ file
    except OSError:
        pass


if __name__ == "__main__":
    main()
