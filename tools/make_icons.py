#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ホーム画面アイコン（apple-touch-icon / PWA）を生成する。

  python3 tools/make_icons.py            # リポジトリ直下に書き出す
  python3 tools/make_icons.py --check    # 書き出さず、実測値だけ出す

対象は 180 / 192 / 512px の3枚と、マスカブル専用の512px。
favicon.ico(16/32/48) と og-image.png はこのスクリプトの対象外（手を触れない）。

──────────────────────────────────────────────
決まっていること（2026-08-26に確定）
──────────────────────────────────────────────
・文字は「高校物理解説チャンネル」11文字を全部入れる。
・折り方は 4/2/5 の3行。語の切れ目で折る（高校物理／解説／チャンネル）。
  11は素数なので均等には割れない。どこで折るかが見た目そのものを決めるので、
  行の文字数を勝手に変えないこと。
・文字サイズは全行そろえる。最長行（チャンネル＝5文字）が基準になる。
・色は元のアイコンから実測した値。BG はサイトの --accent、INK は --bg と同じ。

⚠ 1文字ずつ外接矩形いっぱいに拡大してはいけない。画数の少ない「ン」「ル」が
   漢字より大きく見え、字面が揃わなくなる。行を文字列のまま描き、
   書体が持つ字面比率に任せること（下の render がそうしている）。

──────────────────────────────────────────────
マスカブルについて
──────────────────────────────────────────────
Android のアダプティブアイコンは、中央の直径80%の円だけを安全圏として扱い、
外側は端末の形に合わせて切り落とす。11文字を正方形いっぱいに組むと必ず
はみ出すので、通常版とマスカブル版を分けている。

  icon-192.png / icon-512.png / apple-touch-icon.png … purpose "any"
  icon-512-maskable.png                              … purpose "maskable"

site.webmanifest 側の purpose もこの分担に合わせてあること。通常版に
"maskable" を付け直すと、角の文字が切られる状態に戻る。
"""
import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("Pillow が要ります: python3 -m pip install --user Pillow")

REPO = Path(__file__).resolve().parent.parent

LINES = ["高校物理", "解説", "チャンネル"]
BG = (244, 201, 93)     # サイトの --accent
INK = (16, 21, 27)      # サイトの --bg
FONT = str(Path.home() / "Library/Fonts/NotoSansCJKjp-Black.otf")

BLOCK = 0.90            # 正方形版：一辺に対する文字ブロックの割合
LINE_GAP = 0.10         # 行間（文字サイズに対する割合）
SAFE_R = 0.40           # マスカブル安全圏の半径（一辺に対する割合）
SS = 4                  # スーパーサンプリング倍率
F0 = 200                # 幅を測るための基準サイズ

_fonts = {}
_probe = ImageDraw.Draw(Image.new("L", (8, 8)))


def _font(px):
    px = max(4, int(px))
    if px not in _fonts:
        _fonts[px] = ImageFont.truetype(FONT, px)
    return _fonts[px]


def _line_w(text, px):
    return _probe.textlength(text, font=_font(px))


def render(size, maskable=False):
    """size×size のアイコンを描く。

    maskable=True のときは、文字ブロックの対角が安全圏の円に収まるまで縮める。
    正方形に合わせるのではなく円に合わせるのがポイントで、四隅が切られなくなる。
    """
    S = size * SS
    target = S * BLOCK

    # 全行同じ文字サイズ。最長行が target に収まるように決める。
    f = target * F0 / max(_line_w(l, F0) for l in LINES)

    # 余裕を持ったキャンバスに組んでから、インクの外接矩形で切り出す。
    # こうすると行数や仮名漢字の混ざり方によらず光学的な中心が合う。
    pad = int(S * 1.2)
    layer = Image.new("L", (pad * 2, pad * 2), 0)
    d = ImageDraw.Draw(layer)
    y = pad * 0.5
    for l in LINES:
        d.text((pad - _line_w(l, f) / 2, y), l, font=_font(f), fill=255)
        y += f * (1 + LINE_GAP)

    ink = layer.crop(layer.getbbox())
    w, h = ink.size
    if maskable:
        # 半対角が安全圏の半径に収まる倍率
        k = (S * SAFE_R) / ((w ** 2 + h ** 2) ** 0.5 / 2)
    else:
        k = target / max(w, h)
    ink = ink.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)

    img = Image.new("RGB", (S, S), BG)
    img.paste(INK, ((S - ink.size[0]) // 2, (S - ink.size[1]) // 2), ink)
    return img.resize((size, size), Image.LANCZOS)


# ── 実測 ────────────────────────────────────────────────────────────
def _runs(seq):
    out, cur, n = [], seq[0], 0
    for v in seq:
        if v == cur:
            n += 1
        else:
            out.append((cur, n)); cur, n = v, 1
    out.append((cur, n))
    return out


def measure(im):
    """線の太さと画数どうしの隙間を px で測る。

    ⚠ 最小値で測ってはいけない。斜線の先端とアンチエイリアスの縁が必ず1pxの
       走査線を作るので、512pxの明らかに読めるアイコンと16pxの潰れた塊が
       同じ「最小1px」になる。分布の下側10%を見る。
    """
    g = im.convert("L")
    mid = (sum(BG) / 3 + sum(INK) / 3) / 2
    px = g.load()
    W, H = g.size
    strokes, gaps = [], []
    for axis in range(2):
        for a in range(W if axis == 0 else H):
            line = [(px[a, b] if axis == 0 else px[b, a]) < mid
                    for b in range(H if axis == 0 else W)]
            if not any(line):
                continue
            rr = _runs(line)
            for i, (val, n) in enumerate(rr):
                if val:
                    strokes.append(n)
                elif 0 < i < len(rr) - 1:
                    gaps.append(n)
    p = lambda v, q: sorted(v)[min(len(v) - 1, int(len(v) * q / 100))] if v else 0
    return p(strokes, 10), p(gaps, 10)


def safe_overflow(im):
    """安全圏の円からはみ出したインクの割合(%)。マスカブル版は 0.0 でなければならない。"""
    S = im.size[0]
    g = im.convert("L")
    mid = (sum(BG) / 3 + sum(INK) / 3) / 2
    px = g.load()
    r2 = (S * SAFE_R) ** 2
    c = S / 2
    ink = out = 0
    for y in range(S):
        for x in range(S):
            if px[x, y] < mid:
                ink += 1
                if (x - c) ** 2 + (y - c) ** 2 > r2:
                    out += 1
    return (out / ink * 100) if ink else 0.0


TARGETS = [
    ("apple-touch-icon.png", 180, False),
    ("icon-192.png",         192, False),
    ("icon-512.png",         512, False),
    ("icon-512-maskable.png", 512, True),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="書き出さず実測だけ")
    args = ap.parse_args()

    print(f"{'ファイル':24} {'px':>4} {'線p10':>6} {'間p10':>6} {'円外':>7}")
    print("-" * 52)
    bad = 0
    for name, size, maskable in TARGETS:
        im = render(size, maskable)
        s10, g10 = measure(im)
        ov = safe_overflow(im)
        print(f"{name:24} {size:>4} {s10:>6} {g10:>6} {ov:>6.1f}%")
        if maskable and ov > 0.0:
            print(f"    ✗ マスカブル版が安全圏をはみ出している（{ov:.1f}%）")
            bad += 1
        if not args.check:
            im.save(REPO / name)
    if not args.check:
        print(f"\n{len(TARGETS)}枚を書き出しました。favicon.ico と og-image.png は対象外です。")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
