import csv
import os
import requests
import json
import re
import base64
from urllib.parse import urljoin
import anthropic
from dotenv import load_dotenv

# Load credentials
load_dotenv()

WP_URL = os.getenv('WP_SITE_URL', 'https://lucas.vn').strip().strip('"').strip("'")
WP_USER = os.getenv('WP_USERNAME').strip().strip('"').strip("'")
WP_PASSWORD = os.getenv('WP_APP_PASSWORD').strip().strip('"').strip("'")
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-opus-4-8')

if not all([WP_URL, WP_USER, WP_PASSWORD, ANTHROPIC_API_KEY]):
    raise RuntimeError('Missing WordPress or Anthropic credentials in .env')

CSV_PATH = os.path.abspath('content_plan.csv')

def get_catchy_title(product_title: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    prompt = f"""Bạn là một chuyên gia tối ưu tiêu đề SEO (giật tít, clickbait) cho trang tin tức phụ kiện công nghệ lucas.vn.
Hãy viết một tiêu đề bài viết duy nhất cho sản phẩm sau đây:
Tên sản phẩm: {product_title}

Yêu cầu tiêu đề:
1. Độ dài lý tưởng từ 55 - 65 ký tự.
2. Cực kỳ cuốn hút, giật tít, kích thích tò mò, tạo ham muốn click ngay lập tức.
3. Phải chứa từ khóa chính (tên sản phẩm hoặc thương hiệu + loại sản phẩm) để tối ưu công cụ tìm kiếm (SEO).
4. KHÔNG dùng dấu ngoặc kép bọc ngoài tiêu đề, không giải thích gì thêm, chỉ trả về chuỗi tiêu đề duy nhất.

Ví dụ giật tít hay:
- "Đế Sạc 4-in-1 Aulumu M01: Tiền Nào Của Nấy, Có Thực Sự Đỉnh?"
- "Giá Đỡ AULUMU G09 MagSafe: Có Đáng Cho Dân Chơi Công Nghệ?"
- "Đánh Giá Ốp iPhone 17 Aulumu Aramid Fiber: Mỏng, Nhẹ Có Đủ Bảo Vệ?"

Hãy tạo tiêu đề cho sản phẩm: {product_title}"""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        title = response.content[0].text.strip()
        # Clean title from wrapping quotes if any
        title = re.sub(r'^["\'“‘]|[”’"\']$', '', title).strip()
        return title
    except Exception as e:
        print(f"[!] Error calling Claude for title: {e}")
        return None

def update_wp_post_title(post_id: str, new_title: str):
    endpoint = urljoin(WP_URL, f'/wp-json/wp/v2/posts/{post_id}')
    auth = base64.b64encode(f"{WP_USER}:{WP_PASSWORD}".encode()).decode()
    headers = {
        'Authorization': f'Basic {auth}',
        'Content-Type': 'application/json',
    }
    
    payload = {
        'title': new_title,
        'meta': {
            '_yoast_wpseo_title': new_title
        }
    }
    
    try:
        r = requests.post(endpoint, json=payload, headers=headers, timeout=20)
        if r.status_code == 200:
            print(f"[+] Successfully updated post {post_id} title to: '{new_title}'")
            return True
        else:
            print(f"[!] Failed to update post {post_id}: {r.status_code} {r.text}")
    except Exception as e:
        print(f"[!] Exception updating post {post_id}: {e}")
    return False

def main():
    if not os.path.exists(CSV_PATH):
        print(f"[!] CSV file not found at {CSV_PATH}")
        return
        
    rows = []
    with open(CSV_PATH, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = list(reader.fieldnames)
        for row in reader:
            if None in row:
                del row[None]
            rows.append(row)
            
    updated = False
    for i, row in enumerate(rows):
        # We process posts that have WP_ID and have been drafted (Status can be WP_DRAFT)
        if row.get('Status') == 'WP_DRAFT' and row.get('WP_ID'):
            post_id = row['WP_ID']
            print(f"\n[*] Processing Post {post_id}: {row['Title']}")
            new_title = get_catchy_title(row['Title'])
            if new_title:
                success = update_wp_post_title(post_id, new_title)
                if success:
                    # Update Title field in CSV as well
                    rows[i]['Title'] = new_title
                    updated = True
                    
    if updated:
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print("\n[+] Updated CSV with new catchy titles.")
    else:
        print("\n[*] No WP_DRAFT posts found to rewrite.")

if __name__ == '__main__':
    main()
