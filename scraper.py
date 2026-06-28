import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

def get_new_products(max_items=30):
    """
    Truy cập vào trang sản phẩm mới nhất của lucas.vn để lấy danh sách sản phẩm.
    Trả về list các dict: [{'title': '...', 'link': '...', 'thumbnail': '...'}, ...]
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    results = []
    seen_links = set()
    page = 1
    
    target_category_url = os.getenv("TARGET_CATEGORY_URL", "https://lucas.vn/san-pham")
    if not target_category_url:
        target_category_url = "https://lucas.vn/san-pham"
        
    # Nếu URL ở trong .env kết thúc bằng '/', ta bỏ đi để nối chuỗi cho chuẩn
    if target_category_url.endswith('/'):
        target_category_url = target_category_url[:-1]

    # --- Ưu tiên WooCommerce REST API (tin cậy hơn scrape HTML) ---
    try:
        import wc_api
        if wc_api.enabled():
            brand = target_category_url.split("/")[-1].lower()
            wc_products = wc_api.list_recent_products(brand_keyword=brand, max_items=max_items)
            if wc_products:
                print(f"[*] WooCommerce API: lấy {len(wc_products)} sản phẩm (brand~'{brand}').")
                return wc_products
            print("[*] WC API không trả sản phẩm phù hợp — fallback scrape HTML.")
    except Exception as e:
        print(f"[!] WC API lỗi ({e}) — fallback scrape HTML.")

    while len(results) < max_items and page <= 5:
        # Nếu URL đã có dấu '?' (ví dụ url có param) thì nối thêm '&', nếu chưa có thì dùng '?'
        if "?" in target_category_url:
            url = f"{target_category_url}&page={page}&orderby=date" if page > 1 else f"{target_category_url}&orderby=date"
        else:
            url = f"{target_category_url}/page/{page}?orderby=date" if page > 1 else f"{target_category_url}?orderby=date"
            
        print(f"[*] Đang quét dữ liệu từ: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"[!] Lỗi khi truy cập {url}: {e}")
            break
            
        soup = BeautifulSoup(response.text, "html.parser")
        products = soup.find_all("div", class_="product-small")
        
        if not products:
            break
            
        for prod in products:
            if len(results) >= max_items:
                break
                
            try:
                a_tag = prod.find("a")
                if not a_tag:
                    continue
                
                link = a_tag.get("href")
                if link in seen_links:
                    continue
                
                img_tag = prod.find("img")
                thumbnail = img_tag.get("src") if img_tag else None
                if img_tag and img_tag.get("data-src"):
                    thumbnail = img_tag.get("data-src")
                    
                title_tag = prod.find(class_="product-title")
                title = title_tag.text.strip() if title_tag else ""
                
                if thumbnail and "-300x300" in thumbnail:
                    thumbnail = thumbnail.replace("-300x300", "")
                    
                if title and link and thumbnail:
                    seen_links.add(link)
                    results.append({
                        "title": title,
                        "link": link,
                        "thumbnail": thumbnail
                    })
            except Exception as e:
                continue
                
        page += 1
            
    print(f"[*] Tìm thấy {len(results)} sản phẩm hợp lệ không trùng lặp.")
    return results

def scrape_single_product(url):
    """
    Bóc tách dữ liệu từ 1 đường link sản phẩm cụ thể.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        title_tag = soup.find("h1", class_="product-title")
        title = title_tag.text.strip() if title_tag else ""
        
        img_tag = soup.find("div", class_="woocommerce-product-gallery__image")
        thumbnail = ""
        if img_tag and img_tag.find("a"):
            thumbnail = img_tag.find("a").get("href")
            
        if not title or not thumbnail:
            return None
            
        return {
            "title": title,
            "link": url,
            "thumbnail": thumbnail
        }
    except Exception as e:
        print(f"[!] Lỗi khi quét link {url}: {e}")
        return None

if __name__ == "__main__":
    # Test thử
    prods = get_new_products()
    if prods:
        print("Sản phẩm đầu tiên:", prods[0])
