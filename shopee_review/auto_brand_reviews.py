#!/usr/bin/env python3
"""
auto_brand_reviews.py — Tự động COPY review Shopee -> sản phẩm web theo thương hiệu.

An toàn tuyệt đối (tránh gắn nhầm): CHỈ đẩy khi Shopee & web TRÙNG thương hiệu VÀ
TRÙNG mã model (vd Wi-C041, S400, LP005FX...). Sp không có mã hoặc không khớp -> bỏ,
để duyệt tay. Bỏ qua WiWU + Lucas (đã làm tay). Lọc rác bằng keyword + Gemini vision.

Mỗi lần chạy giới hạn MAX_PRODUCTS_PER_RUN sp (đỡ đốt quota Gemini) — cron hằng ngày sẽ
cày dần hết các thương hiệu còn lại rồi tự dừng, về sau chỉ bắt sp/mã mới xuất hiện.

State: shopee_review/brand_reviews_state.json = {"done": {"<item_id>": web_id}}
Chạy: python shopee_review/auto_brand_reviews.py
"""
import sys, os, re, json, time, datetime, requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
try:
    from dotenv import load_dotenv; load_dotenv(os.path.join(ROOT, ".env"))
except Exception:
    pass
import shopee_reviews as sr
from image_uploader import upload_image_to_wordpress

U = (os.getenv("WP_SITE_URL") or "https://lucas.vn").strip().strip('"').strip("'").rstrip("/")
K = (os.getenv("WC_CONSUMER_KEY") or "").strip(); S = (os.getenv("WC_CONSUMER_SECRET") or "").strip()
AUTH = (K, S)
DOMAIN = "@shopee-import.lucas.vn"
MAX_PER = 40                    # trần review / sp
MAX_PRODUCTS_PER_RUN = 6       # trần sp xử lý / lần chạy (bảo vệ quota Gemini)
STATE = os.path.join(HERE, "brand_reviews_state.json")

SKIP_BRANDS = {"wiwu", "lucas"}   # đã làm tay
# Danh sách thương hiệu shop đang bán (để bắt buộc khớp brand giữa Shopee <-> web)
BRANDS = {
    "anker","ulanzi","inateck","hoda","aulumu","satechi","tomtoc","thule","jcpal",
    "innostyle","nillkin","lisen","hyperwork","hyperone","hyperdrive","hyper","mipow",
    "jrc","mcdodo","ugreen","baseus","elago","spigen","esr","moft","rock","remax",
    "benks","kingxbar","momax","choetech","mophie","belkin","logitech","keychron",
    "lofree","xiaomi","joyroom","hyperjuice","zmi","aukey","ringke","dux","uniq",
    "switcheasy","pitaka","native","peak","zens","courant","twelve","hyperx","razer",
}

def brands_in(name):
    low = name.lower()
    return {b for b in BRANDS if b in low}

def mcodes(name):
    c = set(re.findall(r"[A-Za-z]{1,4}-\w*\d[\w]*", name)) | set(re.findall(r"\b[A-Z]{1,4}\d{2,5}[A-Z]{0,3}\b", name))
    return {x.lower() for x in c if len(x) >= 3}

def load_state():
    try: return json.load(open(STATE))
    except Exception: return {"done": {}}

def save_state(st):
    json.dump(st, open(STATE, "w"), ensure_ascii=False, indent=0)

def wc_search(q):
    try:
        r = requests.get(f"{U}/wp-json/wc/v3/products", params={"search": q, "per_page": 8, "_fields": "id,name"}, auth=AUTH, timeout=25).json()
        return r if isinstance(r, list) else []
    except Exception:
        return []

def find_web_match(nm):
    """Trả (web_id, web_name) nếu tìm được sp web TRÙNG brand + TRÙNG mã model; else None."""
    sbrands = brands_in(nm); scodes = mcodes(nm)
    if not sbrands or not scodes:
        return None
    for code in scodes:                       # search TỪNG mã (đã học: đừng nhồi cả cụm)
        for p in wc_search(code):
            wn = p["name"]
            if not (brands_in(wn) & sbrands):   # phải cùng thương hiệu
                continue
            if code in mcodes(wn):              # và trùng đúng mã model
                return p["id"], wn
    return None

def existing_reviewers(pid):
    try:
        return {(r.get("reviewer") or "").lower() for r in requests.get(f"{U}/wp-json/wc/v3/products/reviews", params={"product": pid, "per_page": 100}, auth=AUTH, timeout=30).json()}
    except Exception:
        return set()

def gallery(urls):
    return ('<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;">'
            + "".join(f'<a href="{x}" target="_blank" rel="noopener"><img src="{x}" style="width:84px;height:84px;object-fit:cover;border-radius:6px;border:1px solid #eee;"/></a>' for x in urls)
            + "</div>")

def upload(url):
    try:
        d = requests.get(url, timeout=25).content
        p = f"/tmp/br_{int(time.time()*1000)}.jpg"; open(p, "wb").write(d)
        w = upload_image_to_wordpress(p); os.remove(p); return w
    except Exception:
        return None

def set_counts(pid):
    rv = requests.get(f"{U}/wp-json/wc/v3/products/reviews", params={"product": pid, "per_page": 100, "status": "approved"}, auth=AUTH, timeout=30).json()
    rs = [r.get("rating") or 5 for r in rv]; n = len(rs)
    if not n: return 0, 0
    avg = round(sum(rs) / n, 2); dist = {str(x): rs.count(x) for x in set(rs)}
    requests.put(f"{U}/wp-json/wc/v3/products/{pid}", json={"average_rating": str(avg),
        "meta_data": [{"key": "_wc_review_count", "value": n}, {"key": "_wc_average_rating", "value": str(avg)}, {"key": "_wc_rating_count", "value": dist}]}, auth=AUTH, timeout=30)
    return n, avg

def import_reviews(pid, item_id):
    cs = sr.fetch_all_comments(item_id=item_id)
    cand = [c for c in cs if c.get("rating_star", 0) >= 4 and (c.get("comment") or "").strip()
            and sr.classify_text((c.get("comment") or "").strip())[0]
            and (c.get("media") or {}).get("image_url_list")]
    requests.put(f"{U}/wp-json/wc/v3/products/{pid}", json={"reviews_allowed": True}, auth=AUTH, timeout=30)
    ex = existing_reviewers(pid); added = 0
    for c in cand[:MAX_PER]:
        buyer = c.get("buyer_username") or "Khách"
        if buyer.lower() in ex: continue
        real = [im for im in (c.get("media") or {}).get("image_url_list", [])[:3] if sr.vet_image(im)[0]]
        if not real: continue
        wp = [w for w in (upload(im) for im in real) if w]
        if not wp: continue
        ct = c.get("create_time") or c.get("ctime"); t = c["comment"].strip()
        body = {"product_id": pid, "review": t + gallery(wp), "reviewer": buyer,
                "reviewer_email": re.sub(r"[^a-z0-9]", "", buyer.lower())[:20] + DOMAIN,
                "rating": c.get("rating_star", 5), "status": "approved"}
        if ct:
            body["date_created_gmt"] = datetime.datetime.fromtimestamp(int(ct), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        r = requests.post(f"{U}/wp-json/wc/v3/products/reviews", json=body, auth=AUTH, timeout=45)
        if r.status_code in (200, 201): added += 1; ex.add(buyer.lower())
    n, avg = set_counts(pid)
    return added, n, avg

def all_items(tok):
    items = []; off = 0
    while True:
        res = sr._shop_get("/api/v2/product/get_item_list", tok, {"offset": off, "page_size": 100, "item_status": "NORMAL"})
        r = res.get("response") or {}; lst = r.get("item", [])
        items += [i["item_id"] for i in lst]
        if r.get("has_next_page") and lst: off = r.get("next_offset", off + len(lst)); time.sleep(0.2)
        else: break
    names = {}
    for i in range(0, len(items), 50):
        res = sr._shop_get("/api/v2/product/get_item_base_info", tok, {"item_id_list": ",".join(map(str, items[i:i+50]))})
        for it in (res.get("response") or {}).get("item_list", []): names[it["item_id"]] = it.get("item_name", "")
        time.sleep(0.2)
    return names

def main():
    if not (K and S):
        print("[!] Thiếu WC_CONSUMER_KEY/SECRET -> dừng."); return
    st = load_state(); done = st.setdefault("done", {})
    tok = sr._get_valid_token()
    names = all_items(tok)
    used_web = set(done.values())

    # Xây worklist: sp chưa done, không phải WiWU/Lucas, khớp brand+mã model
    work = []
    for iid, nm in names.items():
        if str(iid) in done: continue
        low = nm.lower()
        if any(b in low for b in SKIP_BRANDS): continue
        m = find_web_match(nm)
        if not m: continue
        wid, wn = m
        if wid in used_web: continue           # 1 web chỉ nhận từ 1 sp Shopee
        work.append((iid, nm, wid, wn))

    print(f"[i] {len(names)} sp Shopee | {len(done)} đã xong | {len(work)} cặp khớp brand+mã mới.")
    if not work:
        print("[+] Không có cặp mới để đẩy. Xong."); return

    total = 0
    for iid, nm, wid, wn in work[:MAX_PRODUCTS_PER_RUN]:
        try:
            added, n, avg = import_reviews(wid, iid)
            done[str(iid)] = wid; used_web.add(wid); total += added
            print(f"  ✅ [{wid}] {wn[:42]} | +{added} review (tổng {n}, {avg}★)  <- Shopee {iid}")
            save_state(st)
        except Exception as e:
            print(f"  ⚠️ Shopee {iid} -> web {wid} lỗi: {str(e)[:80]}")
    save_state(st)
    print(f"\nXONG lần này: {total} review, {sum(1 for _ in work[:MAX_PRODUCTS_PER_RUN])} sp. Còn lại chờ lần sau: {max(0,len(work)-MAX_PRODUCTS_PER_RUN)} cặp.")

if __name__ == "__main__":
    main()
