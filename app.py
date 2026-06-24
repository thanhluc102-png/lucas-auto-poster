import os
import time
from flask import Flask, request, jsonify, render_template, send_from_directory
from dotenv import load_dotenv

# Load biến môi trường từ .env
load_dotenv()

from scraper import scrape_single_product
from ai_generator import generate_social_posts
from image_processor import create_product_banner
from image_uploader import upload_image_to_wordpress
from facebook_poster import post_to_facebook, comment_on_post, post_to_instagram, post_to_threads

app = Flask(__name__)

# Đảm bảo thư mục lưu ảnh tĩnh tồn tại
os.makedirs("static", exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/api/quick-post', methods=['POST'])
def quick_post():
    try:
        url = request.form.get('url')
        if not url and request.is_json:
            url = request.json.get('url')
            
        if not url:
            return jsonify({'success': False, 'message': 'Vui lòng nhập đường link!'})
            
        print(f"[*] Bắt đầu tiến trình đăng nhanh: {url}")
        
        # Lưu file ảnh tự chụp nếu có
        image_file = request.files.get('image')
        custom_image_path = None
        if image_file and image_file.filename != '':
            custom_image_path = os.path.join('static', f"upload_{int(time.time())}.png")
            image_file.save(custom_image_path)
        
        # 1. Quét dữ liệu
        product = scrape_single_product(url)
        if not product:
            return jsonify({'success': False, 'message': 'Không thể bóc tách dữ liệu từ link này. Vui lòng kiểm tra lại.'})
            
        title = product['title']
        image_url = custom_image_path if custom_image_path else product['thumbnail']
        
        # 2. Tạo nội dung AI cho 3 nền tảng
        contents = generate_social_posts(title, url)
        if not contents or not isinstance(contents, dict):
            return jsonify({'success': False, 'message': 'Lỗi khi nhờ Claude AI viết nội dung đa nền tảng.'})
            
        fb_caption = contents.get("facebook", "")
        ig_caption = contents.get("instagram", "")
        threads_caption = contents.get("threads", "")
        
        # 3. Tạo ảnh banner HTML
        safe_name = "".join([c if c.isalnum() else "_" for c in title[:15]])
        banner_path = f"static/banner_{safe_name}_{int(time.time())}.png"
        banner_result = create_product_banner(image_url, title, banner_path)
        
        if not banner_result or not os.path.exists(banner_path):
            return jsonify({'success': False, 'message': 'Lỗi khi tạo ảnh Banner HTML.'})
            
        # 4. Upload ảnh lên Web để lấy Public Link cho IG/Threads
        public_img_url = upload_image_to_wordpress(banner_path)
        
        results = {}
        
        # 5. Bắn lên Facebook (Dùng ảnh local)
        post_id_fb = post_to_facebook(banner_path, fb_caption)
        if post_id_fb:
            comment_on_post(post_id_fb, f"🛍️ Tham khảo chi tiết và đặt mua hàng chính hãng tại Lucas:\n👉 {url}")
            results['facebook'] = f"https://www.facebook.com/{post_id_fb}"
            
        # 6. Bắn lên Instagram & Threads (Chỉ khi có Public URL)
        if public_img_url:
            post_id_ig = post_to_instagram(public_img_url, ig_caption)
            if post_id_ig:
                results['instagram'] = f"https://www.instagram.com/p/{post_id_ig}/" # ID này có thể là Graph ID, dùng app mở là tốt nhất
                
            post_id_threads = post_to_threads(public_img_url, threads_caption)
            if post_id_threads:
                results['threads'] = f"https://www.threads.net/post/{post_id_threads}"
        else:
            results['warning'] = "Không thể upload ảnh lên web để lấy link public, bỏ qua IG & Threads."
            
        return jsonify({
            'success': True,
            'message': 'Hoàn tất quá trình!',
            'results': results,
            'banner_url': f"/{banner_path}",
            'title': title
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Lỗi hệ thống (Python): {str(e)}'})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    print(f"[*] Khởi động Lucas Auto Poster Web App tại cổng {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
