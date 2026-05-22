# -*- coding: utf-8 -*-
"""アイコン生成スクリプト。
   - アプリアイコン icon.ico/png は あきら 提供の app_icon_src.png から生成（円形・角透明）。
   - UIアイコン ui_*.png は Subara3 自作のフラットアイコン。"""

import math
import os
from PIL import Image, ImageDraw

ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

# === アプリアイコン（あきら提供の素材から円形に切り出して生成）===========
SRC = "app_icon_src.png"
if os.path.exists(SRC):
    src = Image.open(SRC).convert("RGBA")
    w, h = src.size
    s = min(w, h)
    src = src.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2)).resize(
        (256, 256), Image.LANCZOS)
    cmask = Image.new("L", (256, 256), 0)
    ImageDraw.Draw(cmask).ellipse([0, 0, 255, 255], fill=255)
    app_icon = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    app_icon.paste(src, (0, 0), cmask)
    app_icon.save("icon.png")
    app_icon.save("icon.ico", sizes=ICO_SIZES)
    print("icon.ico / icon.png を生成しました（あきら提供素材・円形）")
else:
    print(f"{SRC} が見つからないため icon.ico/png はスキップしました")


# ===========================================================================
# UI 用フラットアイコン（行の鍵・鉛筆・ゴミ箱、設定の歯車、検索）
# 72px で描画 → 18px へ縮小。すべて単色フラット・絵文字不使用。
# ===========================================================================
GOLD = (198, 146, 30, 255)
INDIGO = (91, 75, 138, 255)
SLATE = (96, 96, 116, 255)
RED = (192, 86, 63, 255)
UI = 72
UI_OUT = 18


def _new():
    im = Image.new("RGBA", (UI, UI), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def _save(im, name):
    im.resize((UI_OUT, UI_OUT), Image.LANCZOS).save(name)


LOCK_LOCKED = (90, 86, 104, 255)   # 落ち着いたスレート（黄色をやめる）
LOCK_OPEN = (46, 150, 160, 255)    # 開錠＝ティール（コピー準備OKの合図）


def lock_icon(open_=False):
    im, dr = _new()
    col = LOCK_OPEN if open_ else LOCK_LOCKED
    if open_:
        # 開錠：フックを左に開いた状態
        dr.arc([16, 6, 42, 36], start=160, end=340, fill=col, width=8)
    else:
        dr.ellipse([22, 8, 50, 40], outline=col, width=8)  # 閉じたフック（下半分は本体で隠す）
    dr.rounded_rectangle([16, 34, 56, 64], radius=8, fill=col)  # 本体
    dr.ellipse([32, 44, 40, 52], fill=(255, 255, 255, 255))      # 鍵穴
    dr.rectangle([34, 49, 38, 59], fill=(255, 255, 255, 255))
    return im


def gear_icon():
    im, dr = _new()
    cx = cy = 36
    teeth, r_out, r_in, hole = 8, 30, 23, 11
    pts = []
    for i in range(teeth * 2):
        ang = i / (teeth * 2) * 2 * math.pi
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    dr.polygon(pts, fill=INDIGO)
    dr.ellipse([cx - hole, cy - hole, cx + hole, cy + hole], fill=(255, 255, 255, 0))
    dr.ellipse([cx - hole, cy - hole, cx + hole, cy + hole], fill=(244, 240, 250, 255))
    return im


def edit_icon():
    im, dr = _new()
    # 斜めの鉛筆（本体＋先端）
    dr.line([(20, 54), (50, 22)], fill=SLATE, width=12)
    dr.polygon([(50, 22), (60, 14), (58, 30)], fill=(60, 60, 72, 255))  # 芯
    dr.line([(16, 58), (22, 52)], fill=(60, 60, 72, 255), width=6)       # 書き先
    return im


def delete_icon():
    im, dr = _new()
    dr.rectangle([28, 12, 44, 20], fill=RED)            # 取っ手
    dr.rounded_rectangle([16, 20, 56, 28], radius=3, fill=RED)  # 蓋
    dr.polygon([(22, 28), (50, 28), (46, 62), (26, 62)], fill=RED)  # 本体
    for x in (31, 36, 41):                               # 縦溝
        dr.line([(x, 33), (x, 57)], fill=(255, 255, 255, 230), width=3)
    return im


def search_icon():
    im, dr = _new()
    dr.ellipse([16, 16, 44, 44], outline=SLATE, width=7)
    dr.line([(42, 42), (58, 58)], fill=SLATE, width=9)
    return im


def _star_points(cx, cy, r_out, r_in, n=5, rot=-math.pi / 2):
    pts = []
    for i in range(n * 2):
        ang = rot + i * math.pi / n
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


def star_icon(filled=True):
    im, dr = _new()
    pts = _star_points(36, 38, 28, 12)
    if filled:
        dr.polygon(pts, fill=GOLD)
    else:
        dr.line(pts + [pts[0]], fill=(168, 168, 184, 255), width=5, joint="curve")
    return im


def grip_icon():
    im, dr = _new()
    light = (150, 150, 168, 255)   # 控えめなドラッグ・グリップ（点6つ）
    for x in (27, 45):
        for y in (20, 36, 52):
            dr.ellipse([x - 5, y - 5, x + 5, y + 5], fill=light)
    return im


_save(lock_icon(False), "ui_lock.png")
_save(lock_icon(True), "ui_unlock.png")
_save(gear_icon(), "ui_gear.png")
_save(edit_icon(), "ui_edit.png")
_save(delete_icon(), "ui_delete.png")
_save(search_icon(), "ui_search.png")
_save(grip_icon(), "ui_grip.png")
_save(star_icon(True), "ui_star.png")
_save(star_icon(False), "ui_star_off.png")
Image.new("RGBA", (UI_OUT, UI_OUT), (0, 0, 0, 0)).save("ui_blank.png")
print("UI アイコン（ui_*.png）を生成しました")
