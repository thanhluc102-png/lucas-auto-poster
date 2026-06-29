"""
shopee_card.py — Render ảnh "card review" Shopee (1080px) bằng Pillow.
Port thiết kế từ tool tay lucas-auto-poster/review_tool_fixed.html (theme .c-shopee):
  dải cam, avatar, tên + tích xanh đỏ, sao đỏ, chip "✓ Đã mua hàng",
  "Phân loại hàng: ...", nội dung, ảnh hero + overlay "Ảnh thực tế từ khách",
  footer "Khách hàng để lại đánh giá tại Shopee", logo Lucas góc phải.

render_card(review, out_path) -> out_path (PNG)
  review = {"buyer","stars","text","image"(url), "category"(optional)}
"""
import os
import io
import math
import requests
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(BASE_DIR, "fonts")   # Be Vietnam Pro
LOGO_URL = "https://lucas.vn/wp-content/uploads/2025/10/Logo-Lucas-Combo-200x200-1-1.png"

W = 1080
PADX = 56
CW = W - 2 * PADX
ORANGE = (238, 77, 45)        # #ee4d2d
ORANGE2 = (255, 106, 61)      # #ff6a3d
GREY = (155, 155, 155)
DARK = (51, 51, 51)

_AV_COLORS = [(26,188,156),(52,152,219),(155,89,182),(230,126,34),(231,76,60),
              (22,160,133),(41,128,185),(142,68,173),(211,84,0),(192,57,43),
              (39,174,96),(44,62,80)]
_font_cache = {}
_logo_cache = {}


def _font(size, bold=False, weight=None):
    w = weight or ("SemiBold" if bold else "Regular")
    key = (size, w)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(
            os.path.join(FONT_DIR, f"BeVietnamPro-{w}.ttf"), size)
    return _font_cache[key]


def _avatar_color(name):
    s = sum(ord(c) for c in (name or "L"))
    return _AV_COLORS[s % len(_AV_COLORS)]


def _wrap(draw, text, font, max_w):
    out = []
    for para in (text or "").split("\n"):
        words = para.split()
        if not words:
            out.append("")
            continue
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if draw.textlength(test, font=font) <= max_w:
                cur = test
            else:
                if cur:
                    out.append(cur)
                cur = w
        if cur:
            out.append(cur)
    return out


def _star(draw, cx, cy, r, fill):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.42
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    draw.polygon(pts, fill=fill)


def _stars_row(draw, x, y, size, count, fill, empty=(224,227,233)):
    r = size / 2
    gap = size + 8
    for i in range(5):
        _star(draw, x + r + i * gap, y + r, r, fill if i < count else empty)
    return 5 * gap


def _verified(base, cx, cy, r):
    """Tích xanh kiểu Shopee: hoa thị đỏ + dấu check trắng."""
    d = ImageDraw.Draw(base)
    pts = []
    for i in range(24):
        ang = i * math.pi / 12
        rad = r if i % 2 == 0 else r * 0.82
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    d.polygon(pts, fill=ORANGE)
    d.line([(cx - r*0.42, cy + r*0.05), (cx - r*0.08, cy + r*0.4),
            (cx + r*0.5, cy - r*0.35)], fill=(255,255,255),
           width=max(3, int(r*0.22)), joint="curve")


def _circle_img(im, size):
    im = im.convert("RGBA").resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    im.putalpha(mask)
    return im


def _fetch(url, timeout=20):
    return Image.open(io.BytesIO(requests.get(url, timeout=timeout).content))


def _logo():
    if "img" not in _logo_cache:
        try:
            _logo_cache["img"] = _fetch(LOGO_URL)
        except Exception:
            _logo_cache["img"] = None
    return _logo_cache["img"]


def render_card(review, out_path):
    name = review.get("buyer") or "Khách hàng"
    rating = int(review.get("stars") or 5)
    text = (review.get("text") or "").strip()
    category = review.get("category") or "—"
    photo_url = review.get("image")

    photo = None
    if photo_url:
        try:
            photo = _fetch(photo_url).convert("RGB")
        except Exception:
            photo = None

    # --- đo trước chiều cao ảnh hero để biết chiều cao card ---
    hero_h = 0
    if photo:
        scale = min(CW / photo.width, 850 / photo.height)
        ph_w, ph_h = int(photo.width * scale), int(photo.height * scale)
        hero_h = ph_h

    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    body_font = _font(33)
    lines = _wrap(tmp, text, body_font, CW)
    line_h = 51

    # --- tính tổng chiều cao ---
    y = 16 + 46                      # dải cam + padding trên
    y += 100                         # khối top (avatar/tên/sao)
    y += 36 + 50                     # chip "Đã mua hàng"
    y += 26 + 32                     # phân loại hàng
    y += 16 + len(lines) * line_h    # nội dung
    if photo:
        y += 24 + hero_h             # ảnh hero
    y += 34 + 28 + 40                # footer
    y += 56                          # padding dưới
    H = y

    img = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # dải cam gradient ngang
    for x in range(W):
        t = x / W
        c = tuple(int(ORANGE2[i] + (ORANGE[i]-ORANGE2[i]) * t) for i in range(3))
        draw.line([(x, 0), (x, 16)], fill=c)

    # logo góc phải
    lg = _logo()
    if lg:
        img.paste(lg.convert("RGBA").resize((76, 76)), (W - 44 - 76, 44),
                  lg.convert("RGBA").resize((76, 76)))

    cy = 16 + 46
    # avatar
    av_d = 100
    ac = _avatar_color(name)
    draw.ellipse((PADX, cy, PADX + av_d, cy + av_d), fill=ac)
    init = (name.strip()[:1] or "L").upper()
    f_av = _font(46, bold=True)
    bb = draw.textbbox((0, 0), init, font=f_av)
    draw.text((PADX + av_d/2 - (bb[2]-bb[0])/2, cy + av_d/2 - (bb[3]-bb[1])/2 - bb[1]),
              init, font=f_av, fill=(255, 255, 255))
    # tên + tích
    nx = PADX + av_d + 24
    f_name = _font(35, bold=True)
    draw.text((nx, cy + 6), name, font=f_name, fill=(34, 34, 34))
    nw = draw.textlength(name, font=f_name)
    _verified(img, nx + nw + 28, cy + 6 + 18, 18)
    # sao
    _stars_row(draw, nx, cy + 56, 34, rating, ORANGE)

    y = cy + 100
    # chip "Đã mua hàng"
    y += 36
    chip = "✓ Đã mua hàng"
    f_chip = _font(23, bold=True)
    cw = draw.textlength(chip, font=f_chip)
    draw.rounded_rectangle((PADX, y, PADX + cw + 40, y + 50), radius=25,
                           fill=(255, 244, 240), outline=(255, 215, 201), width=1)
    draw.text((PADX + 20, y + 12), chip, font=f_chip, fill=ORANGE)
    y += 50

    # phân loại hàng (cắt gọn 1 dòng — tên sản phẩm Shopee thường rất dài)
    y += 26
    f_var = _font(25)
    f_varb = _font(25, weight="Medium")
    pre = "Phân loại hàng: "
    val = (category or "—").split(",")[0].strip()          # lấy phần trước dấu phẩy
    avail = CW - draw.textlength(pre, font=f_var)
    if draw.textlength(val, font=f_varb) > avail:           # vẫn dài -> ellipsis
        while val and draw.textlength(val + "…", font=f_varb) > avail:
            val = val[:-1]
        val += "…"
    draw.text((PADX, y), pre, font=f_var, fill=GREY)
    draw.text((PADX + draw.textlength(pre, font=f_var), y), val,
              font=f_varb, fill=(85, 85, 85))
    y += 32

    # nội dung
    y += 16
    for ln in lines:
        draw.text((PADX, y), ln, font=body_font, fill=DARK)
        y += line_h

    # ảnh hero
    if photo:
        y += 24
        scale = min(CW / photo.width, 850 / photo.height)
        ph_w, ph_h = int(photo.width * scale), int(photo.height * scale)
        frame = Image.new("RGB", (CW, ph_h), (233, 236, 241))
        frame.paste(photo.resize((ph_w, ph_h)), ((CW - ph_w) // 2, 0))
        # overlay gradient đen dưới 55%
        ov = Image.new("RGBA", (CW, ph_h), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        gh = int(ph_h * 0.55)
        for i in range(gh):
            a = int(150 * (i / gh))
            od.line([(0, ph_h - gh + i), (CW, ph_h - gh + i)], fill=(0, 0, 0, a))
        frame = Image.alpha_composite(frame.convert("RGBA"), ov).convert("RGB")
        # bo góc
        mask = Image.new("L", (CW, ph_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, CW, ph_h), radius=18, fill=255)
        img.paste(frame, (PADX, y), mask)
        # nhãn "Ảnh thực tế từ khách"
        ld = ImageDraw.Draw(img)
        lx, ly = PADX + 30, y + ph_h - 28 - 40
        ld.ellipse((lx, ly, lx + 48, ly + 48), fill=(0, 0, 0, 180))
        # icon camera đơn giản
        ld.rounded_rectangle((lx + 12, ly + 17, lx + 36, ly + 34), radius=3, fill=(255,255,255))
        ld.ellipse((lx + 19, ly + 20, lx + 29, ly + 30), fill=(0,0,0,180))
        ld.rectangle((lx + 19, ly + 13, lx + 27, ly + 18), fill=(255,255,255))
        ld.text((lx + 62, ly + 8), "Ảnh thực tế từ khách", font=_font(25, bold=True),
                fill=(255, 255, 255))
        y += ph_h

    # footer
    y += 34
    draw.line((PADX, y, W - PADX, y), fill=(241, 241, 241), width=1)
    y += 28
    draw.text((PADX, y), "Khách hàng để lại đánh giá tại Shopee",
              font=_font(25, bold=True), fill=ORANGE)

    img.save(out_path, "PNG")
    return out_path


if __name__ == "__main__":
    demo = {
        "buyer": "Nguyễn Minh Anh", "stars": 5,
        "text": "Shop tư vấn nhiệt tình, hàng chính hãng đầy đủ, dán máy đẹp không bọt khí. Sẽ ủng hộ Lucas dài dài!",
        "category": "Dán màn hình MacBook",
        "image": "https://mms.img.susercontent.com/vn-11134103-81ztc-mpj4l33gykgec3",
    }
    out = render_card(demo, os.path.join(BASE_DIR, "shopee_card_demo.png"))
    print("Đã render:", out)
