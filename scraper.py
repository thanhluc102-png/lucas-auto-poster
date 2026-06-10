import requests
from bs4 import BeautifulSoup

def get_new_products(url="https://lucas.vn/"):
    """
    Truy cập vào trang chủ hoặc danh mục của lucas.vn để lấy danh sách sản phẩm.
    Trả về list các dict: [{'title': '...', 'link': '...', 'thumbnail': '...'}, ...]
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"[*] Đang quét dữ liệu từ: {url}")
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, "html.parser")
    products = soup.find_all("div", class_="product-small")
    
    results = []
    for prod in products:
        try:
            a_tag = prod.find("a")
            if not a_tag:
                continue
            
            link = a_tag.get("href")
            
            img_tag = prod.find("img")
            thumbnail = img_tag.get("src") if img_tag else None
            # Handle lazy loading images if data-src exists
            if img_tag and img_tag.get("data-src"):
                thumbnail = img_tag.get("data-src")
                
            title_tag = prod.find(class_="product-title")
            title = title_tag.text.strip() if title_tag else ""
            
            # Nếu thumbnail là dạng 300x300, ta có thể xoá đuôi -300x300 để lấy ảnh gốc
            # Ví dụ: image-300x300.png -> image.png
            if thumbnail and "-300x300" in thumbnail:
                thumbnail = thumbnail.replace("-300x300", "")
                
            if title and link and thumbnail:
                results.append({
                    "title": title,
                    "link": link,
                    "thumbnail": thumbnail
                })
        except Exception as e:
            print(f"  [!] Lỗi khi parse một sản phẩm: {e}")
            continue
            
    print(f"[*] Tìm thấy {len(results)} sản phẩm hợp lệ.")
    return results

if __name__ == "__main__":
    # Test thử
    prods = get_new_products()
    if prods:
        print("Sản phẩm đầu tiên:", prods[0])
