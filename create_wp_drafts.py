import csv
import os
import requests
import json
import re
import base64
from base64 import b64encode
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import anthropic

# Load credentials from .env (fallback to environment variables)
from dotenv import load_dotenv
load_dotenv()

WP_URL = os.getenv('WP_SITE_URL', 'https://lucas.vn').strip().strip('"').strip("'")
WP_USER = os.getenv('WP_USERNAME').strip().strip('"').strip("'")
WP_PASSWORD = os.getenv('WP_APP_PASSWORD').strip().strip('"').strip("'")
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-opus-4-8')

if not all([WP_URL, WP_USER, WP_PASSWORD]):
    raise RuntimeError(f'WordPress credentials not fully set in .env: WP_SITE_URL={WP_URL}, WP_USERNAME={WP_USER}')

CSV_PATH = os.path.abspath('content_plan.csv')
LOG_PATH = os.path.abspath('logs/create_wp_drafts.log')
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

HEADERS_SCRAPE = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def log(message: str):
    print(message)
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(message + '\n')

def get_brand_kicker(title):
    title_lower = title.lower()
    BRANDS = {
        'lisen': 'THƯƠNG HIỆU LISEN',
        'aulumu': 'THƯƠNG HIỆU AULUMU',
        'inateck': 'THƯƠNG HIỆU INATECK',
        'thule': 'THƯƠNG HIỆU THULE',
        'ulanzi': 'PHỤ KIỆN ULANZI',
        'wiwu': 'THƯƠNG HIỆU WIWU',
        'hyperwork': 'PHỤ KIỆN HYPERWORK',
        'anker': 'PHỤ KIỆN ANKER',
        'sharge': 'THƯƠNG HIỆU SHARGE',
        'tomtoc': 'PHỤ KIỆN TOMTOC',
        'spigen': 'ỐP LƯNG SPIGEN',
        'moft': 'PHỤ KIỆN MOFT',
        'zagg': 'THƯƠNG HIỆU ZAGG'
    }
    for b, kicker in BRANDS.items():
        if b in title_lower:
            return kicker
    return "PHỤ KIỆN CAO CẤP"

def scrape_product_detail(url):
    # Ưu tiên WooCommerce REST API (mô tả/gallery/giá chuẩn), fallback scrape HTML
    try:
        import wc_api
        if wc_api.enabled():
            d = wc_api.detail_from_link(url)
            if d:
                log(f"[*] Lấy chi tiết qua WooCommerce API: {url}")
                return d
    except Exception as e:
        log(f"[!] WC API lỗi, fallback scrape HTML: {e}")

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

        # Lấy giá sản phẩm nếu có
        price_tag = soup.find(class_="woocommerce-Price-amount")
        price = price_tag.get_text(" ", strip=True) if price_tag else "Liên hệ"

        return {
            "short_desc": short_text,
            "long_desc": long_text,
            "gallery": gallery[:5],
            "price": price
        }
    except Exception as e:
        log(f"[!] Lỗi scrape chi tiết {url}: {e}")
        return {"short_desc": "", "long_desc": "", "gallery": [], "price": "Liên hệ"}

def write_seo_article(product_title, product_link, price, detail):
    if not ANTHROPIC_API_KEY:
        log("[!] ANTHROPIC_API_KEY is not set.")
        return None
        
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    prompt = f"""Bạn là chuyên gia SEO content tiếng Việt cho trang thương mại điện tử lucas.vn.
Hãy viết bài review/giới thiệu sản phẩm chuẩn SEO để đăng lên WordPress.

Thông tin sản phẩm:
- Tên: {product_title}
- Giá: {price}
- Link: {product_link}
- Mô tả ngắn: {detail.get('short_desc', '')}
- Mô tả đầy đủ: {detail.get('long_desc', '')}

Phong cách tiêu đề mẫu (giật tít, kích thích tò mò, vẫn chứa từ khóa):
- "Đế Sạc 4-in-1 Aulumu M01: Tiền Nào Của Nấy, Có Thực Sự Đỉnh?"
- "Giá Đỡ AULUMU G09 MagSafe: Có Đáng Cho Dân Chơi Công Nghệ?"
- "Đánh Giá Ốp iPhone 17 Aulumu Aramid Fiber: Mỏng, Nhẹ Có Đủ Bảo Vệ?"

Yêu cầu BẮT BUỘC — Trả về DUY NHẤT một JSON hợp lệ, không có text ngoài JSON:
{{
  "seo_title": "Tiêu đề 55-65 ký tự theo đúng phong cách mẫu ở trên: CỰC giật tít, kích thích tò mò/đặt câu hỏi, thôi thúc click ngay, NHƯNG bắt buộc chứa từ khóa chính (tên/thương hiệu + loại sản phẩm) để chuẩn SEO. Không bọc dấu ngoặc kép ngoài cùng",
  "meta_description": "Meta description 150-160 ký tự, tóm tắt lợi ích chính",
  "focus_keyword": "Từ khóa SEO chính (ví dụ: Ulanzi D200X)",
  "slug": "slug-url-tieng-viet-khong-dau",
  "tags": ["Tên thương hiệu", "Loại sản phẩm", "Tính năng nổi bật 1", "Tính năng nổi bật 2"],
  "content": "Nội dung HTML đầy đủ của bài viết (ít nhất 800 từ). Dùng thẻ <h2>, <h3>, <p>, <ul>, <li>. KHÔNG dùng <html><body><head>. Bao gồm: giới thiệu, tính năng nổi bật, thông số kỹ thuật, đối tượng phù hợp, kết luận. Chèn từ khóa tự nhiên. KẾT THÚC bằng đoạn kết luận — TUYỆT ĐỐI KHÔNG tự tạo card/box/nút mua hàng (hệ thống sẽ tự chèn khối Card Mua Hàng có ảnh sản phẩm ở cuối bài)."
}}"""

    log(f"[*] Đang nhờ Claude viết bài cho: {product_title[:50]}...")
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            raw = match.group(0)
        return json.loads(raw)
    except Exception as e:
        log(f"[!] Lỗi gọi Claude hoặc parse JSON: {e}")
        return None

def inject_images_into_content(content: str, gallery_urls: list) -> str:
    """Rải ảnh từ gallery vào giữa các đoạn <p> trong bài viết."""
    if not gallery_urls:
        return content
    # Tìm các thẻ </p> để chèn ảnh sau đó
    paragraphs = [m.start() for m in re.finditer(r'</p>', content)]
    if not paragraphs:
        return content

    offset = 0
    step = max(1, len(paragraphs) // (len(gallery_urls) + 1))
    
    for i, img_url in enumerate(gallery_urls):
        idx = (i + 1) * step
        if idx >= len(paragraphs):
            break
        pos = paragraphs[idx] + offset
        img_html = (
            f'\n<figure class="wp-block-image size-large">'
            f'<img src="{img_url}" alt="Hình ảnh chi tiết sản phẩm" class="wp-image-details"/>'
            f'</figure>\n'
        )
        content = content[:pos + 4] + img_html + content[pos + 4:]
        offset += len(img_html)
    return content

def upload_media_to_wp(image_path, filename):
    url = urljoin(WP_URL, "/wp-json/wp/v2/media")
    auth = base64.b64encode(f"{WP_USER}:{WP_PASSWORD}".encode()).decode()
    ext = os.path.splitext(filename)[1].lower()
    content_type = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".gif": "image/gif",
    }.get(ext, "image/png")
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Disposition": f"attachment; filename={filename}",
        "Content-Type": content_type,
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


def upload_image_url_to_wp(image_url, base_name):
    """Tải ảnh từ URL về rồi upload làm media (dùng làm fallback khi dựng thumbnail lỗi)."""
    if not image_url:
        return None
    try:
        r = requests.get(image_url, headers=HEADERS_SCRAPE, timeout=30)
        r.raise_for_status()
        ext = os.path.splitext(image_url.split("?")[0])[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            ext = ".jpg"
        tmp = f"/tmp/orig_{int(time.time())}{ext}"
        with open(tmp, "wb") as f:
            f.write(r.content)
        media_id = upload_media_to_wp(tmp, f"{base_name}{ext}")
        try:
            os.remove(tmp)
        except Exception:
            pass
        return media_id
    except Exception as e:
        log(f"[!] Lỗi tải/upload ảnh gốc fallback: {e}")
        return None

def get_or_create_tag(tag_name: str) -> int:
    endpoint = urljoin(WP_URL, '/wp-json/wp/v2/tags')
    auth = b64encode(f"{WP_USER}:{WP_PASSWORD}".encode()).decode()
    headers = {
        'Authorization': f'Basic {auth}',
        'Content-Type': 'application/json',
    }
    try:
        # Search for tag
        r = requests.get(endpoint, params={'search': tag_name}, headers=headers, timeout=20)
        if r.status_code == 200:
            for t in r.json():
                if t.get("name", "").lower() == tag_name.lower():
                    return t.get("id")
        # Create tag if not found
        r = requests.post(endpoint, json={'name': tag_name}, headers=headers, timeout=20)
        if r.status_code == 201:
            return r.json().get("id")
        elif r.status_code == 400 and r.json().get("code") == "term_exists":
            return r.json().get("data", {}).get("term_id")
    except Exception as e:
        log(f"[!] Error handling tag '{tag_name}': {e}")
    return None

def build_product_card(name: str, price: str, image_url: str, link: str) -> str:
    """Dựng khối 'Card Mua Hàng' cố định (ảnh trái + thông tin phải), chèn cuối bài.
    Dùng flex-wrap nên tự xuống hàng (ảnh trên / chữ dưới) khi màn hình hẹp."""
    img_html = ""
    if image_url:
        img_html = (
            f'<img src="{image_url}" alt="{name}" loading="lazy" '
            'style="width:92px;height:92px;object-fit:contain;border-radius:8px;'
            'background:#ffffff;flex-shrink:0;"/>'
        )
    return (
        '<div style="display:flex;align-items:center;gap:14px;border:1px solid #ffd9b8;'
        'border-radius:12px;padding:12px 16px;margin:28px 0;background:#fff8f2;'
        'box-shadow:0 2px 8px rgba(255,107,0,.08);">'
        f'{img_html}'
        '<div style="flex:1;min-width:0;">'
        f'<div style="font-size:15px;font-weight:600;color:#222222;line-height:1.35;margin:0 0 4px;">{name}</div>'
        f'<div style="font-size:19px;font-weight:700;color:#ff6b00;margin:0 0 8px;">{price}</div>'
        f'<a href="{link}" style="display:inline-block;background:#ff6b00;color:#ffffff;'
        'padding:8px 22px;border-radius:8px;font-size:14px;font-weight:600;'
        'text-decoration:none;">🛒 MUA NGAY</a>'
        '</div></div>'
    )


def create_wp_draft(row: dict, default_tag_id: int = None) -> dict:
    """Create a draft post via WP REST API.
    Returns the updated row with WP_ID and new status.
    """
    # 1. Scrape product details
    detail = scrape_product_detail(row['Link'])
    
    # 2. Ask Claude to write the SEO article
    article = write_seo_article(
        product_title=row['Title'],
        product_link=row['Link'],
        price=detail.get('price', 'Liên hệ'),
        detail=detail
    )
    
    if not article:
        log(f"[!] Không tạo được bài viết SEO cho {row['Title']}. Bỏ qua.")
        return row
        
    # 3. Inject gallery images
    if detail.get('gallery'):
        article['content'] = inject_images_into_content(article['content'], detail['gallery'])

    # 3.5 Chèn Card Mua Hàng cố định (có ẢNH sản phẩm) ở cuối bài
    card_img = detail.get('image') or row.get('ImageURL')
    article['content'] = article['content'] + build_product_card(
        row['Title'], detail.get('price', 'Liên hệ'), card_img, row['Link']
    )

    # 4. Generate branded thumbnail (có fallback: dùng ảnh sản phẩm gốc nếu dựng lỗi)
    tmp_path = f"/tmp/seo_thumb_{int(time.time())}.png"
    kicker = get_brand_kicker(row['Title'])
    safe_name = re.sub(r'[^a-z0-9]', '-', row['Title'].lower())[:40] or "lucas"
    img_src = detail.get('image') or row.get('ImageURL')  # ưu tiên ảnh full-size từ WC
    media_id = None
    try:
        from seo_make_thumbnail import create_seo_thumbnail
        thumb_ok = create_seo_thumbnail(img_src, row['Title'], tmp_path, kicker=kicker)
        if thumb_ok and os.path.exists(tmp_path):
            media_id = upload_media_to_wp(tmp_path, f"{safe_name}-thumbnail.png")
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        else:
            log("[!] Dựng thumbnail thất bại → fallback dùng ảnh sản phẩm gốc.")
            media_id = upload_image_url_to_wp(img_src, f"{safe_name}-original")
    except Exception as e:
        log(f"[!] Lỗi khi xử lý ảnh đại diện: {e} → fallback ảnh gốc.")
        media_id = upload_image_url_to_wp(img_src, f"{safe_name}-original")
    if not media_id:
        log(f"[!] CẢNH BÁO: bài '{row['Title']}' sẽ không có ảnh đại diện.")
        
    # 5. Get Tag IDs from WordPress
    tag_ids = []
    if default_tag_id:
        tag_ids.append(default_tag_id)
        
    if article.get('tags'):
        for tag_name in article['tags']:
            t_id = get_or_create_tag(tag_name)
            if t_id and t_id not in tag_ids:
                tag_ids.append(t_id)
                
    # 6. Post draft to WordPress
    endpoint = urljoin(WP_URL, '/wp-json/wp/v2/posts')
    auth = b64encode(f"{WP_USER}:{WP_PASSWORD}".encode()).decode()
    headers = {
        'Authorization': f'Basic {auth}',
        'Content-Type': 'application/json',
    }
    
    payload = {
        'title': article.get('seo_title', row['Title']),
        'content': article.get('content', ''),
        'status': 'draft',
        'slug': article.get('slug', ''),
        'meta': {
            '_yoast_wpseo_title':           article.get("seo_title", ""),
            '_yoast_wpseo_metadesc':        article.get("meta_description", ""),
            '_yoast_wpseo_focuskw':         article.get("focus_keyword", ""),
        }
    }
    if media_id:
        payload['featured_media'] = media_id
    if tag_ids:
        payload['tags'] = tag_ids

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=35)
        if response.status_code != 201:
            log(f"[!] Failed to create WP draft for '{row['Title']}': {response.status_code} {response.text}")
            return row
        data = response.json()
        wp_id = data.get('id')
        log(f"[+] Created WP draft ID {wp_id} with SEO Article for '{row['Title']}'")
        row['WP_ID'] = str(wp_id)
        row['Status'] = 'WP_DRAFT'
    except Exception as e:
        log(f"[!] Exception creating draft for '{row['Title']}': {e}")
    return row

def main():
    if not os.path.exists(CSV_PATH):
        log(f"[!] CSV file not found at {CSV_PATH}")
        return
        
    rows = []
    with open(CSV_PATH, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        
        # Ensure Tag and WP_ID are in fieldnames
        if 'Tag' not in fieldnames:
            fieldnames.append('Tag')
        if 'WP_ID' not in fieldnames:
            fieldnames.append('WP_ID')
            
        for row in reader:
            if None in row:
                extra_vals = row[None]
                if isinstance(extra_vals, list) and len(extra_vals) > 0:
                    if not row.get('Tag'):
                        row['Tag'] = extra_vals[0]
                    if len(extra_vals) > 1 and not row.get('WP_ID'):
                        row['WP_ID'] = extra_vals[1]
                del row[None]
            rows.append(row)
        
    # Get or create tag id for "lucas.vn"
    tag_id = get_or_create_tag("lucas.vn")
    log(f"[*] tag 'lucas.vn' ID is {tag_id}")

    def write_csv():
        # Lưu CSV NGAY sau mỗi bài: nếu lần chạy bị crash giữa chừng cũng không
        # tạo lại nháp trùng ở lần sau (nháp đã đổi Status -> WP_DRAFT được giữ lại).
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    # Nhận cả 'DRAFT' lẫn 'PENDING' làm hàng chờ tạo nháp (thống nhất vocabulary cũ/mới)
    TODRAFT_STATUSES = {'DRAFT', 'PENDING'}
    # Giới hạn số nháp mỗi lần chạy để tránh gọi API/timeout hàng loạt khi tồn đọng lớn
    MAX_DRAFTS = int(os.getenv("MAX_DRAFTS", "5"))

    processed = 0
    for i, row in enumerate(rows):
        if row.get('Status') in TODRAFT_STATUSES:
            log(f"[*] Processing draft ({processed + 1}/{MAX_DRAFTS}): {row['Title']}")
            rows[i] = create_wp_draft(row, tag_id)
            write_csv()
            processed += 1
            if processed >= MAX_DRAFTS:
                log(f"[*] Đã đạt giới hạn {MAX_DRAFTS} nháp/lần chạy, dừng tạo thêm.")
                break

    if processed:
        log(f'[+] CSV updated — đã xử lý {processed} nháp WP.')
    else:
        log('[*] No DRAFT/PENDING entries found in CSV.')

if __name__ == '__main__':
    main()
