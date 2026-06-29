"""
shopee_reviews.py — Lấy đánh giá (comment) sản phẩm Shopee qua Open Platform API
                    để lọc đánh giá mới rồi đẩy sang social.

API: GET /api/v2/product/get_comment  (nhóm quyền "Product")
  -> trả về item_comment_list: comment, rating_star, buyer_username, item_id,
     order_sn, ctime, comment_id, ...

Luồng:
  1. fetch_all_comments() : phân trang (cursor) lấy toàn bộ comment hiện có
  2. get_new_reviews()    : lọc comment CHƯA thấy (state file) + rating >= MIN_STAR
                            + có nội dung -> trả list dict sẵn sàng đăng social
  3. CLI: in JSON các đánh giá mới, đồng thời cập nhật state để hôm sau không lặp.

Token tự refresh giống shopee_video.py. DÙNG CHUNG token file, NHƯNG token đó
phải thuộc app "Seller In House" (có quyền Product). Xem hướng dẫn cuối file.
"""
import os
import re
import time
import json
import hmac
import hashlib
import requests

# ---- App "Seller In House" — bộ LIVE (chạy trên partner.shopeemobile.com) ----
# PARTNER_KEY ưu tiên lấy từ GitHub Secret SHOPEE_PARTNER_KEY (cloud), fallback local.
PARTNER_ID = int(os.getenv("SHOPEE_PARTNER_ID", "2037669"))
PARTNER_KEY = os.getenv(
    "SHOPEE_PARTNER_KEY",
    "shpk6b76526d7149626174745a6a4b4b7a466d4862734e547041426b486d6363").encode()
HOST = "https://partner.shopeemobile.com"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(BASE_DIR, "shopee_token.json")
SEEN_FILE = os.path.join(BASE_DIR, "shopee_reviews_seen.json")
QUEUE_FILE = os.path.join(BASE_DIR, "shopee_review_queue.json")   # ảnh chờ đăng dần
POST_STATE_FILE = os.path.join(BASE_DIR, "shopee_post_state.json")  # ngày đăng gần nhất

MIN_STAR = 4          # chỉ đăng đánh giá >= 4 sao
PAGE_SIZE = 100       # tối đa Shopee cho phép
MAX_VET_PER_RUN = 25  # trần số ảnh gọi Gemini mỗi lần (tránh đốt quota lần đầu)


# ============ TOKEN (giống shopee_video.py) ============
def _load_token():
    with open(TOKEN_FILE) as f:
        return json.load(f)


def _save_token(data):
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _refresh_access_token(tok):
    path = "/api/v2/auth/access_token/get"
    ts = int(time.time())
    base = f"{PARTNER_ID}{path}{ts}".encode()
    sign = hmac.new(PARTNER_KEY, base, hashlib.sha256).hexdigest()
    url = f"{HOST}{path}?partner_id={PARTNER_ID}&timestamp={ts}&sign={sign}"
    payload = {
        "refresh_token": tok["refresh_token"],
        "partner_id": PARTNER_ID,
        "shop_id": int(tok["shop_id"]),
    }
    r = requests.post(url, json=payload).json()
    if not r.get("access_token"):
        raise RuntimeError(f"Refresh token thất bại: {r}")
    tok["access_token"] = r["access_token"]
    tok["refresh_token"] = r.get("refresh_token", tok["refresh_token"])
    tok["_obtained_at"] = ts
    _save_token(tok)
    print("🔄 Đã refresh access_token mới.")
    return tok


def _get_valid_token():
    tok = _load_token()
    obtained = tok.get("_obtained_at", 0)
    expire_in = tok.get("expire_in", 14400)
    if time.time() - obtained > expire_in - 300:
        tok = _refresh_access_token(tok)
    return tok


# ============ SIGNATURE cấp shop ============
def _shop_get(path, tok, extra_params=None):
    ts = int(time.time())
    access_token = tok["access_token"]
    shop_id = int(tok["shop_id"])
    base = f"{PARTNER_ID}{path}{ts}{access_token}{shop_id}".encode()
    sign = hmac.new(PARTNER_KEY, base, hashlib.sha256).hexdigest()
    params = {
        "partner_id": PARTNER_ID,
        "timestamp": ts,
        "access_token": access_token,
        "shop_id": shop_id,
        "sign": sign,
    }
    if extra_params:
        params.update(extra_params)
    r = requests.get(f"{HOST}{path}", params=params)
    return r.json()


# ============ GET COMMENT ============
def fetch_all_comments(item_id=None):
    """Phân trang lấy toàn bộ comment của shop (hoặc 1 item nếu truyền item_id)."""
    path = "/api/v2/product/get_comment"
    comments = []
    cursor = ""
    while True:
        tok = _get_valid_token()
        extra = {"cursor": cursor, "page_size": PAGE_SIZE}
        if item_id:
            extra["item_id"] = int(item_id)
        res = _shop_get(path, tok, extra)
        if res.get("error"):
            raise RuntimeError(f"get_comment lỗi: {res}")
        data = res.get("response", {})
        comments.extend(data.get("item_comment_list", []))
        cursor = data.get("next_cursor", "")
        if not data.get("more") or not cursor:
            break
        time.sleep(0.3)
    return comments


# ============ TÊN SẢN PHẨM (cho "Phân loại hàng") ============
ITEM_NAME_FILE = os.path.join(BASE_DIR, "shopee_item_names.json")
_item_name_cache = None


def get_item_name(item_id):
    """item_id -> item_name (get_item_base_info), có cache file. Lỗi -> ''."""
    global _item_name_cache
    if _item_name_cache is None:
        _item_name_cache = {}
        if os.path.exists(ITEM_NAME_FILE):
            with open(ITEM_NAME_FILE) as f:
                _item_name_cache = json.load(f)
    key = str(item_id)
    if key in _item_name_cache:
        return _item_name_cache[key]
    name = ""
    try:
        tok = _get_valid_token()
        res = _shop_get("/api/v2/product/get_item_base_info", tok,
                        {"item_id_list": key})
        items = res.get("response", {}).get("item_list", [])
        if items:
            name = items[0].get("item_name", "") or ""
    except Exception:
        name = ""
    _item_name_cache[key] = name
    with open(ITEM_NAME_FILE, "w") as f:
        json.dump(_item_name_cache, f, ensure_ascii=False, indent=2)
    return name


# ============ LỌC CHẤT LƯỢNG (tầng 1: text) ============
# Từ khoá cày xu / quảng cáo cài cắm -> chặn cứng.
SPAM_KEYWORDS = [
    "nhận xu", "nhan xu", "săn xu", "san xu", "shopee xu", "đánh giá để", "danh gia de",
    "klq", "ko liên quan", "không liên quan", "k liên quan", "kg liên quan",
    "đánh giá nhận", "5 sao nhận", "review nhận", "đánh giá lấy", "cho đủ kí tự",
    "đủ kí tự", "du ki tu", "cho đủ chữ", "spam", "tích điểm",
    # quảng cáo / chèo kéo
    "học phí", "khóa học", "tuyển sinh", "tuyển dụng", "việc làm", "tuyển ctv",
    "kiếm tiền", "thu nhập", "quỹ", "từ thiện", "ủng hộ", "vay tiền", "vay vốn",
    "đầu tư", "chứng khoán", "hotline", "zalo", "kết bạn", "liên hệ", "ib mình",
    "inbox", "nhắn tin", "fanpage", "fb.com", "facebook.com",
]
# Tín hiệu tích cực: nói về sản phẩm / mua bán.
PRODUCT_HINTS = [
    "sản phẩm", "san pham", "shop", "giao hàng", "giao hang", "đóng gói", "dong goi",
    "chất lượng", "chat luong", "đúng mô tả", "dung mo ta", "dùng", "xài", "đẹp",
    "ok", "oke", "ưng", "hài lòng", "chắc chắn", "giá", "ship", "nhanh", "mượt",
    "bền", "xịn", "tốt", "tot", "đáng tiền", "recommend", "đáng mua", "kết nối",
]
_PHONE_RE = re.compile(r"(?:0|\+84)\d[\d\s.\-]{7,}\d")
_URL_RE = re.compile(r"(https?://|www\.|\.com|\.vn|\.net|t\.me/|bit\.ly)", re.I)
_EMAIL_RE = re.compile(r"[\w.\-]+@[\w.\-]+")


def classify_text(text):
    """Trả (keep: bool, reason: str). Chặn cứng spam/quảng cáo, giữ review sản phẩm."""
    t = text.lower().strip()
    if len(t) < 12:
        return False, "quá ngắn"
    if _PHONE_RE.search(t):
        return False, "chứa số điện thoại"
    if _URL_RE.search(t):
        return False, "chứa link"
    if _EMAIL_RE.search(t):
        return False, "chứa email"
    for kw in SPAM_KEYWORDS:
        if kw in t:
            return False, f"từ khoá cấm: '{kw}'"
    # quảng cáo thường có nhiều dòng gạch đầu / emoji checklist
    if t.count("✅") + t.count("👉") + t.count("🎓") + t.count("🆘") >= 3:
        return False, "nghi quảng cáo (emoji checklist)"
    # phải có ít nhất 1 tín hiệu liên quan sản phẩm
    if not any(h in t for h in PRODUCT_HINTS):
        return False, "không nhắc tới sản phẩm"
    return True, "ok"


# ============ LỌC CHẤT LƯỢNG (tầng 2: ảnh bằng Gemini vision) ============
_gemini = None


def _get_gemini():
    global _gemini
    if _gemini is None:
        try:
            from dotenv import load_dotenv
            load_dotenv(os.path.join(BASE_DIR, ".env"))
        except Exception:
            pass
        from google import genai
        key = os.getenv("GEMINI_API_KEY") or "AIzaSyBUEoG7WDvSEIctEqxg9J_9lttBqak2ia8"
        _gemini = genai.Client(api_key=key)
    return _gemini


_VISION_PROMPT = """Bạn đang lọc ảnh đánh giá Shopee để đăng lên mạng xã hội.
Phân loại tấm ảnh:
- "real": khách tự chụp sản phẩm/đơn hàng thật ngoài đời (trên bàn, trên tay, có tem ship, bao bì thật...).
- "junk": KHÔNG dùng được — chụp màn hình app, ảnh nhạc/phim, meme, ảnh chữ/poster quảng cáo, ảnh catalog shop tự up, ảnh mờ hỏng hoặc không liên quan sản phẩm.
Chỉ trả JSON: {"verdict":"real|junk","reason":"ngắn gọn tiếng Việt"}"""


def vet_image(url, *, timeout=15):
    """Tải ảnh + hỏi Gemini. Trả (genuine: bool|None, reason: str)."""
    try:
        img = requests.get(url, timeout=timeout).content
    except Exception as e:
        return None, f"tải ảnh lỗi: {e}"
    try:
        from google.genai import types
        out = _get_gemini().models.generate_content(
            model="gemini-2.5-flash",
            contents=[_VISION_PROMPT,
                      types.Part.from_bytes(data=img, mime_type="image/jpeg")],
        )
        m = re.search(r"\{.*\}", (out.text or "").strip(), re.S)
        data = json.loads(m.group(0)) if m else {"verdict": "junk", "reason": "no-json"}
        return data.get("verdict") == "real", data.get("reason", "")
    except Exception as e:
        return None, f"gemini lỗi: {e}"


# ============ STATE: comment đã xử lý ============
def _load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def _save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f)


def get_new_reviews(min_star=MIN_STAR, item_id=None, mark_seen=True,
                    quality=True, vet_images=True):
    """Trả các đánh giá MỚI (chưa thấy) đạt chuẩn để đăng social.

    quality=True   : lọc text (classify_text) bỏ review cày xu/quảng cáo.
    vet_images=True: với review có ảnh, gọi Gemini chấm ảnh thật/rác.
                     -> real_images: chỉ những ảnh đã xác thực thật.
                     -> tier: "rich" (text sạch + ảnh thật) | "good" (sạch, không ảnh thật).
    """
    seen = _load_seen()
    out = []
    for c in fetch_all_comments(item_id=item_id):
        cid = str(c.get("comment_id"))
        if cid in seen:
            continue
        seen.add(cid)
        star = c.get("rating_star", 0)
        text = (c.get("comment") or "").strip()
        if star < min_star or not text:
            continue
        if quality:
            keep, reason = classify_text(text)
            if not keep:
                continue
        media = c.get("media") or {}
        images = media.get("image_url_list", [])
        real_images = images
        if vet_images and images:
            real_images = [u for u in images if vet_image(u)[0]]
        out.append({
            "comment_id": cid,
            "item_id": c.get("item_id"),
            "order_sn": c.get("order_sn"),
            "buyer": c.get("buyer_username"),
            "stars": star,
            "text": text,
            "ctime": c.get("create_time"),
            "images": images,
            "real_images": real_images,
            "videos": media.get("video_url_list", []),
            "tier": "rich" if real_images else "good",
        })
    if mark_seen:
        _save_seen(seen)
    return out


# ============ HÀNG ĐỢI: tích trữ ảnh, đăng dần 1/sáng ============
def _load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def _dump_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def enqueue_new(max_vet=MAX_VET_PER_RUN):
    """Quét comment MỚI, chỉ giữ review có ẢNH THẬT (Gemini duyệt), nạp vào hàng đợi.
    Giới hạn max_vet ảnh/lần để không đốt quota; comment chưa xử lý để lần sau."""
    seen = _load_seen()
    queue = _load_json(QUEUE_FILE, [])
    queued_ids = {item["comment_id"] for item in queue}
    vetted = added = 0

    for c in fetch_all_comments():
        if vetted >= max_vet:
            break
        cid = str(c.get("comment_id"))
        if cid in seen or cid in queued_ids:
            continue
        star = c.get("rating_star", 0)
        text = (c.get("comment") or "").strip()
        images = (c.get("media") or {}).get("image_url_list", [])
        if star < MIN_STAR or not text or not images:
            continue
        if not classify_text(text)[0]:
            seen.add(cid)              # text rác -> đánh dấu xong luôn
            continue
        # còn ngân sách -> duyệt ảnh
        real_images = []
        for u in images:
            if vetted >= max_vet:
                break
            vetted += 1
            if vet_image(u)[0]:
                real_images.append(u)
        seen.add(cid)
        if real_images:
            queue.append({
                "comment_id": cid, "item_id": c.get("item_id"),
                "buyer": c.get("buyer_username"), "stars": star,
                "text": text, "ctime": c.get("create_time"),
                "image": real_images[0], "all_real_images": real_images,
                "category": get_item_name(c.get("item_id")),
            })
            added += 1

    _save_seen(seen)
    _dump_json(QUEUE_FILE, queue)
    print(f"📥 Đã duyệt {vetted} ảnh, thêm {added} review vào hàng đợi. "
          f"Tồn kho: {len(queue)}.")
    return added


def post_today(force=False, render=True):
    """Lấy ĐÚNG 1 ảnh cũ nhất trong hàng đợi để đăng — mỗi ngày chỉ 1 lần.
    render=True: dựng luôn ảnh card Shopee (shopee_card.py) -> item['card_path']."""
    import datetime
    today = datetime.date.today().isoformat()
    state = _load_json(POST_STATE_FILE, {})
    if not force and state.get("last_post_date") == today:
        print("⏸️  Hôm nay đã đăng rồi (Shopee). Để dành mai.")
        return None
    queue = _load_json(QUEUE_FILE, [])
    if not queue:
        print("📭 Hàng đợi Shopee rỗng — chưa có ảnh để đăng.")
        return None
    item = queue.pop(0)               # FIFO: cũ nhất trước
    _dump_json(QUEUE_FILE, queue)
    state["last_post_date"] = today
    _dump_json(POST_STATE_FILE, state)

    if not item.get("category"):       # backfill cho item cũ trong kho
        item["category"] = get_item_name(item.get("item_id"))

    if render:
        try:
            import shopee_card
            out = os.path.join(BASE_DIR, f"shopee_card_{today}.png")
            item["card_path"] = shopee_card.render_card(item, out)
            print(f"🖼️  Đã render card: {item['card_path']}")
        except Exception as e:
            print(f"⚠️  Render card lỗi: {e}")

    print(f"📤 Ảnh hôm nay (Shopee) — còn lại {len(queue)} trong kho:")
    print(json.dumps(item, ensure_ascii=False, indent=2))
    return item


def daily(force=False):
    """Chạy mỗi sáng: nạp ảnh mới vào kho rồi đăng 1 ảnh."""
    enqueue_new()
    return post_today(force=force)


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "daily"
    if cmd == "enqueue":
        enqueue_new()
    elif cmd == "post":
        post_today(force="--force" in sys.argv)
    else:  # daily
        daily(force="--force" in sys.argv)

# ─────────────────────────────────────────────────────────────────────────────
# CÁCH DÙNG
#   python shopee_reviews.py enqueue   # chỉ nạp ảnh mới vào hàng đợi
#   python shopee_reviews.py post      # lấy 1 ảnh để đăng (1 lần/ngày)
#   python shopee_reviews.py           # daily = enqueue + post 1 ảnh (dùng cho cron)
#   thêm --force để bỏ qua khoá "đã đăng hôm nay".
# State: shopee_review_queue.json (kho ảnh chờ), shopee_post_state.json (ngày đăng),
#        shopee_reviews_seen.json (comment đã xử lý).
# ─────────────────────────────────────────────────────────────────────────────
