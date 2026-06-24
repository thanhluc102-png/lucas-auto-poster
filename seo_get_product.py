#!/usr/bin/env python3
"""
seo_get_product.py
Lấy sản phẩm Ulanzi mới nhất chưa được đăng. In ra JSON hoặc "NO_NEW_PRODUCT".
"""
import json, sys, requests
from pathlib import Path
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

ULANZI_URL   = "https://lucas.vn/danh-muc/phu-kien-ulanzi"
HISTORY_FILE = Path(__file__).parent / "seo_history.json"
HEADERS      = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

def load_history():
    if HISTORY_FILE.exists():
        try: return json.loads(HISTORY_FILE.read_text())
        except: pass
    return []

def get_products():
    results, seen = [], set()
    try:
        r = requests.get(ULANZI_URL, headers=HEADERS, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.find_all("div", class_="product-small"):
            a = item.find("a", href=True)
            title = item.find(class_="product-title")
            img = item.find("img")
            price = item.find(class_="price")
            if not (a and title): continue
            link = a["href"]
            if link in seen: continue
            seen.add(link)
            src = (img.get("data-src") or img.get("src", "")) if img else ""
            results.append({
                "title": title.text.strip(),
                "link": link,
                "thumbnail": src.replace("-300x300", ""),
                "price": price.text.strip() if price else "",
            })
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
    return results

def get_product_detail(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(r.text, "html.parser")
        desc = soup.find(id="tab-description") or soup.find(class_="woocommerce-Tabs-panel--description")
        gallery = [a["href"] for a in soup.select(".woocommerce-product-gallery__image a") if a.get("href","").startswith("http")]
        return {
            "description": desc.get_text(" ", strip=True)[:1000] if desc else "",
            "gallery": gallery[:5],
        }
    except:
        return {"description": "", "gallery": []}

history  = load_history()
products = get_products()
new = [p for p in products if p["link"] not in history]

if not new:
    print("NO_NEW_PRODUCT")
    sys.exit(0)

product = new[0]
detail  = get_product_detail(product["link"])
product.update(detail)
print(json.dumps(product, ensure_ascii=False))
