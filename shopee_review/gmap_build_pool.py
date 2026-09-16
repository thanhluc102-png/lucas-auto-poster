#!/usr/bin/env python3
"""Kéo MỘT LẦN toàn bộ đánh giá Google Business cũ vào kho gmap_pool.json.

Chạy ở MÁY (nơi có token_gbp.pickle), không chạy trên CI — kho commit sẵn rồi job
hằng ngày chỉ bốc từ kho, khỏi cần OAuth Google trên GitHub Actions.

  python3 shopee_review/gmap_build_pool.py
"""
import os, sys, json, datetime, requests

sys.path.insert(0, "/Users/luctran/auto-reviews")
import gbp_api, main as M

HERE = os.path.dirname(os.path.abspath(__file__))
POOL = os.path.join(HERE, "gmap_pool.json")
MIN_STAR = 4
MIN_AGE_DAYS = 365          # chỉ lấy review từ >= 1 năm trước
STAR = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}

creds = M.get_credentials()
c = gbp_api.GBPClient(creds)
loc = (f"accounts/{M.ACCOUNT_ID}/locations/{M.LOCATION_ID}"
       if M.ACCOUNT_ID and M.LOCATION_ID else M.pick_location(c))

url = f"{c.REVIEW_BASE}/{c._v4_name(loc)}/reviews"
allrv, tok = [], None
while True:
    p = {"pageSize": 50, "orderBy": "updateTime desc"}
    if tok:
        p["pageToken"] = tok
    r = requests.get(url, headers=c._headers(), params=p, timeout=60)
    r.raise_for_status()
    j = r.json()
    allrv += j.get("reviews", [])
    tok = j.get("nextPageToken")
    if not tok:
        break
print(f"  kéo được {len(allrv)} review")

cutoff = (datetime.date.today() - datetime.timedelta(days=MIN_AGE_DAYS)).isoformat()
pool = []
for rv in allrv:
    stars = STAR.get(str(rv.get("starRating")).upper(), 0)
    text = (rv.get("comment") or "").strip()
    created = (rv.get("createTime") or "")[:10]
    if stars < MIN_STAR or not text or not created or created > cutoff:
        continue
    # Bản dịch Google chèn "(Translated by Google)" / "(Original)" — cắt bỏ, chỉ giữ
    # phần tiếng Việt gốc của khách.
    for marker in ("(Translated by Google)", "(Original)"):
        if marker in text:
            text = text.split(marker)[0].strip()
    if len(text) < 12:
        continue
    pool.append({
        "id": rv["name"].split("/")[-1],       # định danh ổn định để chống đăng trùng
        "buyer": rv.get("reviewer", {}).get("displayName", "Khách hàng"),
        "stars": stars,
        "text": text,
        "date": created,
        "year": created[:4],
    })

pool.sort(key=lambda x: x["date"])              # cũ nhất trước
json.dump({"built": datetime.date.today().isoformat(), "reviews": pool},
          open(POOL, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"✔ {len(pool)} review >= {MIN_STAR}★, có nội dung, >= 1 năm trước -> {POOL}")
print(f"  cũ nhất {pool[0]['date']} · mới nhất {pool[-1]['date']}")
