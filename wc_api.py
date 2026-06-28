"""
wc_api.py — Lấy dữ liệu sản phẩm qua WooCommerce REST API (tin cậy hơn scrape HTML).

Gộp "cái hay" từ repo claudeseo: thay vì parse CSS class dễ vỡ, gọi thẳng
/wp-json/wc/v3/products để lấy tên, mô tả, gallery, giá, ảnh full-size.

An toàn: tất cả hàm chỉ hoạt động khi có WC_CONSUMER_KEY + WC_CONSUMER_SECRET.
Nếu thiếu key hoặc lỗi → trả [] / None để caller tự fallback sang scrape HTML.
"""
import os
import re
import requests
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

WP_SITE_URL = os.getenv("WP_SITE_URL", "https://lucas.vn").strip().strip('"').strip("'").rstrip("/")
WC_KEY = (os.getenv("WC_CONSUMER_KEY", "") or "").strip().strip('"').strip("'")
WC_SECRET = (os.getenv("WC_CONSUMER_SECRET", "") or "").strip().strip('"').strip("'")

# Slug danh mục coi như "tất cả" (không lọc theo brand)
_ALL_SLUGS = {"", "san-pham", "sản-phẩm", "shop", "store"}


def enabled() -> bool:
    """True nếu đã cấu hình đủ WooCommerce API key."""
    return bool(WC_KEY and WC_SECRET)


def _auth():
    return (WC_KEY, WC_SECRET)


def slug_from_link(link: str) -> str:
    """https://lucas.vn/san-pham/<slug>/ -> <slug>"""
    try:
        parts = [p for p in urlparse(link).path.split("/") if p]
        return parts[-1] if parts else ""
    except Exception:
        return ""


def _strip_html(html: str, limit: int) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _format_price(raw) -> str:
    """WC trả giá dạng số '199000' -> '199.000₫'. Trống -> 'Liên hệ'."""
    s = str(raw or "").strip()
    if not s:
        return "Liên hệ"
    try:
        return f"{int(float(s)):,.0f}".replace(",", ".") + "₫"
    except Exception:
        return s


def list_recent_products(brand_keyword: str = "", max_items: int = 30) -> list:
    """Danh sách sản phẩm mới nhất (publish). Lọc theo brand_keyword nếu có.
    Trả [{title, link, thumbnail}], hoặc [] nếu không bật/không có kết quả."""
    if not enabled():
        return []
    params = {
        "orderby": "date",
        "order": "desc",
        "status": "publish",
        "per_page": min(max(max_items * 2, 20), 100),
    }
    kw = (brand_keyword or "").strip().lower()
    if kw and kw not in _ALL_SLUGS:
        params["search"] = kw
    try:
        r = requests.get(f"{WP_SITE_URL}/wp-json/wc/v3/products",
                         params=params, auth=_auth(), timeout=30)
        r.raise_for_status()
        out = []
        for p in r.json():
            name = (p.get("name") or "").strip()
            link = p.get("permalink") or ""
            if not name or not link:
                continue
            imgs = [i.get("src") for i in p.get("images", []) if i.get("src")]
            out.append({"title": name, "link": link, "thumbnail": imgs[0] if imgs else ""})
            if len(out) >= max_items:
                break
        return out
    except Exception as e:
        print(f"[!] WC list_recent_products lỗi: {e}")
        return []


def get_product_by_slug(slug: str) -> dict | None:
    if not enabled() or not slug:
        return None
    try:
        r = requests.get(f"{WP_SITE_URL}/wp-json/wc/v3/products",
                         params={"slug": slug, "per_page": 1},
                         auth=_auth(), timeout=20)
        r.raise_for_status()
        data = r.json()
        return data[0] if data else None
    except Exception as e:
        print(f"[!] WC get_product_by_slug lỗi: {e}")
        return None


def detail_from_link(link: str) -> dict | None:
    """Lấy chi tiết sản phẩm qua WC từ link bài. Trả None nếu không lấy được
    (để caller fallback scrape HTML). Cùng schema với scrape_product_detail()."""
    p = get_product_by_slug(slug_from_link(link))
    if not p:
        return None
    images = [i.get("src") for i in p.get("images", []) if i.get("src")]
    return {
        "short_desc": _strip_html(p.get("short_description", ""), 500),
        "long_desc": _strip_html(p.get("description", ""), 1000),
        "gallery": images[:5],
        "price": _format_price(p.get("price") or p.get("regular_price")),
        "image": images[0] if images else "",
        "name": (p.get("name") or "").strip(),
    }
