#!/usr/bin/env python3
"""Nhập 1 sản phẩm từ trang hãng -> sản phẩm nháp chuẩn SEO trên lucas.vn.

  python import_product.py <link trang hãng>              # xem thử, KHÔNG ghi gì
  python import_product.py <link> --apply                 # tạo sản phẩm NHÁP
  python import_product.py <link> --apply --price 1890000 # kèm giá bán

Mặc định chỉ in ra để duyệt. Có --apply mới ghi lên web, và luôn tạo ở trạng thái
NHÁP (draft) — không bao giờ tự đăng công khai.

Không viết adapter riêng cho từng hãng: mỗi hãng một nền tảng (tomtoc/satechi chạy
Shopify, pitaka/jcpal thì không), viết riêng là vỡ ngay khi thêm hãng mới. Thay vào
đó render trang bằng trình duyệt thật rồi gom mọi tín hiệu có cấu trúc (JSON-LD,
thẻ og, bảng thông số, ảnh) và để Claude bóc — cách này chạy được với mọi trang.
"""
import os
import re
import sys
import json
import argparse
from base64 import b64encode
from urllib.parse import urlparse, quote_plus

import requests
from dotenv import load_dotenv

load_dotenv()

WP_URL = os.getenv("WP_SITE_URL", "https://lucas.vn").strip().strip('"').strip("'")
WP_USER = (os.getenv("WP_USERNAME") or "").strip().strip('"').strip("'")
WP_PASSWORD = (os.getenv("WP_APP_PASSWORD") or "").strip().strip('"').strip("'")
WC_KEY = (os.getenv("WC_CONSUMER_KEY") or "").strip().strip('"').strip("'")
WC_SECRET = (os.getenv("WC_CONSUMER_SECRET") or "").strip().strip('"').strip("'")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-8")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA}


def log(m):
    print(m, flush=True)


# ---------------------------------------------------------------- cào trang hãng
def render_page(url):
    """Render bằng trình duyệt thật thay vì requests: trang hãng phần lớn dựng nội
    dung bằng JS, tải HTML thô về thì bảng thông số và ảnh đều rỗng."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA, viewport={"width": 1400, "height": 2000})
        # KHÔNG dùng wait_until="networkidle": trang hãng gắn widget chat/analytics
        # kết nối liên tục nên mạng không bao giờ "im", chờ kiểu đó là treo tới hết
        # timeout (đã dính với tomtoc.com). Chờ DOM xong rồi tự kéo trang cho đủ.
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)
        # Kéo dần xuống cho ảnh lazy-load kịp hiện, không nhảy một phát xuống đáy
        for frac in (0.25, 0.5, 0.75, 1.0):
            page.evaluate(f"window.scrollTo(0, document.body.scrollHeight*{frac})")
            page.wait_for_timeout(900)
        page.wait_for_timeout(1200)
        data = page.evaluate("""() => {
            const abs = (u) => { try { return new URL(u, location.href).href; } catch { return null; } };
            const ld = [...document.querySelectorAll('script[type="application/ld+json"]')]
                .map(s => s.textContent).filter(Boolean);
            const meta = {};
            document.querySelectorAll('meta[property], meta[name]').forEach(m => {
                const k = m.getAttribute('property') || m.getAttribute('name');
                if (k && /^(og:|twitter:|description|keywords)/i.test(k)) meta[k] = m.content;
            });
            // Chỉ lấy ảnh đủ lớn: ảnh nhỏ hầu hết là icon, cờ, logo thanh toán
            const imgs = [...document.querySelectorAll('img')]
                .filter(i => (i.naturalWidth || 0) >= 500 && (i.naturalHeight || 0) >= 500)
                .map(i => abs(i.currentSrc || i.src)).filter(Boolean);
            const tables = [...document.querySelectorAll('table')].map(t => t.innerText.trim())
                .filter(t => t.length > 40).slice(0, 6);
            return {
                title: document.title,
                h1: [...document.querySelectorAll('h1,h2')].map(h => h.innerText.trim())
                      .filter(Boolean).slice(0, 12),
                jsonld: ld, meta, images: [...new Set(imgs)].slice(0, 20), tables,
                text: document.body.innerText.replace(/\\n{3,}/g, '\\n\\n').slice(0, 14000),
            };
        }""")
        browser.close()
    return data


# ---------------------------------------------------------------- video review
def find_review_video(product_name):
    """Ưu tiên YouTube Data API nếu có key; không có thì đọc trang kết quả tìm kiếm.
    Bản không key dựa vào cấu trúc HTML của YouTube nên có thể hỏng bất cứ lúc nào —
    hỏng thì bỏ qua video chứ không làm chết cả lượt nhập."""
    q = f"{product_name} review"
    try:
        if YOUTUBE_API_KEY:
            r = requests.get("https://www.googleapis.com/youtube/v3/search", timeout=20,
                             params={"part": "snippet", "q": q, "type": "video",
                                     "maxResults": 3, "key": YOUTUBE_API_KEY})
            items = r.json().get("items", [])
            if items:
                it = items[0]
                return it["id"]["videoId"], it["snippet"]["title"]
        r = requests.get(f"https://www.youtube.com/results?search_query={quote_plus(q)}",
                         headers=HEADERS, timeout=20)
        ids = re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', r.text)
        titles = re.findall(r'"title":\{"runs":\[\{"text":"(.*?)"\}', r.text)
        if ids:
            return ids[0], (titles[0] if titles else "")
    except Exception as e:
        log(f"  [!] Không tìm được video review: {e}")
    return None, None


# ---------------------------------------------------------------- sinh nội dung
def build_content(scraped, source_url):
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    ctx = {
        "url_goc": source_url,
        "title": scraped.get("title"),
        "headings": scraped.get("h1"),
        "meta": scraped.get("meta"),
        "jsonld": scraped.get("jsonld", [])[:3],
        "bang_thong_so": scraped.get("tables"),
        "noi_dung_trang": scraped.get("text"),
    }

    prompt = f"""Bạn là biên tập viên thương mại điện tử của Lucas Combo (lucas.vn) — shop phụ kiện Apple chính hãng tại TP.HCM, hoạt động từ 2017.

Dưới đây là dữ liệu cào từ TRANG CHÍNH HÃNG của một sản phẩm. Nhiệm vụ: viết lại thành trang sản phẩm tiếng Việt chuẩn SEO cho lucas.vn.

DỮ LIỆU CÀO ĐƯỢC:
{json.dumps(ctx, ensure_ascii=False)[:26000]}

QUY TẮC BẮT BUỘC:
- CHỈ dùng thông số có thật trong dữ liệu trên. Không suy đoán, không làm tròn cho đẹp, không thêm tính năng không thấy nhắc tới. Thiếu thông tin thì bỏ trường đó đi.
- Không dùng từ nổ: "cực kỳ", "siêu phẩm", "đỉnh cao", "số 1", "tốt nhất thế giới". Giọng Lucas: thẳng, hiểu chuyện, không nổ.
- KHÔNG bịa giá, không nhắc giá tiền ở bất kỳ đâu trong mô tả.
- Không nhắc tên hãng bán lẻ khác, không dẫn link ra ngoài lucas.vn.
- Viết cho người Việt mua hàng: nêu rõ giải quyết vấn đề gì, hợp với ai, dùng ra sao.

Trả về DUY NHẤT một JSON đúng cấu trúc sau, không kèm markdown hay lời dẫn:
{{
  "name": "Tên sản phẩm tiếng Việt, có tên hãng + dòng máy tương thích, 50-70 ký tự",
  "slug": "slug-khong-dau-ngan-gon",
  "short_description": "<p>2-3 câu tóm tắt bán hàng, HTML đơn giản</p>",
  "description": "<h2>...</h2><p>...</p> Bài mô tả dài 400-700 từ, chia 3-5 mục có thẻ h2, dùng <ul><li> cho ý liệt kê. Không có bảng thông số ở đây (bảng đưa vào trường attributes).",
  "attributes": [{{"name": "Chất liệu", "value": "..."}}],
  "seo_title": "Tiêu đề SEO 50-60 ký tự, có từ khoá chính",
  "meta_description": "Mô tả meta 140-160 ký tự, có từ khoá chính, có lời mời hành động",
  "focus_keyword": "từ khoá chính người Việt hay tìm",
  "tags": ["3-6 tag tiếng Việt"],
  "brand": "Tên hãng"
}}"""

    r = client.messages.create(model=CLAUDE_MODEL, max_tokens=4000,
                               messages=[{"role": "user", "content": prompt}])
    txt = r.content[0].text.strip()
    txt = re.sub(r"^```(?:json)?|```$", "", txt, flags=re.M).strip()
    return json.loads(txt)


# ---------------------------------------------------------------- đẩy lên web
def wp_headers():
    auth = b64encode(f"{WP_USER}:{WP_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {auth}", "User-Agent": UA}


def upload_image(image_url, base_name):
    """Tải ảnh từ trang hãng rồi đưa vào thư viện media của WordPress."""
    try:
        r = requests.get(image_url, headers=HEADERS, timeout=40)
        r.raise_for_status()
        ext = os.path.splitext(urlparse(image_url).path)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".webp"):
            ext = ".jpg"
        fn = f"{base_name}{ext}"
        h = wp_headers() | {
            "Content-Disposition": f'attachment; filename="{fn}"',
            "Content-Type": r.headers.get("Content-Type", "image/jpeg"),
        }
        up = requests.post(f"{WP_URL}/wp-json/wp/v2/media", headers=h, data=r.content, timeout=90)
        up.raise_for_status()
        return up.json()["id"]
    except Exception as e:
        log(f"  [!] Lỗi upload ảnh {image_url[:60]}: {e}")
        return None


def create_product(content, image_ids, video_id, price):
    desc = content["description"]
    if video_id:
        desc += (f'\n<h2>Video đánh giá</h2>\n<p><iframe width="560" height="315" '
                 f'src="https://www.youtube.com/embed/{video_id}" frameborder="0" '
                 f'allowfullscreen loading="lazy"></iframe></p>')

    payload = {
        "name": content["name"],
        "slug": content.get("slug", ""),
        "type": "simple",
        "status": "draft",          # LUÔN nháp, người duyệt rồi mới đăng
        "description": desc,
        "short_description": content.get("short_description", ""),
        "images": [{"id": i} for i in image_ids if i],
        "attributes": [
            {"name": a["name"], "options": [a["value"]], "visible": True, "variation": False}
            for a in content.get("attributes", []) if a.get("name") and a.get("value")
        ],
        "meta_data": [
            {"key": "_yoast_wpseo_title", "value": content.get("seo_title", "")},
            {"key": "_yoast_wpseo_metadesc", "value": content.get("meta_description", "")},
            {"key": "_yoast_wpseo_focuskw", "value": content.get("focus_keyword", "")},
        ],
    }
    if price:
        payload["regular_price"] = str(int(price))

    r = requests.post(f"{WP_URL}/wp-json/wc/v3/products",
                      auth=(WC_KEY, WC_SECRET), json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- chạy
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="Link trang sản phẩm của hãng")
    ap.add_argument("--apply", action="store_true", help="Thật sự tạo sản phẩm nháp")
    ap.add_argument("--price", type=int, default=0, help="Giá bán VNĐ")
    ap.add_argument("--max-images", type=int, default=6)
    a = ap.parse_args()

    for name, val in [("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY), ("WP_USERNAME", WP_USER),
                      ("WP_APP_PASSWORD", WP_PASSWORD), ("WC_CONSUMER_KEY", WC_KEY),
                      ("WC_CONSUMER_SECRET", WC_SECRET)]:
        if not val:
            sys.exit(f"Thiếu {name} trong .env")

    log(f"[1/5] Đang render trang hãng: {a.url}")
    scraped = render_page(a.url)
    log(f"      title: {scraped.get('title', '')[:70]}")
    log(f"      {len(scraped.get('images', []))} ảnh lớn, {len(scraped.get('tables', []))} bảng thông số")
    if not scraped.get("text"):
        sys.exit("Không lấy được nội dung trang — có thể bị chặn bot.")

    log("[2/5] Claude đang viết nội dung tiếng Việt chuẩn SEO...")
    content = build_content(scraped, a.url)

    log("[3/5] Tìm video review trên YouTube...")
    video_id, video_title = find_review_video(content["name"])
    log(f"      {('https://youtu.be/' + video_id + '  ' + (video_title or '')) if video_id else 'không tìm thấy'}")

    imgs = scraped.get("images", [])[: a.max_images]

    print("\n" + "=" * 68)
    print(f"TÊN      : {content['name']}")
    print(f"SLUG     : {content.get('slug')}")
    print(f"SEO TITLE: {content.get('seo_title')}  ({len(content.get('seo_title',''))} ký tự)")
    print(f"META DESC: {content.get('meta_description')}  ({len(content.get('meta_description',''))} ký tự)")
    print(f"FOCUS KW : {content.get('focus_keyword')}")
    print(f"TAGS     : {', '.join(content.get('tags', []))}")
    print(f"THÔNG SỐ : {len(content.get('attributes', []))} dòng")
    for at in content.get("attributes", [])[:10]:
        print(f"   - {at.get('name')}: {at.get('value')}")
    print(f"MÔ TẢ    : {len(re.sub('<[^>]+>', '', content['description']).split())} từ")
    print(f"ẢNH      : {len(imgs)}")
    print(f"VIDEO    : {('https://youtu.be/' + video_id) if video_id else '(không có)'}")
    print(f"GIÁ      : {(format(a.price, ',').replace(',', '.') + 'đ') if a.price else '⚠️ CHƯA CÓ — phải nhập trước khi đăng'}")
    print("=" * 68 + "\n")

    if not a.apply:
        log("Đây là bản xem thử. Thêm --apply để tạo sản phẩm nháp trên lucas.vn.")
        return

    log(f"[4/5] Upload {len(imgs)} ảnh lên thư viện WordPress...")
    base = re.sub(r"[^a-z0-9]+", "-", content.get("slug", "san-pham").lower()).strip("-")
    ids = []
    for i, u in enumerate(imgs, 1):
        mid = upload_image(u, f"{base}-{i}")
        if mid:
            ids.append(mid)
            log(f"      {i}/{len(imgs)} ok (media {mid})")

    log("[5/5] Tạo sản phẩm nháp trên WooCommerce...")
    prod = create_product(content, ids, video_id, a.price)
    log(f"\n✅ Đã tạo NHÁP #{prod['id']}: {prod['name']}")
    log(f"   Sửa & đăng tại: {WP_URL}/wp-admin/post.php?post={prod['id']}&action=edit")
    if not a.price:
        log("   ⚠️ Sản phẩm chưa có giá — nhập giá rồi mới chuyển sang Đã đăng.")


if __name__ == "__main__":
    main()
