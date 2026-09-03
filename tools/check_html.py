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
                   と、要素にならない約束ごと(css)          ← 擬似要素の消失を捕まえる
3. id の重複
4. ページ内リンク href="#foo" の飛び先 id="foo" が存在するか
5. ショート節     id="shortsGrid" があるファイルだけの追加検査
6. 警告のみ       getElementById('x') の x が無い(防御的に書かれている場合もあるため)
7. 共有部品       「上へ戻る」のCSSとしきい値が全ページで同一か  ← ファイルをまたぐ検査
8. Service Worker sw.js が先読みするファイルが実在するか        ← ファイルをまたぐ検査

7・8 は 1〜6 と違い、**1枚だけ見ても気づけない**種類のずれを受け持つ。トップは手書き、
他は生成物で出どころが別なので、片方だけ直すと静かに食い違う(2026-09-02 導入)。
"""
import argparse
import fnmatch
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
            "jm-index": 1,         # 重問インデックスへの導線(build_site_index.pyが管理)
            "km-index": 1,         # 過去問インデックスへの導線(build_kakomon.pyが管理)
            "la-index": 1,         # リードαインデックスへの導線(build_site_leadalpha.pyが管理)
            "la-2024": 1,          # リードα改訂版への導線(同上。同じマーカーの中)
            "jg-index": 1,         # 授業動画インデックスへの導線(build_site_jugyo.pyが管理)
            "quiet-link": 1,       # フッタの進学情報への導線
        },
    },
    # 重問インデックス。002 物理重要問題集/scripts/build_site_index.py が生成する。
    # 問題が減ることはないので、min_counts は現状の163問をそのまま下限にしてある。
    "juyomon/2026/index.html": {
        "ids": ["filters", "qIndex", "nLive", "nSched", "onlyLive",
                "f-mech", "f-therm", "f-wave", "f-electro", "f-atom", "f-survey"],
        "min_counts": {
            "q": 163,      # 1問1枚のカード
            "qmain": 163,  # 本編の行(カード1枚に必ず1行)
            "qa": 2,       # 別解の行(問25(7)と問26。増える分には通る)
            "fs": 6,       # 分野セクション
            "none": 6,     # 各分野の「該当なし」表示
        },
        # 公開済みの行に出る再生マーク。リードα側と対になっている(下の css を見よ)。
        "css": {"再生マーク": '.qrow[data-state="live"] .st::before{ content:"\\25B6 "; }'},
    },
    "juyomon/2025/index.html": {
        "ids": ["y2025"],
        "min_counts": {"y-table": 1},
    },
    # リードα。002 リード/999 抽出/scripts/build_site_leadalpha.py が生成する。
    # 第28・29章は未撮影だが一覧には載せるので、下限は現状の650問・29章のまま。
    "leadalpha/index.html": {
        "ids": ["panel", "jump", "q", "hits",
                "ch1", "ch13", "ch20", "ch27", "ch28", "ch29"],
        "min_counts": {
            "p": 650,      # 1問1枚のカード
            "ch": 29,      # 章セクション
            "kg": 29,      # 種別のまとまり(章あたり1〜4)
            "jc": 29,      # 章ジャンプ
            "none": 29,    # 章ごとの「該当なし」表示
            # 対応する版の明記と、改訂版(/leadalpha/2024/)への案内。両ページが
            # 互いを指しているので、片方だけ消えると行き止まりになる。
            "edition": 1,    # 「2022年11月1日発行 新課程版」の明記
            "yearnote": 1,   # 改訂版への案内
            "which": 1,      # 版の見分け方
        },
        # 公開済み591問に出る再生マーク。::after なので class も id も増えず、
        # 上の min_counts では消えても気づけない。ここだけが受け皿になる。
        "css": {"再生マーク": '.p[data-state=live]::after{ content:"\\25B6";'},
    },
    # リードα 改訂版。002 リード/999 抽出/scripts/build_site_leadalpha2024.py が
    # 生成する。台帳は leadalpha-2024-mapping.csv（2つのPDFの全対全突き合わせ）。
    # 動画にリンクするのは判定が「対応」かつ一致率0.9以上のものだけで、残りは
    # 準備中。撮り足せば live が増える側なので、下限は現状の444のまま。
    "leadalpha/2024/index.html": {
        "ids": ["panel", "jump", "q", "hits",
                "ch1", "ch21", "ch30", "ch特集①", "ch特集③"],
        "min_counts": {
            "p": 567,        # 1問1枚のカード（改訂版の全問）
            "ch": 33,        # 章30 ＋ 特集3
            "jc": 33,        # 章ジャンプ
            "none": 33,      # 章ごとの「該当なし」表示
            "edition": 1,    # 「2024年11月1日発行 改訂版」の明記
            "yearnote": 1,   # 新課程版への案内と、番号がずれる旨
            "which": 1,      # 版の見分け方
            "src": 1,        # 新課程版の番号の添え字(←174)。消えると番号の
                             # 出どころが分からなくなる
        },
        "css": {"再生マーク": '.p[data-state=live]::after{ content:"\\25B6";'},
    },
    # 授業動画。002 リード/999 抽出/scripts/build_site_jugyo.py が生成する。
    # 中学理科17本はトップの再生リスト5枚に揃えて載せていないので、下限は
    # 5分野176本のまま。撮り足せば増える側なので、増える分には通る。
    "jugyo/index.html": {
        "ids": ["panel", "q", "hits",
                "fs-mech", "fs-therm", "fs-wave", "fs-electro", "fs-atom"],
        "min_counts": {
            "p": 176,      # 1本1枚のカード
            "fs": 5,       # 分野セクション
            "none": 5,     # 分野ごとの「該当なし」表示
        },
        # このページには再生マークが無い(176本すべて公開済みで、印が
        # 公開済み／準備中を分ける役に立たない)。リードαや重問の css 検査を
        # ここに写さないこと。理由は build_site_jugyo.py の CSS 内に書いてある。
    },
    # 過去問。GAS/slidekit/build_kakomon.py が生成する。
    # 大学一覧は「区分グループの数」を下限にする。準備中の大学は公開に
    # 切り替わると prep が減るので、減る側の数は下限に使わない。
    "kakomon/index.html": {
        "ids": ["kakomonList"],
        "min_counts": {
            "grp": 4,      # 区分グループの見出し(旧帝/関東/私立/共通テスト)
            "ugrid": 4,    # グループごとのタイル並び
            "uni": 1,      # 公開中の大学(増える分には通る)
        },
    },
    # 進学情報。007 進路部/研修/_web/build_page.py が生成する。
    # 資料が増えたときに手で足さずに済むよう glob で受ける。学科数や表の数は
    # 資料ごとに違うので、下限は「表と注意書きが在る」に留める。
    "shingaku/*/index.html": {
        # 表の本体は大学群によらず <main id="hyo">。かつては MARCH 1枚だけだった
        # 名残で "marchTable" を見ていたが、早慶上理を足すと glob に載らなくなる。
        # 資料が増えても手を入れずに済ませるのが、この glob の趣旨(2026-09-03)。
        "ids": ["hyo"],
        "min_counts": {
            "warn": 1,     # 出願前に要項で確認、の注意書き
            "tw": 1,       # 横スクロールする表の器
            "row": 1,      # 学科の行
        },
    },
    # 大学ページ。大学が増えるたびに手で足さずに済むよう glob で受ける。
    # 収録数は大学ごとに違うので、下限は「1つは在る」に留める。
    "kakomon/*/index.html": {
        "ids": ["uniIndex"],
        "min_counts": {
            "yr-sec": 1,   # 年度セクション
            "ex-sec": 1,   # 実施回(学部・方式)
            "qgrid": 1,    # 大問ごとの問の並び
            "q": 1,        # 1問1枚のカード
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


def landmark_spec(rel):
    """LANDMARKS の引き当て。完全一致が無ければ glob キーを試す。

    glob を入れたのは kakomon/<大学>/index.html のため。大学が増えるたびに
    LANDMARKS へ手で足すのは忘れるので、まとめて1行で受ける。
    完全一致を先に見るので、特定の1枚だけ強い目印を課すこともできる。
    """
    if rel in LANDMARKS:
        return LANDMARKS[rel]
    for pat, spec in LANDMARKS.items():
        if "*" in pat and fnmatch.fnmatch(rel, pat):
            return spec
    return None


def check_landmarks(rel, masked, ids):
    spec = landmark_spec(rel)
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


# ── 共有部品の同期 ──────────────────────────────────────────────────
# 「上へ戻る」はトップ(index.html、手書き)と生成ページ6枚に同じものが入っている。
# 生成側の出どころは GAS/slidekit/webparts.py だが、**トップは生成物ではないので
# 自動では追随しない**。片方だけ直すと「トップだけ挙動が違う」というわかりにくい
# 不整合になるので、ここでずれを捕まえる(2026-09-02 導入)。
#
# リポジトリ内のHTML同士だけを突き合わせる。webparts.py は Dropbox 側にあり、
# この検査は標準ライブラリだけで動く前提なので参照しない。
TOTOP_CSS_RE = re.compile(r'(?:@media[^{]*\{\s*)?\.to-top[^{]*\{[^{}]*\}(?:\s*\})?')
TOTOP_THRESHOLD_RE = re.compile(r"window\.scrollY\s*>\s*(\d+)")
STYLE_RE = re.compile(r"(<style\b[^>]*>)(.*?)(</style>)", re.S)


def totop_fingerprint(src):
    """「上へ戻る」のCSSルールと出現しきい値を、空白を潰して取り出す。

    戻り値 (ルールのリスト, しきい値)。ボタンが無いページは (None, None)。
    """
    if 'id="toTop"' not in src:
        return None, None
    css = "".join(m.group(2) for m in STYLE_RE.finditer(src))
    rules = [re.sub(r"\s+", " ", r).strip() for r in TOTOP_CSS_RE.findall(css)]
    th = TOTOP_THRESHOLD_RE.search(src)
    return rules, (th.group(1) if th else None)


def check_totop_sync(seen):
    """seen = {rel: (rules, threshold)}。index.html を基準に全部そろっているか見る。

    比較対象が1枚しか無いとき(ファイルを指定して実行したとき)は何もしない。
    """
    have = {rel: v for rel, v in seen.items() if v[0] is not None}
    if len(have) < 2:
        return []
    ref_rel = "index.html" if "index.html" in have else sorted(have)[0]
    ref_rules, ref_th = have[ref_rel]
    problems = []
    if not ref_rules:
        return [f'{ref_rel}: id="toTop" があるのに .to-top のCSSが見つからない']
    for rel, (rules, th) in sorted(have.items()):
        if rel == ref_rel:
            continue
        if rules != ref_rules:
            only_ref = [r for r in ref_rules if r not in rules]
            only_this = [r for r in rules if r not in ref_rules]
            detail = "; ".join(
                [f"{ref_rel}にだけ有る: {r[:60]}" for r in only_ref[:2]] +
                [f"{rel}にだけ有る: {r[:60]}" for r in only_this[:2]]) or "並びが違う"
            problems.append(
                f"{rel}: 「上へ戻る」のCSSが {ref_rel} と違う({detail})。"
                "生成ページ側は GAS/slidekit/webparts.py が出どころ。"
                "トップは手書きなので、どちらかを直したらもう一方も直すこと")
        if th != ref_th:
            problems.append(
                f"{rel}: 「上へ戻る」の出現しきい値が {th}px、"
                f"{ref_rel} は {ref_th}px。そろえること")
    return problems


# ── CSSの目印 ───────────────────────────────────────────────────────
# LANDMARKS の "css" は、**HTMLの要素として現れない**約束ごとを見張る。
#
# きっかけは再生マーク(U+25B6)。リードαでは .p[data-state=live]::after で出して
# いるので、class も id も1つも増えない。つまり min_counts では、CSSが1行消えて
# 591問ぶんの印が全部消えても**枚数は650枚のまま**で、何も起きていないように見える。
# 重問側は .st::before で、こちらも同じく数えられない。
#
# 2つを対で書いてあるのは、片方だけ消えると「重問には印が有るのにリードαには
# 無い」という、1枚ずつ見ていては気づけない食い違いになるため(検査7と同じ性質)。
def check_css_landmarks(rel, src):
    spec = landmark_spec(rel)
    if not spec or "css" not in spec:
        return []
    css = " ".join(re.sub(r"\s+", " ", m.group(2)) for m in STYLE_RE.finditer(src))
    problems = []
    for label, needle in spec["css"].items():
        if needle not in css:
            problems.append(
                f"{label}のCSSが無い（{needle} を探した）。生成スクリプトの実行を"
                "疑うこと。意図して外したなら tools/check_html.py の LANDMARKS も"
                "更新する（対になっているページも一緒に見直すこと）")
    return problems


# ── Service Worker の先読み一覧 ──────────────────────────────────────
# sw.js は install 時に SHELL のURLを取りに行く。ここに書いたファイルを改名・削除
# しても、SWは1件ずつ失敗を握りつぶす作りなので**何も言わずに欠けたまま動く**。
# オフラインのときだけ「アイコンが出ない」「トップが開けない」形で表面化するので、
# 手元では気づけない。実在するかどうかはリポジトリを見れば分かるので、ここで見る。
SW_SHELL_RE = re.compile(r"const\s+SHELL\s*=\s*\[(.*?)\]", re.S)
SW_URL_RE = re.compile(r"['\"]\./([^'\"]*)['\"]")


def check_sw_shell():
    """sw.js が先読みするファイルが実在するか。sw.js が無ければ何もしない。"""
    sw = REPO / "sw.js"
    if not sw.exists():
        return []
    src = sw.read_text(encoding="utf-8")
    m = SW_SHELL_RE.search(src)
    if not m:
        return ["sw.js: const SHELL = [...] が見つからない。"
                "名前を変えたなら check_html.py の SW_SHELL_RE も直すこと"]
    problems = []
    for rel in SW_URL_RE.findall(m.group(1)):
        if rel == "":          # './' はトップページ自身
            rel = "index.html"
        if not (REPO / rel).exists():
            problems.append(
                f"sw.js: 先読みする {rel} がリポジトリに無い。"
                "ファイルを改名したなら sw.js の SHELL も直すこと")
    # 登録側も見る。sw.js があるのに誰も register していなければ、ただの死んだファイル。
    if "navigator.serviceWorker.register" not in (REPO / "index.html").read_text(encoding="utf-8"):
        problems.append("index.html: sw.js があるのに register() していない。"
                        "意図して外したなら sw.js も消すこと")
    return problems


def check_file(path, rel=None):
    src = path.read_text(encoding="utf-8")
    masked = mask_noise(src)
    ids = find_ids(masked)
    if rel is None:
        rel = path.name

    problems = check_nesting(masked)
    problems += check_landmarks(rel, masked, ids)
    problems += check_css_landmarks(rel, src)
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
    seen = {}
    for path in files:
        try:
            rel = str(path.relative_to(REPO))
        except ValueError:
            rel = str(path)
        src = path.read_text(encoding="utf-8")
        seen[rel] = totop_fingerprint(src)
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

    # ファイルをまたぐ検査。1枚ずつ見ていても気づけない種類のずれを受け持つ。
    cross = check_totop_sync(seen)
    if cross:
        failed += 1
        print("NG 共有部品「上へ戻る」")
        for p in cross:
            print(f"    ✗ {p}")

    sw = check_sw_shell()
    if sw:
        failed += 1
        print("NG Service Worker (sw.js)")
        for p in sw:
            print(f"    ✗ {p}")

    if failed:
        print(f"\n{failed}件のファイルに問題があります。pushを中止してください。")
        sys.exit(1)
    if not args.quiet:
        n_tt = sum(1 for v in seen.values() if v[0] is not None)
        print(f"\n{len(files)}件すべて問題なし。"
              f"（「上へ戻る」は{n_tt}枚で同一）")


if __name__ == "__main__":
    main()
