#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""butsuri-channel のHTML構造検査。push前と、生成スクリプトの実行後に走らせる。

  python3 tools/check_html.py              # リポジトリ内の全HTMLを検査
  python3 tools/check_html.py index.html   # ファイルを指定
  python3 tools/check_html.py --quiet      # 問題がなければ何も出さない
  python3 tools/check_html.py --self-test  # 既知の事故を再現し、検査が効くか確かめる

問題が1件でもあれば終了コード1。標準ライブラリだけで動く(依存パッケージなし)。

──────────────────────────────────────────────
なぜこれが必要か(2026-08-23の事故)
──────────────────────────────────────────────
ショートセクションを生成する gen_shorts_html.py が、差し替え範囲を
`</div>\\s*</section>` に一致する正規表現で決めていた。grid の `</div>` の直後に
`<p class="empty-note">` が挿入されて以降その前提が崩れ、**次のセクション
(テキスト・プリント)の中身までを飲み込んで削除**した。

このとき **タグの対応は崩れていなかった**。消えた範囲の中で開きと閉じがたまたま
釣り合っていたためで、入れ子検査だけを持っていても素通りしていた。
さらにカードは17枚生成されていてバッジの数字とも一致していたので、
ショート節の検査でも捕まらない。

**捕まえられるのは「消えた節がもう無い」と言える目印だけ**。それが LANDMARKS。
`--self-test` で、この事故を今も検出できることを確認できる。**検査項目を削るときは
必ず --self-test が通ることを確かめてから削ること。**

──────────────────────────────────────────────
検査項目
──────────────────────────────────────────────
1. タグの入れ子   コメント/<style>/<script> の中身をマスクしてから対応を見る
2. 目印(LANDMARKS) 必ず在るはずの id と、要素の最低個数     ← 節の消失を捕まえる
3. id の重複
4. ページ内リンク href="#foo" の飛び先 id="foo" が存在するか
5. ショート節     id="shortsGrid" があるファイルだけの追加検査
6. 警告のみ       getElementById('x') の x が無い(防御的に書かれている場合もあるため)
"""
import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# ── 目印 ────────────────────────────────────────────────────────────
# 「このファイルにはこれが必ず在る」という宣言。ページの一部が丸ごと消える事故を
# 検出するためのもので、入れ子検査では原理的に捕まえられない範囲を受け持つ。
#
# ⚠ **意図してブロックを削除・改名したときは、ここも一緒に更新すること。**
#    検査が落ちたら、まず「消したのは意図的か?」を確かめる。意図的でなければ
#    直近の生成スクリプトの実行を疑う(それが2026-08-23に起きたこと)。
# 個数は「最低これだけ」の意味。増える分には通る(節やカードの追加を邪魔しない)。
LANDMARKS = {
    "index.html": {
        "ids": ["lectures", "jumon", "leadalpha", "kakomon", "shorts", "texts",
                "lectureGrid", "jumonGrid", "chapterGrid", "kakomonGrid", "shortsGrid",
                "filters", "toTop", "lj"],
        "min_counts": {
            "physica-card": 1,     # PHYSICA導線
            "empty-note": 4,       # 各グリッドの「該当なし」表示
            "section-head": 6,     # 節の見出し
        },
    },
}

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"}

COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
# 開始タグ・閉じタグは残し、中身だけを潰すための3分割。
# ⚠ タグごと潰してはいけない。<script id="d" type="application/json"> のように
#   タグ自身が持つ id/属性まで見えなくなり、「JSが参照するidが無い」と誤検知する
#   (2026-08-23、resonance/index.html で実際に出た)。
INNER_RE = tuple(re.compile(p, re.S | re.I) for p in (
    r"(<style\b[^>]*>)(.*?)(</style>)",
    r"(<script\b[^>]*>)(.*?)(</script>)",
))


def _spaces(text):
    """中身を空白に置き換える。行番号と桁がずれないよう改行だけ残す。"""
    return re.sub(r"[^\n]", " ", text)


def mask_noise(src):
    """コメントを丸ごと、<style>/<script> は中身だけを空白に潰す。

    マスクせずに数えると、説明文として書かれた `<div>` まで数えてしまう
    (index.html には実際に3か所ある。これを数えて「div が 86/85 でずれている」と
    誤診した経緯がある)。
    """
    out = COMMENT_RE.sub(lambda m: _spaces(m.group(0)), src)
    for rx in INNER_RE:
        out = rx.sub(lambda m: m.group(1) + _spaces(m.group(2)) + m.group(3), out)
    return out


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


class NestingChecker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.problems = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag, attrs):
        pass  # <path/> のような自己完結タグは入れ子に影響しない

    def handle_endtag(self, tag):
        line = self.getpos()[0]
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for t, ln in self.stack[i + 1:]:
                    self.problems.append(
                        f"{ln}行: <{t}> が閉じられないまま {line}行の </{tag}> に到達した")
                del self.stack[i:]
                return
        self.problems.append(f"{line}行: 対応する開始タグのない </{tag}>")

    def finish(self):
        for t, ln in self.stack:
            self.problems.append(f"{ln}行: <{t}> が最後まで閉じられていない")
        return self.problems


def find_ids(masked):
    ids = {}
    for m in re.finditer(r'\bid="([^"]+)"', masked):
        ids.setdefault(m.group(1), []).append(line_of(masked, m.start()))
    return ids


def check_nesting(masked):
    p = NestingChecker()
    p.feed(masked)
    p.close()
    return p.finish()


def check_landmarks(rel, masked, ids):
    spec = LANDMARKS.get(rel)
    if not spec:
        return []
    problems = []
    for name in spec.get("ids", []):
        if name not in ids:
            problems.append(f'目印 id="{name}" が無い。ブロックが丸ごと消えていないか'
                            f'確認する(意図的な削除なら tools/check_html.py の '
                            f'LANDMARKS も更新すること)')
    for cls, least in spec.get("min_counts", {}).items():
        n = len(re.findall(r'class="[^"]*\b' + re.escape(cls) + r'\b', masked))
        if n < least:
            problems.append(f'class="{cls}" が {n} 個しかない(最低 {least} 個のはず)。'
                            f'ブロックが消えていないか確認する')
    return problems


def check_ids_and_anchors(src, masked, ids):
    problems, warnings = [], []
    for name, lines in ids.items():
        if len(lines) > 1:
            problems.append(f'id="{name}" が{len(lines)}回使われている(行: '
                            + ", ".join(map(str, lines)) + ")")
    for m in re.finditer(r'href="#([^"]+)"', masked):
        target = m.group(1)
        if target and target not in ids:
            problems.append(f'{line_of(masked, m.start())}行: href="#{target}" の'
                            f'飛び先 id="{target}" が無い')
    # JSからのid参照は防御的に書かれていることがあるので警告どまり
    for m in re.finditer(r"getElementById\(\s*['\"]([^'\"]+)['\"]", src):
        if m.group(1) not in ids:
            warnings.append(f'{line_of(src, m.start())}行: JSが参照する '
                            f'id="{m.group(1)}" がHTMLに無い')
    return problems, warnings


def check_shorts_section(src, masked):
    """ショートセクションを持つファイルだけの追加検査。"""
    if 'id="shortsGrid"' not in masked:
        return []
    problems = []
    cards = re.findall(r'<a class="short-card"[^>]*href="([^"]+)"', masked)
    if not cards:
        problems.append("shortsGrid はあるのに short-card が1枚も無い")

    badge = re.search(r'<span class="count mono">(\d+) shorts</span>', masked)
    if not badge:
        problems.append("「N shorts」バッジが見つからない")
    elif int(badge.group(1)) != len(cards):
        problems.append(f"バッジの数字({badge.group(1)})とカード枚数({len(cards)})が違う")

    for href in cards:
        if not re.fullmatch(r"https://www\.youtube\.com/shorts/[\w-]+", href):
            problems.append(f"short-card の href が想定の形ではない: {href}")

    # インラインJSが特定のカードを名指ししているなら、そのカードが実在すること
    for m in re.finditer(r"a\.short-card\[href\*=[\"']([\w-]+)[\"']\]", src):
        if not any(m.group(1) in h for h in cards):
            problems.append(f"{line_of(src, m.start())}行: JSが名指しする "
                            f"short-card({m.group(1)}) がHTMLに無い")
    return problems


def check_file(path, rel=None):
    src = path.read_text(encoding="utf-8")
    masked = mask_noise(src)
    ids = find_ids(masked)
    if rel is None:
        rel = path.name

    problems = check_nesting(masked)
    problems += check_landmarks(rel, masked, ids)
    p, warnings = check_ids_and_anchors(src, masked, ids)
    problems += p
    problems += check_shorts_section(src, masked)
    return problems, warnings


def self_test():
    """2026-08-23の事故を忠実に再現し、この検査が捕まえられることを確かめる。

    事故は「カードは正しく17枚生成されたが、後続セクションの中身が消えた」形
    だった。カード枚数もバッジも正しいままなので、ショート節の検査では捕まらない。
    ここが素通りするようになったら、LANDMARKS が痩せすぎている。
    """
    path = REPO / "index.html"
    src = path.read_text(encoding="utf-8")

    m = re.search(r'<div class="shorts-grid" id="shortsGrid">(.*?)\n\s*</div>\s*\n\s*<p',
                  src, re.S)
    if not m:
        print("self-test: 現在のindex.htmlからカードを取り出せませんでした")
        return 1
    cards = m.group(1)

    # 旧版の壊れた正規表現をそのまま使って事故を再現する
    broken, n = re.subn(
        r'(<div class="shorts-grid" id="shortsGrid">).*?(\s*</div>\s*</section>)',
        lambda mm: mm.group(1) + cards + mm.group(2), src, count=1, flags=re.S)
    if n != 1:
        print("self-test: 事故を再現できませんでした(index.htmlの構造が変わった?)")
        return 1

    tmp = REPO / "tools" / "_selftest_broken.html"
    tmp.write_text(broken, encoding="utf-8")
    try:
        problems, _ = check_file(tmp, rel="index.html")
        n_cards = len(re.findall(r'<a class="short-card"', broken))
        badge = re.search(r'<span class="count mono">(\d+) shorts</span>', broken)
    finally:
        tmp.unlink()

    print(f"  再現したHTML: カード{n_cards}枚 / バッジ{badge.group(1) if badge else '?'} "
          f"→ ショート節の検査とタグの入れ子では捕まらない状態")
    if not problems:
        print("self-test: NG — 壊れたHTMLを検出できませんでした。LANDMARKS を見直すこと")
        return 1
    print("self-test: OK — 検出できました")
    for p in problems:
        print(f"    ✗ {p}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="検査するHTML(省略時はリポジトリ内の全HTML)")
    ap.add_argument("--quiet", action="store_true", help="問題がなければ何も出さない")
    ap.add_argument("--self-test", action="store_true",
                    help="既知の事故を再現し、検査が機能することを確かめる")
    args = ap.parse_args()

    if args.self_test:
        sys.exit(self_test())

    if args.paths:
        files = [Path(p).resolve() for p in args.paths]
    else:
        files = sorted(p for p in REPO.rglob("*.html") if ".git" not in p.parts)
    if not files:
        sys.exit("検査対象のHTMLがありません")

    failed = 0
    for path in files:
        try:
            rel = str(path.relative_to(REPO))
        except ValueError:
            rel = str(path)
        problems, warnings = check_file(path, rel=rel)
        if problems:
            failed += 1
            print(f"NG {rel}")
            for p in problems:
                print(f"    ✗ {p}")
        elif not args.quiet:
            print(f"OK {rel}")
        for w in warnings:
            print(f"    ! {w}")

    if failed:
        print(f"\n{failed}件のファイルに問題があります。pushを中止してください。")
        sys.exit(1)
    if not args.quiet:
        print(f"\n{len(files)}件すべて問題なし。")


if __name__ == "__main__":
    main()
