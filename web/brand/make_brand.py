"""生成品牌 SVG 与 favicon。用法：python brand/make_brand.py（需要 fonttools、pillow、playwright）。
字标「AI 订阅比价」取自 Noto Sans CJK SC Bold（SIL OFL 1.1）并转成轮廓，所以 SVG 不依赖任何字体。"""
import io, pathlib
from fontTools.ttLib import TTCollection
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

OUT = pathlib.Path(__file__).resolve().parent.parent / "public"
GREEN, AMBER, INK = "#0E6B52", "#F2B544", "#1C1C1A"
GREEN_DARK, INK_DARK = "#14906F", "#ECECE8"   # 暗色主题：图形底色提亮，字标改浅色

# --- 图形：圆角方块里三根递减的价格柱，最低的一根用琥珀色
def mark_inner():
    bars = [(11, 14, 10, 36, "#FFFFFF"), (27, 25, 10, 25, "#FFFFFF"), (43, 36, 10, 14, AMBER)]  # x, y, w, h
    return "".join(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3.5" fill="{c}"/>' for x, y, w, h, c in bars)

def mark_svg(size=64, bleed=False, green=None):
    rx = 0 if bleed else 15
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="{size}" height="{size}">'
            f'<rect width="64" height="64" rx="{rx}" fill="{green or GREEN}"/>{mark_inner()}</svg>')

# --- 字标轮廓
ttc = TTCollection("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
font = next(f for f in ttc.fonts if "SC" in f["name"].getDebugName(1))
gs, cmap, upm = font.getGlyphSet(), font.getBestCmap(), font["head"].unitsPerEm

def text_path(text, size, x0, baseline, tracking=0.0):
    k = size / upm
    x, parts = x0, []
    for ch in text:
        name = cmap[ord(ch)]
        pen = SVGPathPen(gs)
        gs[name].draw(TransformPen(pen, (k, 0, 0, -k, x, baseline)))
        parts.append(pen.getCommands())
        x += gs[name].width * k + tracking
    return " ".join(p for p in parts if p), x

def logo_svg(color=INK, green=None):
    # 40px 图形 + 字标，字号 24，基线与图形底边对齐
    d, end = text_path("AI 订阅比价", 24, 52, 29, tracking=0.4)
    w = round(end + 2)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} 40" width="{w}" height="40" role="img" aria-label="AI 订阅比价">'
            f'<g transform="scale(0.625)"><rect width="64" height="64" rx="15" fill="{green or GREEN}"/>{mark_inner()}</g>'
            f'<path d="{d}" fill="{color}"/></svg>')

files = {"logo.svg": logo_svg(), "logo-mark.svg": mark_svg(), "favicon.svg": mark_svg(),
         "logo-light.svg": logo_svg("#FFFFFF"), "logo-dark.svg": logo_svg(INK_DARK, GREEN_DARK),
         "logo-mark-dark.svg": mark_svg(green=GREEN_DARK)}
for n, s in files.items():
    (OUT / n).write_text(s, encoding="utf-8")

# --- PNG / ICO：用 Chromium 渲染 SVG
from playwright.sync_api import sync_playwright
from PIL import Image
def render(svg, px, bleed_bg=None):
    html = f'<html><body style="margin:0;background:{bleed_bg or "transparent"}"><div style="width:{px}px;height:{px}px">{svg.replace("width=\"64\" height=\"64\"", f"width=\"{px}\" height=\"{px}\"")}</div></body></html>'
    page.set_content(html)
    return page.screenshot(clip={"x": 0, "y": 0, "width": px, "height": px}, omit_background=bleed_bg is None)
with sync_playwright() as p:
    b = p.chromium.launch(); page = b.new_page(viewport={"width": 600, "height": 600})
    for px, name in [(16, "favicon-16.png"), (32, "favicon-32.png"), (48, "favicon-48.png"), (192, "icon-192.png"), (512, "icon-512.png")]:
        (OUT / name).write_bytes(render(mark_svg(), px))
    (OUT / "apple-touch-icon.png").write_bytes(render(mark_svg(bleed=True), 180, bleed_bg=GREEN))
    b.close()
imgs = [Image.open(OUT / f"favicon-{n}.png").convert("RGBA") for n in (16, 32, 48)]
imgs[2].save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)], append_images=imgs[:2])
(OUT / "site.webmanifest").write_text('{"name":"AI 订阅比价","short_name":"订阅比价","icons":[{"src":"/icon-192.png","sizes":"192x192","type":"image/png"},{"src":"/icon-512.png","sizes":"512x512","type":"image/png"}],"theme_color":"#0E6B52","background_color":"#F5F5F3","display":"browser"}', encoding="utf-8")
print("ok", sorted(f.name for f in OUT.iterdir()))
