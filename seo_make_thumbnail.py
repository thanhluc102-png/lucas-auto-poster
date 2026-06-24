#!/usr/bin/env python3
"""
seo_make_thumbnail.py
Tạo thumbnail SEO branded theo định dạng ngang 1200x630 (chuẩn featured image / OG).
Dùng Pillow + numpy (không cần Chromium/Playwright) nên chạy được trong task tự động.

Có thể gọi 2 cách:
  1) CLI:   python3 seo_make_thumbnail.py "<image_url_or_path>" "<title>" [output.png]
  2) Import: from seo_make_thumbnail import create_seo_thumbnail
"""
import os, sys, io, requests
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE = Path(__file__).parent

# ---- Định dạng chuẩn thumbnail (KHÔNG vuông) ----
W, H = 1200, 630           # tỉ lệ ~1.91:1, chuẩn Open Graph / featured image

# ---- Bảng màu brand Lucas ----
NAVY        = (10, 15, 30)       # nền tối góc trên-trái
EMERALD_BG  = (9, 68, 50)        # nền xanh đậm góc dưới-phải
GREEN       = (16, 185, 129)     # #10b981
GREEN_LIGHT = (52, 211, 153)     # #34d399
WHITE       = (255, 255, 255)

FONT_BOLD = BASE / "assets" / "fonts" / "DejaVuSans-Bold.ttf"
FONT_REG  = BASE / "assets" / "fonts" / "DejaVuSans.ttf"
LOGO_PATH = BASE / "logo.png"

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def _font(bold, size):
    path = FONT_BOLD if bold else FONT_REG
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        sysfont = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold \
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        try:
            return ImageFont.truetype(sysfont, size)
        except Exception:
            return ImageFont.load_default()


def _load_image(src):
    """Tải ảnh sản phẩm từ URL hoặc đường dẫn local -> RGBA."""
    try:
        if str(src).startswith("http"):
            r = requests.get(src, headers=HEADERS, timeout=20)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content))
        else:
            img = Image.open(src)
        return img.convert("RGBA")
    except Exception as e:
        print(f"[!] Không tải được ảnh sản phẩm: {e}", file=sys.stderr)
        return None


def _rounded_mask(size, radius):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return m


def _gradient_bg(c1, c2):
    """Gradient chéo mượt từ c1 (góc trên-trái) -> c2 (góc dưới-phải)."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    t = (xx / W) * 0.55 + (yy / H) * 0.45
    t = (t - t.min()) / (t.max() - t.min())
    arr = np.zeros((H, W, 3), dtype=np.float32)
    for i in range(3):
        arr[..., i] = c1[i] * (1 - t) + c2[i] * t
    return Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")


def _radial_glow(cx, cy, radius, color, max_alpha):
    """Vầng sáng tròn mượt, gọn (không bị xỉn như blur blob)."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    a = np.clip(1 - d / radius, 0, 1) ** 2.2
    arr = np.zeros((H, W, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = color
    arr[..., 3] = (a * max_alpha).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def _wrap(draw, text, font, max_w):
    """Xuống dòng theo chiều rộng, KHÔNG giới hạn số dòng (không cắt chữ)."""
    lines, cur = [], ""
    for w in text.split():
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def create_seo_thumbnail(image_src, title, output_path="seo_thumbnail.png", price=""):
    # price được giữ trong chữ ký để tương thích, nhưng KHÔNG hiển thị (giữ tính tò mò).

    # ---- Nền gradient + glow sạch ----
    img = _gradient_bg(NAVY, EMERALD_BG)

    # ---- Card trắng bên phải, TO, chứa ảnh sản phẩm ----
    card_w, card_h = 552, 552
    card_x = W - 50 - card_w
    card_y = (H - card_h) // 2

    # Glow emerald sáng làm halo quanh card -> nổi khối, hiện đại
    glow = _radial_glow(card_x + card_w / 2, card_y + card_h / 2, 430, GREEN, 150)
    img.alpha_composite(glow)
    # Glow phụ rất nhẹ phía sau tiêu đề cho có chiều sâu
    img.alpha_composite(_radial_glow(150, 120, 420, GREEN_LIGHT, 38))

    draw = ImageDraw.Draw(img)

    # Bóng đổ mềm cho card
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [card_x + 4, card_y + 16, card_x + card_w + 4, card_y + card_h + 16],
        radius=44, fill=(0, 0, 0, 120))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(22)))

    # Card trắng
    card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    card.paste(Image.new("RGBA", (card_w, card_h), WHITE + (255,)), (0, 0),
               _rounded_mask((card_w, card_h), 44))
    img.alpha_composite(card, (card_x, card_y))

    # ---- Ảnh sản phẩm TO (ít padding) ----
    prod = _load_image(image_src)
    if prod:
        inner = 34
        box_w, box_h = card_w - inner * 2, card_h - inner * 2
        p = prod.copy()
        p.thumbnail((box_w, box_h), Image.LANCZOS)
        px = card_x + (card_w - p.width) // 2
        py = card_y + (card_h - p.height) // 2
        img.alpha_composite(p, (px, py))

    # ---- Tag "MỚI VỀ" góc trên card ----
    tag_font = _font(True, 23)
    tag_txt = "MỚI VỀ"
    tw = draw.textlength(tag_txt, font=tag_font)
    tag_w, tag_h = int(tw) + 40, 48
    tag_x, tag_y = card_x + 22, card_y + 22
    draw.rounded_rectangle([tag_x, tag_y, tag_x + tag_w, tag_y + tag_h], radius=14, fill=(239, 68, 68))
    draw.text((tag_x + 20, tag_y + tag_h / 2), tag_txt, font=tag_font, fill=WHITE, anchor="lm")

    # ---- Cột chữ bên trái ----
    PAD = 64
    text_x = PAD
    cursor_y = 56
    text_max_w = card_x - PAD - 28

    # Logo
    if LOGO_PATH.exists():
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            lh = 58
            lw = int(logo.width * lh / logo.height)
            logo = logo.resize((lw, lh), Image.LANCZOS)
            img.alpha_composite(logo, (text_x, cursor_y))
            cursor_y += lh + 22
        except Exception:
            cursor_y += 16
    else:
        cursor_y += 16

    # Kicker label "PHỤ KIỆN ULANZI"
    kf = _font(True, 22)
    kick = "PHỤ KIỆN ULANZI"
    kw = draw.textlength(kick, font=kf)
    draw.rounded_rectangle([text_x, cursor_y, text_x + int(kw) + 36, cursor_y + 40],
                           radius=20, fill=(255, 255, 255, 28))
    draw.text((text_x + 18, cursor_y + 20), kick, font=kf, fill=GREEN_LIGHT, anchor="lm")
    cursor_y += 40 + 26

    # ---- Tiêu đề: tự co cỡ chữ + xuống dòng cho đủ HẾT chữ (không cắt) ----
    title = (title or "").strip()
    cta_h = 60
    bottom_limit = H - 56 - cta_h - 28
    avail_h = bottom_limit - cursor_y
    chosen, lines = None, None
    for size in (52, 48, 44, 40, 37, 34, 31, 28):
        f = _font(True, size)
        ls = _wrap(draw, title, f, text_max_w)
        line_h = int(size * 1.2)
        if len(ls) * line_h <= avail_h:
            chosen, lines = f, ls
            break
    if chosen is None:                      # quá dài: dùng size nhỏ nhất
        chosen = _font(True, 28)
        lines = _wrap(draw, title, chosen, text_max_w)

    size = chosen.size
    line_h = int(size * 1.2)
    # căn giữa khối chữ theo chiều dọc trong vùng còn lại
    block_h = len(lines) * line_h
    ty = cursor_y + max(0, (avail_h - block_h) // 2)
    for ln in lines:
        draw.text((text_x, ty), ln, font=chosen, fill=WHITE)
        ty += line_h

    # ---- CTA pill ----
    cta = "Đặt hàng tại lucas.vn  ›"
    cf = _font(True, 27)
    cw = draw.textlength(cta, font=cf)
    pill_w = int(cw) + 60
    pill_y = H - 56 - cta_h
    draw.rounded_rectangle([text_x, pill_y, text_x + pill_w, pill_y + cta_h], radius=30, fill=GREEN)
    draw.text((text_x + 30, pill_y + cta_h / 2), cta, font=cf, fill=WHITE, anchor="lm")

    img.convert("RGB").save(output_path, "PNG", optimize=True)
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 seo_make_thumbnail.py <image_url_or_path> <title> [output.png]",
              file=sys.stderr)
        sys.exit(1)
    src = sys.argv[1]
    title = sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else "seo_thumbnail.png"
    print(create_seo_thumbnail(src, title, out))
