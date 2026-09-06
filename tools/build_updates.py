# -*- coding: utf-8 -*-
"""updates.csv から、トップページの「最近の更新」節を生成する。

    python3 tools/build_updates.py            # 生成して構造検査
    python3 tools/build_updates.py --dry-run  # 差分の要約だけ

出力:

    index.html   <!-- BUILD_UPDATES:START / :END --> で囲った範囲だけを差し替える

────────────────────────────────────────────────────────────
なぜ Dropbox ではなくリポジトリの tools/ に置くか
────────────────────────────────────────────────────────────
他の4本（build_site_index.py／build_kakomon.py／build_site_leadalpha.py／
build_site_jugyo.py）はそれぞれの教材フォルダに住んでいるが、更新履歴は
**教材をまたぐ**。どれか1つの教材フォルダに置くと、他の教材の更新を足すたびに
無関係なプロジェクトを開くことになる。updates.csv もろともリポジトリに置けば
Dropbox に依存せず、どのMacからでも回せて、履歴も git に残る。

────────────────────────────────────────────────────────────
「直近7件」は閲覧時に決める
────────────────────────────────────────────────────────────
CSVの行を全部HTMLに焼き、**表示する7件はページ側のJSが選ぶ**。重問の
juyomon/2026/index.html の settle() と同じ考え方（`002 物理重要問題集/CLAUDE.md`）。

  ・日付が未来の行は出さない。重問は公開予約を先に台帳へ入れるので、
    「9/16公開」の行を9/7に載せてしまわないため。18時に回し直す必要もない。
  ・残ったうち新しい7件だけを出す。件数で切るので、更新が止まっても
    節が空にならない（「直近7日」で切ると空になる日がある）。
  ・同じ日付の行はCSVの並び順を保つ（安定ソート）。

したがって**日が経つだけで表示が入れ替わる**。ビルドが要るのは
updates.csv に行を足したときだけ。

────────────────────────────────────────────────────────────
出所（auto/manual）列
────────────────────────────────────────────────────────────
将来 build_site_index.py 等から自動追記させるための予約列。いまは全行 manual。
自動化するときは「出所が auto:xxx の行だけを消して入れ直す」ことで、
手書きの行を巻き込まずに再生成できる。**列を消さないこと。**

────────────────────────────────────────────────────────────
トップページの書き換えは範囲ガードつき
────────────────────────────────────────────────────────────
2026-08-23 の事故（正規表現で範囲を決めて次の節まで削除した）を踏まえ、
他の4本とまったく同じ作法にしてある。マーカーで囲った範囲だけを置換し、
逆操作で元のHTMLに1バイト違わず戻ることを確かめてから書き出す。
書き出したあと tools/check_html.py に落ちたら元に戻して終了コード1で終わる。
"""
import argparse
import csv
import datetime
import html
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(REPO, "updates.csv")
COLS = ["日付", "種別", "本文", "リンク", "出所"]

# 種別ごとの色。トップの分野色をそのまま借りる（新しい色を増やさない）。
#   動画 = accent（黄。サイトの主役である動画の色）
#   ページ = wave（青。新しい読みもの）
#   機能 = mech（緑。サイトの挙動が変わったもの）
KIND = {
    "動画":  ("accent",  "動画"),
    "ページ": ("wave",   "ページ"),
    "機能":  ("mech",    "機能"),
}

SHOW = 7   # ページ側が出す件数。CSSとJSの両方で使うのでここが正。


class Abort(Exception):
    pass


def load():
    if not os.path.exists(LEDGER):
        raise Abort(f"{LEDGER} がありません。")
    with open(LEDGER, encoding="utf-8-sig") as fp:
        rows = list(csv.DictReader(fp))
    if not rows:
        raise Abort("updates.csv に行がありません。")

    missing = [c for c in COLS if c not in rows[0]]
    if missing:
        raise Abort(f"updates.csv に列がありません: {missing}")

    for i, r in enumerate(rows, start=2):
        d = (r["日付"] or "").strip()
        try:
            datetime.date.fromisoformat(d)
        except ValueError:
            raise Abort(f"{i}行目: 日付が YYYY-MM-DD ではありません: {d!r}")
        if (r["種別"] or "").strip() not in KIND:
            raise Abort(f"{i}行目: 種別は {'／'.join(KIND)} のどれかです: {r['種別']!r}")
        if not (r["本文"] or "").strip():
            raise Abort(f"{i}行目: 本文が空です。")
        link = (r["リンク"] or "").strip()
        if link:
            if link.startswith("/") or "://" in link:
                raise Abort(f"{i}行目: リンクはリポジトリ内の相対パスで書きます: {link!r}")
            # 飛び先が実在するか。index.html を省いたディレクトリ指定も許す。
            target = os.path.join(REPO, link)
            if not (os.path.exists(target) or os.path.exists(os.path.join(target, "index.html"))):
                raise Abort(f"{i}行目: リンク先が見つかりません: {link}")

    # 新しい順。日付が同じならCSVの並び順を保つ（sortedは安定）。
    return sorted(rows, key=lambda r: r["日付"].strip(), reverse=True)


# ── トップページ（範囲ガードつき） ──────────────────────────────────
START = "  <!-- BUILD_UPDATES:START この節は tools/build_updates.py が管理します -->\n"
END = "  <!-- BUILD_UPDATES:END -->\n"
# 行頭に固定する。^ を付けないと、字下げを変えたときに前の字下げの余りが
# 行頭に取り残される（START が前の行の空白の途中から一致してしまうため）。
BLOCK_RE = re.compile(r"^" + re.escape(START) + r".*?^" + re.escape(END),
                      re.S | re.M)
# ヒーローの直後・「教材から探す」の直前に置く。①②③の探す導線とは別物なので
# .steplabel は使わず、節そのものに見出しを持たせる。
ANCHOR_RE = re.compile(r'(  </header>\n\n)(  <div class="findbar">)')


def esc(s):
    return html.escape(s.strip(), quote=True)


def rows_html(rows):
    out = []
    for r in rows:
        d = r["日付"].strip()
        color, label = KIND[r["種別"].strip()]
        link = (r["リンク"] or "").strip()
        md = f"{int(d[5:7])}/{int(d[8:10])}"
        body = esc(r["本文"])
        tag = (f'<a class="upd-row" href="{esc(link)}" data-date="{d}" style="--k:var(--{color})">'
               if link else
               f'<span class="upd-row" data-date="{d}" style="--k:var(--{color})">')
        close = "</a>" if link else "</span>"
        arrow = '<span class="upd-go mono" aria-hidden="true">→</span>' if link else ""
        out.append(
            f'    {tag}'
            f'<time class="upd-date mono" datetime="{d}">{md}</time>'
            f'<span class="upd-kind mono">{label}</span>'
            f'<span class="upd-text">{body}</span>{arrow}{close}\n')
    return "".join(out)


def section(rows):
    return (
        START +
        '  <section class="updates" id="updates" aria-labelledby="updates-h" hidden>\n'
        '    <h2 class="upd-h" id="updates-h">最近の更新</h2>\n'
        + rows_html(rows) +
        '  </section>\n' + END)


def patch_top(src, rows):
    """マーカーで囲った1節だけを差し替える。逆操作で元に戻ることを確かめて返す。"""
    block = section(rows)
    old = BLOCK_RE.search(src)
    if old:
        out = BLOCK_RE.sub(lambda _m: block, src, count=1)
        back = out.replace(block, old.group(0), 1)
    else:
        a = ANCHOR_RE.search(src)
        if not a:
            raise Abort("ヒーロー直後（</header> と .findbar の間）が見つかりません。"
                        "トップの構造が変わっています。")
        out = src[:a.end(1)] + block + "\n" + src[a.end(1):]
        back = out.replace(block + "\n", "", 1)
    if back != src:
        raise Abort("逆操作でトップが元に戻りませんでした。想定外の書き換えが起きています。")
    if CSS_MARK not in out:
        raise Abort(f"トップに更新節のCSS（{CSS_MARK}）がありません。先にCSSを入れてください。")
    return out


CSS_MARK = "/* ── 最近の更新"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    try:
        rows = load()
        top_path = os.path.join(REPO, "index.html")
        src = open(top_path, encoding="utf-8").read()
        out = patch_top(src, rows)
    except Abort as e:
        sys.exit(f"停止: {e}")

    today = datetime.date.today().isoformat()
    live = [r for r in rows if r["日付"].strip() <= today][:SHOW]
    ahead = [r for r in rows if r["日付"].strip() > today]

    print(f"■ updates.csv {len(rows)}行 → HTMLに全行を焼き、ページ側が新しい{SHOW}件を出す")
    print(f"  いま出る{len(live)}件（{today} 時点）:")
    for r in live:
        print(f"    {r['日付']}  {r['種別']:<3}  {r['本文']}")
    if ahead:
        print(f"  まだ出ない{len(ahead)}件（公開日が先）:")
        for r in ahead:
            print(f"    {r['日付']}  {r['種別']:<3}  {r['本文']}")
    drop = [r for r in rows if r["日付"].strip() <= today][SHOW:]
    if drop:
        print(f"  {SHOW}件からあふれた{len(drop)}件（CSVには残る）:")
        for r in drop:
            print(f"    {r['日付']}  {r['種別']:<3}  {r['本文']}")
    print(f"  index.html  {len(src.encode('utf-8')):,} → {len(out.encode('utf-8')):,} bytes")

    if a.dry_run:
        print("\n--dry-run のため書き出していません。")
        return

    top_path = os.path.join(REPO, "index.html")
    open(top_path, "w", encoding="utf-8").write(out)

    chk = os.path.join(REPO, "tools", "check_html.py")
    if os.path.exists(chk):
        r = subprocess.run([sys.executable, chk], capture_output=True, text=True)
        if r.returncode != 0:
            open(top_path, "w", encoding="utf-8").write(src)
            print("\n" + (r.stdout or "") + (r.stderr or ""))
            sys.exit("構造検査に落ちたので、index.html を元に戻しました。")
        print("\n構造検査 OK")
    print(f"完了  {datetime.datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
