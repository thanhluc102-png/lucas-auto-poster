import requests
from bs4 import BeautifulSoup

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
    
    while len(results) < max_items and page <= 5:
        url = f"https://lucas.vn/san-pham/page/{page}?orderby=date" if page > 1 else "https://lucas.vn/san-pham?orderby=date"
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

if __name__ == "__main__":
    # Test thử
    prods = get_new_products()
    if prods:
        print("Sản phẩm đầu tiên:", prods[0])
