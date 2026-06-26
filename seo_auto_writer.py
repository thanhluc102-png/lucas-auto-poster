#!/usr/bin/env python3
"""
seo_auto_writer.py
Tự động lấy sản phẩm mới từ danh mục Ulanzi trên lucas.vn,
dùng Claude AI viết bài SEO tiếng Việt, đăng thẳng lên WordPress.
"""

import os
import sys
import json
import time
import base64
import requests
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv

# Load .env từ cùng thư mục script
load_dotenv(Path(__file__).parent / ".env")

# ── Cấu hình ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
WP_SITE_URL       = os.getenv("WP_SITE_URL", "https://lucas.vn").rstrip("/")
WP_USERNAME       = os.getenv("WP_USERNAME")
WP_APP_PASSWORD   = os.getenv("WP_APP_PASSWORD")
CLAUDE_MODEL      = "claude-opus-4-8"

TARGET_URL        = os.getenv("TARGET_CATEGORY_URL") or "https://lucas.vn/thuong-hieu/lisen"
HISTORY_FILE      = Path(__file__).parent / "seo_history.json"
HEADERS_SCRAPE    = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg): print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []

def save_history(history: list):
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

# ── 1. Lấy danh sách sản phẩm Ulanzi ─────────────────────────────────────────

def get_target_products(pages: int = 3) -> list:
    from bs4 import BeautifulSoup
    results = []
    seen = set()
    for page in range(1, pages + 1):
        url = TARGET_URL if page == 1 else f"{TARGET_URL}/page/{page}"
        try:
            r = requests.get(url, headers=HEADERS_SCRAPE, timeout=15, allow_redirects=True)
            r.raise_for_status()
        except Exception as e:
            log(f"[!] Không truy cập được trang {page}: {e}")
            break
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.find_all("div", class_="product-small")
        if not items:
            break
        for item in items:
            a = item.find("a", href=True)
            title_tag = item.find(class_="product-title")
            img_tag = item.find("img")
            price_tag = item.find(class_="price")
            if not (a and title_tag):
                continue
            link = a["href"]
            if link in seen:
                continue
            seen.add(link)
            img = (img_tag.get("data-src") or img_tag.get("src", "")) if img_tag else ""
            # Dùng ảnh full-size thay vì thumbnail 300x300
            img = img.replace("-300x300", "")
            results.append({
                "title": title_tag.text.strip(),
                "link": link,
                "thumbnail": img,
                "price": price_tag.text.strip() if price_tag else "",
            })
        log(f"[*] Trang {page}: tìm thấy {len(items)} sản phẩm")
    return results

# ── 2. Scrape chi tiết sản phẩm ───────────────────────────────────────────────

def scrape_product_detail(url: str) -> dict:
    from bs4 import BeautifulSoup
    try:
        r = requests.get(url, headers=HEADERS_SCRAPE, timeout=15, allow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Mô tả ngắn
        short_desc = soup.find(class_="woocommerce-product-details__short-description")
        short_text = short_desc.get_text(" ", strip=True)[:500] if short_desc else ""

        # Mô tả dài (tab)
        long_desc = soup.find(id="tab-description") or soup.find(class_="woocommerce-Tabs-panel--description")
        long_text = long_desc.get_text(" ", strip=True)[:1000] if long_desc else ""

        # Gallery ảnh
        gallery = []
        for a in soup.select(".woocommerce-product-gallery__image a"):
            href = a.get("href", "")
            if href and href.startswith("http"):
                gallery.append(href)

        return {
            "short_desc": short_text,
            "long_desc": long_text,
            "gallery": gallery[:5],
        }
    except Exception as e:
        log(f"[!] Lỗi scrape chi tiết {url}: {e}")
        return {"short_desc": "", "long_desc": "", "gallery": []}

# ── 3. Dùng Claude viết bài SEO ───────────────────────────────────────────────

def write_seo_article(product: dict, detail: dict) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""Bạn là chuyên gia SEO content tiếng Việt cho trang thương mại điện tử lucas.vn.
Hãy viết bài review/giới thiệu sản phẩm chuẩn SEO để đăng lên WordPress.

Thông tin sản phẩm:
- Tên: {product['title']}
- Giá: {product.get('price', 'Liên hệ')}
- Link: {product['link']}
- Mô tả ngắn: {detail.get('short_desc', '')}
- Mô tả đầy đủ: {detail.get('long_desc', '')}

Yêu cầu BẮT BUỘC — Trả về DUY NHẤT một JSON hợp lệ, không có text ngoài JSON:
{{
  "seo_title": "Tiêu đề bài viết 55-60 ký tự, có từ khóa chính, hấp dẫn",
  "meta_description": "Meta description 150-160 ký tự, tóm tắt lợi ích chính",
  "focus_keyword": "Từ khóa SEO chính (ví dụ: Ulanzi D200X)",
  "slug": "slug-url-tieng-viet-khong-dau",
  "content": "Nội dung HTML đầy đủ của bài viết (ít nhất 800 từ). Dùng thẻ <h2>, <h3>, <p>, <ul>, <li>. KHÔNG dùng <html><body><head>. Bao gồm: giới thiệu, tính năng nổi bật, thông số kỹ thuật, đối tượng phù hợp, kết luận. Chèn từ khóa tự nhiên. Cuối bài BẮT BUỘC tạo 1 Khối Card Mua Hàng (Product Card) bằng HTML với style CSS inline đẹp mắt (viền bo tròn, bóng đổ, màu sắc nổi bật), hiển thị Tên sản phẩm, Giá bán và một Nút (Button) '🛒 MUA NGAY'. Link mua hàng: {product['link']}. Giá bán: {product.get('price', 'Liên hệ')}."
}}"""

    log(f"[*] Đang nhờ Claude viết bài cho: {product['title'][:50]}...")
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        # Tách JSON an toàn
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            raw = match.group(0)
        return json.loads(raw)
    except json.JSONDecodeError as e:
        log(f"[!] Lỗi parse JSON từ Claude: {e}")
        return None
    except Exception as e:
        log(f"[!] Lỗi gọi Claude: {e}")
        return None

# ── 4. Tạo thumbnail bằng Pillow ──────────────────────────────────────────────

# (Đã chuyển sang dùng create_seo_thumbnail từ seo_make_thumbnail.py)

# ── 5. Upload media lên WordPress ─────────────────────────────────────────────

def upload_media_to_wp(image_path: str, filename: str) -> int | None:
    url = f"{WP_SITE_URL}/wp-json/wp/v2/media"
    auth = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASSWORD}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Disposition": f"attachment; filename={filename}",
        "Content-Type": "image/png",
    }
    try:
        with open(image_path, "rb") as f:
            r = requests.post(url, headers=headers, data=f, timeout=30)
        r.raise_for_status()
        media_id = r.json().get("id")
        log(f"[*] Upload ảnh thành công, media_id={media_id}")
        return media_id
    except Exception as e:
        log(f"[!] Lỗi upload ảnh: {e}")
        return None

# ── 6. Chèn ảnh gallery vào nội dung bài viết ────────────────────────────────

def inject_images_into_content(content: str, gallery_urls: list) -> str:
    """Rải ảnh từ gallery vào giữa các đoạn <p> trong bài viết."""
    if not gallery_urls:
        return content

    # Tách đoạn
    paragraphs = re.split(r'(<h[23][^>]*>.*?</h[23]>)', content, flags=re.DOTALL)
    interval = max(1, len(paragraphs) // (len(gallery_urls) + 1))

    result = []
    img_idx = 0
    for i, part in enumerate(paragraphs):
        result.append(part)
        if img_idx < len(gallery_urls) and (i + 1) % interval == 0:
            url = gallery_urls[img_idx]
            result.append(
                f'\n<figure class="wp-block-image size-large">'
                f'<img src="{url}" alt="" loading="lazy"/></figure>\n'
            )
            img_idx += 1

    return "".join(result)

# ── 7. Đăng bài lên WordPress ─────────────────────────────────────────────────

def publish_to_wordpress(article: dict, featured_media_id: int | None, product_link: str) -> str | None:
    url = f"{WP_SITE_URL}/wp-json/wp/v2/posts"
    auth = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASSWORD}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
    }

    # Yoast SEO meta (nếu plugin hỗ trợ REST)
    payload = {
        "title":   article["seo_title"],
        "content": article["content"],
        "slug":    article.get("slug", ""),
        "status":  "publish",
        "meta": {
            "_yoast_wpseo_title":           article.get("seo_title", ""),
            "_yoast_wpseo_metadesc":        article.get("meta_description", ""),
            "_yoast_wpseo_focuskw":         article.get("focus_keyword", ""),
        },
    }
    if featured_media_id:
        payload["featured_media"] = featured_media_id

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        post_url = r.json().get("link", "")
        post_id  = r.json().get("id", "")
        log(f"[+] Đăng bài thành công! ID={post_id}, URL={post_url}")
        return post_url
    except Exception as e:
        log(f"[!] Lỗi đăng bài lên WordPress: {e}")
        if hasattr(e, "response") and e.response is not None:
            log(f"    Response: {e.response.text[:300]}")
        return None

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🚀 SEO AUTO WRITER — LUCAS.VN / ULANZI")
    print("=" * 60)

    if not all([ANTHROPIC_API_KEY, WP_USERNAME, WP_APP_PASSWORD]):
        log("[!] Thiếu biến môi trường. Kiểm tra file .env")
        sys.exit(1)

    # 1. Đọc lịch sử
    history = load_history()
    log(f"[*] Lịch sử: {len(history)} sản phẩm đã đăng")

    # 2. Lấy danh sách sản phẩm
    products = get_target_products(pages=3)
    if not products:
        log("[-] Không lấy được sản phẩm nào từ danh mục")
        sys.exit(0)

    # 3. Lọc sản phẩm mới
    new_products = [p for p in products if p["link"] not in history]
    log(f"[*] Sản phẩm mới chưa đăng: {len(new_products)}")

    if not new_products:
        print("\n✅ Không có sản phẩm mới hôm nay")
        sys.exit(0)

    # Chỉ xử lý 1 sản phẩm mỗi lần chạy (theo scheduled task)
    product = new_products[0]
    log(f"[*] Sản phẩm sẽ đăng: {product['title']}")

    # 4. Scrape chi tiết
    detail = scrape_product_detail(product["link"])

    # 5. Claude viết bài SEO
    article = write_seo_article(product, detail)
    if not article:
        log("[!] Không tạo được nội dung bài viết. Dừng.")
        sys.exit(1)

    # 6. Chèn ảnh gallery vào bài
    if detail.get("gallery"):
        article["content"] = inject_images_into_content(
            article["content"], detail["gallery"]
        )

    # 7. Tạo thumbnail bằng template chuẩn SEO
    from seo_make_thumbnail import create_seo_thumbnail
    tmp_path = f"/tmp/seo_thumb_{int(time.time())}.png"
    thumb_ok = create_seo_thumbnail(product["thumbnail"], product["title"], tmp_path, kicker="PHỤ KIỆN LISEN")

    # 8. Upload thumbnail lên WordPress
    media_id = None
    if thumb_ok:
        safe_name = re.sub(r'[^a-z0-9]', '-', product['title'].lower())[:40]
        media_id = upload_media_to_wp(tmp_path, f"{safe_name}-thumbnail.png")
        # Dọn file tạm
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    # 9. Đăng bài lên WordPress
    post_url = publish_to_wordpress(article, media_id, product["link"])

    if post_url:
        # 10. Cập nhật lịch sử
        history.append(product["link"])
        save_history(history)
        print(f"\n✅ Đăng thành công!")
        print(f"   Bài viết: {article['seo_title']}")
        print(f"   Link:     {post_url}")
    else:
        log("[!] Đăng bài thất bại")
        sys.exit(1)

if __name__ == "__main__":
    main()
