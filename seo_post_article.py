#!/usr/bin/env python3
"""
seo_post_article.py
Nhận article JSON từ stdin, upload thumbnail, đăng lên WordPress, cập nhật history.
Usage: echo '<json>' | python3 seo_post_article.py
"""
import json, sys, base64, requests, os, time
from pathlib import Path
from dotenv import load_dotenv
from seo_make_thumbnail import create_seo_thumbnail

load_dotenv(Path(__file__).parent / ".env")

WP_SITE_URL     = os.getenv("WP_SITE_URL", "https://lucas.vn").rstrip("/")
WP_USERNAME     = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")
HISTORY_FILE    = Path(__file__).parent / "seo_history.json"
HEADERS_SCRAPE  = {"User-Agent": "Mozilla/5.0"}

def load_history():
    if HISTORY_FILE.exists():
        try: return json.loads(HISTORY_FILE.read_text())
        except: pass
    return []

def wp_auth():
    return "Basic " + base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASSWORD}".encode()).decode()

def upload_media_bytes(content, filename):
    try:
        resp = requests.post(
            f"{WP_SITE_URL}/wp-json/wp/v2/media",
            headers={
                "Authorization": wp_auth(),
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "image/png",
            },
            data=content, timeout=60
        )
        if resp.ok:
            return resp.json().get("id")
        print(f"[!] Media upload HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"[!] Upload ảnh lỗi: {e}", file=sys.stderr)
    return None

def make_and_upload_thumbnail(image_url, title, price, filename):
    """Tạo thumbnail branded 1200x630 từ ảnh sản phẩm rồi upload lên WP."""
    out_path = Path(__file__).parent / "seo_thumbnail_tmp.png"
    try:
        create_seo_thumbnail(image_url, title, str(out_path), price or "")
        data = out_path.read_bytes()
    except Exception as e:
        print(f"[!] Tạo thumbnail lỗi, fallback ảnh gốc: {e}", file=sys.stderr)
        try:
            data = requests.get(image_url, headers=HEADERS_SCRAPE, timeout=15).content
        except Exception as e2:
            print(f"[!] Tải ảnh gốc cũng lỗi: {e2}", file=sys.stderr)
            return None
    return upload_media_bytes(data, filename)

def post_to_wp(article, media_id):
    payload = {
        "title":   article["seo_title"],
        "content": article["content"],
        "slug":    article.get("slug", ""),
        "status":  "publish",
    }
    if media_id:
        payload["featured_media"] = media_id
    r = requests.post(
        f"{WP_SITE_URL}/wp-json/wp/v2/posts",
        headers={"Authorization": wp_auth(), "Content-Type": "application/json"},
        json=payload, timeout=30
    )
    if r.ok:
        return r.json()
    else:
        print(f"[!] WP error: {r.text[:300]}", file=sys.stderr)
        return None

# Đọc input JSON từ stdin
try:
    data = json.load(sys.stdin)
except Exception as e:
    print(f"ERROR: Không đọc được JSON input: {e}", file=sys.stderr)
    sys.exit(1)

article      = data["article"]
product_link = data["product_link"]
thumb_url    = data.get("thumbnail", "")
price        = data.get("price", "")

# Tạo + upload thumbnail branded 1200x630
media_id = None
if thumb_url:
    import re
    safe = re.sub(r'[^a-z0-9]+', '-', article['seo_title'].lower()).strip('-')[:40]
    fname = f"{safe or 'lucas-thumb'}-{int(time.time())}.png"
    media_id = make_and_upload_thumbnail(thumb_url, article['seo_title'], price, fname)
    print(f"[*] Thumbnail media_id={media_id}")

# Đăng bài
result = post_to_wp(article, media_id)
if result:
    # Lưu history
    history = load_history()
    history.append(product_link)
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2))
    print(f"SUCCESS|{result.get('id')}|{result.get('link')}")
else:
    print("ERROR: Đăng bài thất bại", file=sys.stderr)
    sys.exit(1)
