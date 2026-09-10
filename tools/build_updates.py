# -*- coding: utf-8 -*-
"""updates.csv から、トップページの「最近の更新」節を生成する。

    python3 tools/build_updates.py            # 生成して構造検査
    python3 tools/build_updates.py --dry-run  # 差分の要約だけ
    python3 tools/build_updates.py --sync     # 重問の台帳を取り込んでから生成

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

  ・**公開日時**が未来の行は出さない。重問は公開予約を先に台帳へ入れるので、
    「9/16 18:00公開」の行を9/7に載せてしまわないため。18時に回し直す必要もない。
    日付だけでなく時刻まで見る。日付だけで比べると 18:00 公開の行が当日の
    午前中から「公開」扱いになる（2026-09-10 に問31で実際に起きた）。
    時刻は updates.csv の `時刻` 列に持ち、HTMLには data-at として焼く。
    空欄は 00:00 とみなす（リードαは台帳に公開日しか無いのでこちら）。
  ・残ったうち新しい7件だけを出す。件数で切るので、更新が止まっても
    節が空にならない（「直近7日」で切ると空になる日がある）。
  ・同じ日付の行はCSVの並び順を保つ（安定ソート）。

したがって**日が経つだけで表示が入れ替わる**。ビルドが要るのは
updates.csv に行を足したときだけ。

────────────────────────────────────────────────────────────
出所（auto/manual）列と --sync
────────────────────────────────────────────────────────────
`manual` は手で書いた行。`auto:` で始まる行は台帳から機械的に作った行。

`--sync` は **auto: で始まる行を全部捨てて作り直す**。manual の行は読みもしない
ので巻き込まれない。逆に auto: 行を手で直しても次の --sync で消える。
何度走らせても同じ結果になる（冪等）。

取り込み元は重問の2つの台帳で、`--juyomon` でその場所を渡す。既定は Dropbox の
`002 物理重要問題集`。**フォルダが無ければ同期は黙って飛ばす**（Dropbox の無い
Mac でも updates.csv の描画だけは通す）。

  auto:juyomon          juyomon-mapping.csv  の 公開予約(JST) が入っている行
  auto:juyomon-variant  juyomon-variants.csv の 公開予約(JST) が入っている行
  auto:leadalpha        leadalpha-chapter-schedule.csv の 公開日 が入っている行

公開予約が空の行は取らない。重問の問1〜11は予約運用を始める前に公開されたもので
台帳に公開日が無いため、ここには出てこない（2026-09-07、遡らないと決めた）。

リードαは章が単位で、1章ぶんの全動画が日曜にまとめて public になる。したがって
1章＝1行。`履歴` 列が「載せる」の章だけを取る。第1〜16章は公開済みだが
遡らない方針なので「—」にしてあり、記録としては台帳に残るが更新履歴には出ない
（2026-09-07、清水さんの判断）。

飛び先は `juyomon/2026/#qNN` と `leadalpha/#chN`。前者は build_site_index.py が
振っている。後者は build_site_leadalpha.py が元から振っていた。
**あちらのアンカーを消すとリンクが死ぬ**ので、両方セットで直すこと。

────────────────────────────────────────────────────────────
HTMLに焼く行の選び方
────────────────────────────────────────────────────────────
出すのは7件だが、日が経つだけで表示が入れ替われるよう、余分に焼いておく。
とはいえ163問ぶんを全部焼くとトップが倍近くに膨れるので絞る。

    未来日の行は全部 ＋ 過去の新しい PAST 行

**「新しいN行」という単純な上限にしてはいけない。**最初はそうしていたが、
2026-09-07 にリードαの11章ぶんを予約したところ未来日の行が20件に増え、
上限30行のうち過去が10行しか残らなくなった（表示7件に対して余裕3行）。
予約を先に入れるほど過去が押し出される作りだったため、予約を増やすと
いつか表示が7件に届かなくなる。未来と過去を別々に数えれば起きない。

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
# 公開時刻。重問は18:00に予約するので、日付だけで比べると当日の午前から
# 「公開」扱いになってしまう（2026-09-10に問31で実際に起きた）。
# 既存CSVには無い列なので**必須列には入れない**。空なら 00:00 とみなす。
TIME_COL = "時刻"
OUT_COLS = ["日付", TIME_COL, "種別", "本文", "リンク", "出所"]

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
PAST = 15  # 焼く「過去の行」の数。未来日の行はこれとは別に全部焼く（上の docstring 参照）

# --sync の取り込み元。Dropbox が無いMacでは同期を飛ばす。
JUYOMON_DIR = os.path.expanduser(
    "~/Library/CloudStorage/Dropbox/002 物理重要問題集")
LEADALPHA_DIR = os.path.expanduser(
    "~/Library/CloudStorage/Dropbox/002 リード/999 抽出")


class Abort(Exception):
    pass


# ── 重問の台帳から auto: 行を作り直す ──────────────────────────
def core_title(t):
    """別解のYouTubeタイトルから芯だけ取り出す。

    「【別解】保存則を使わず運動方程式で押しきる｜物理重要問題集 力学 問36【高校物理】」
      → 「保存則を使わず運動方程式で押しきる」
    定型の飾りが付かなくなっても壊れないよう、無ければ素通しにする。
    """
    t = t.strip()
    if t.startswith("【別解】"):
        t = t[len("【別解】"):]
    return t.split("｜", 1)[0].strip()


def juyomon_rows(base):
    """公開予約(JST) が入っている行だけを auto: 行にして返す。

    予約が空の行（問1〜11 と未予約127問）は取らない。
    """
    mapping = os.path.join(base, "juyomon-mapping.csv")
    variants = os.path.join(base, "juyomon-variants.csv")
    if not os.path.exists(mapping):
        raise Abort(f"重問の台帳が見つかりません: {mapping}")

    out = []
    with open(mapping, encoding="utf-8-sig") as fp:
        for r in csv.DictReader(fp):
            d = (r.get("公開予約(JST)") or "").strip()
            if not d:
                continue
            num, gist = r["num"].strip(), (r.get("趣旨") or "").strip()
            out.append({
                "日付": d[:10], TIME_COL: d[11:16], "種別": "動画",
                "本文": f'重要問題集 問{num}「{gist}」を公開',
                "リンク": f"juyomon/2026/#q{num}", "出所": "auto:juyomon",
            })

    if os.path.exists(variants):
        with open(variants, encoding="utf-8-sig") as fp:
            for r in csv.DictReader(fp):
                d = (r.get("公開予約(JST)") or "").strip()
                if not d:
                    continue
                num = r["親num"].strip()
                out.append({
                    "日付": d[:10], TIME_COL: d[11:16], "種別": "動画",
                    "本文": f'重要問題集 問{num} 別解「{core_title(r.get("タイトル",""))}」を公開',
                    "リンク": f"juyomon/2026/#q{num}", "出所": "auto:juyomon-variant",
                })
    return out


def leadalpha_rows(base):
    """公開日が入っていて、履歴が「載せる」の章だけを1行ずつ返す。

    リードαは章がまとまって公開されるので、1章＝1行。重問のように
    1動画1行にすると、1つの日曜で25行が並んで更新履歴が埋まってしまう。
    """
    sched = os.path.join(base, "leadalpha-chapter-schedule.csv")
    if not os.path.exists(sched):
        raise Abort(f"リードαの章台帳が見つかりません: {sched}")

    out = []
    with open(sched, encoding="utf-8-sig") as fp:
        for r in csv.DictReader(fp):
            d = (r.get("公開日") or "").strip()
            if not d or (r.get("履歴") or "").strip() != "載せる":
                continue
            ch, title, n = r["章"].strip(), r["章題"].strip(), r["問数"].strip()
            out.append({
                "日付": d[:10], TIME_COL: "", "種別": "動画",
                "本文": f"リードα 第{ch}章「{title}」全{n}問を公開",
                "リンク": f"leadalpha/#ch{ch}", "出所": "auto:leadalpha",
            })
    return out


def sync(base, la_base):
    """auto: で始まる行を捨てて作り直す。manual の行は読みもしない。

    戻り値は (消した数, 入れた数, 手つかずの manual 行数)。
    """
    with open(LEDGER, encoding="utf-8-sig") as fp:
        old = list(csv.DictReader(fp))
    kept = [r for r in old if not (r.get("出所") or "").startswith("auto:")]
    fresh = juyomon_rows(base)
    if os.path.isdir(la_base):
        fresh += leadalpha_rows(la_base)
    else:
        print(f"リードαの同期は飛ばしました（{la_base} がありません）。")

    rows = kept + fresh
    rows.sort(key=lambda r: r["日付"].strip(), reverse=True)

    tmp = LEDGER + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fp:
        # csv の既定は CRLF。手で書いた行と混ざると全行が差分に見えるので LF に揃える。
        w = csv.DictWriter(fp, fieldnames=OUT_COLS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in OUT_COLS})
    os.replace(tmp, LEDGER)
    return len(old) - len(kept), len(fresh), len(kept)


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
        t = (r.get(TIME_COL) or "").strip()
        if t:
            try:
                datetime.time.fromisoformat(t)
            except ValueError:
                raise Abort(f"{i}行目: 時刻が HH:MM ではありません: {t!r}")
        if (r["種別"] or "").strip() not in KIND:
            raise Abort(f"{i}行目: 種別は {'／'.join(KIND)} のどれかです: {r['種別']!r}")
        if not (r["本文"] or "").strip():
            raise Abort(f"{i}行目: 本文が空です。")
        link = (r["リンク"] or "").strip()
        if link:
            if link.startswith("/") or "://" in link:
                raise Abort(f"{i}行目: リンクはリポジトリ内の相対パスで書きます: {link!r}")
            # 飛び先が実在するか。index.html を省いたディレクトリ指定も許す。
            path, _, frag = link.partition("#")
            target = os.path.join(REPO, path)
            page = target if os.path.isfile(target) else os.path.join(target, "index.html")
            if not os.path.isfile(page):
                raise Abort(f"{i}行目: リンク先が見つかりません: {link}")
            # #qNN のような飛び先は、そのidが本当にあるかまで見る。
            # build_site_index.py がアンカーを振るのをやめたら、ここで気づける。
            if frag:
                html_src = open(page, encoding="utf-8").read()
                if f'id="{frag}"' not in html_src:
                    raise Abort(f'{i}行目: リンク先に id="{frag}" がありません: {link}')

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
        at = at_iso(r)
        tag = (f'<a class="upd-row" href="{esc(link)}" data-date="{d}" data-at="{at}" '
               f'style="--k:var(--{color})">'
               if link else
               f'<span class="upd-row" data-date="{d}" data-at="{at}" '
               f'style="--k:var(--{color})">')
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


JST = datetime.timezone(datetime.timedelta(hours=9))


def at_of(r):
    """行の公開日時（JST）。時刻が空なら 00:00 とみなす。

    juyomon/2026/ の settle() は data-pub の**日時**と閲覧時刻を比べている。
    こちらも同じ土俵に乗せるため、日付だけでなく時刻まで持って比較する。
    """
    d = (r["日付"] or "").strip()
    t = (r.get(TIME_COL) or "").strip() or "00:00"
    return datetime.datetime.fromisoformat(f"{d}T{t}:00").replace(tzinfo=JST)


def at_iso(r):
    """data-at 属性に焼く文字列。例 '2026-09-10T18:00:00+09:00'。"""
    return at_of(r).isoformat()


def to_bake(rows):
    """焼く行を選ぶ。未来日は全部、過去は新しい PAST 行だけ。

    rows は日付の降順。未来の行が何件あっても過去が PAST 行残るので、
    表示件数(SHOW)に届かなくなることがない。

    「未来」は**日時**で判定する。日付だけで見ると、18:00公開の行が当日の
    午前中から過去扱いになる（2026-09-10 に問31で実際に起きた）。
    """
    now = datetime.datetime.now(JST)
    out, past = [], 0
    for r in rows:
        if at_of(r) > now:
            out.append(r)
        elif past < PAST:
            out.append(r)
            past += 1
    return out


CSS_MARK = "/* ── 最近の更新"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sync", action="store_true",
                    help="重問の台帳から auto: 行を作り直してから生成する")
    ap.add_argument("--juyomon", default=JUYOMON_DIR,
                    help="重問の台帳があるフォルダ（既定は Dropbox）")
    ap.add_argument("--leadalpha", default=LEADALPHA_DIR,
                    help="リードαの章台帳があるフォルダ（既定は Dropbox）")
    a = ap.parse_args()

    if a.sync:
        base = os.path.expanduser(a.juyomon)
        if not os.path.isdir(base):
            # Dropbox の無いMacでも描画だけは通す。同期しなかったことは必ず告げる。
            print(f"同期を飛ばしました（{base} がありません）。"
                  "updates.csv の中身をそのまま描画します。")
        elif a.dry_run:
            print("--dry-run のため同期していません（--sync は updates.csv を書き換えます）。")
        else:
            try:
                gone, made, manual = sync(base, os.path.expanduser(a.leadalpha))
                print(f"■ 同期  auto行 {gone} → {made} に入れ替え／manual {manual}行は手つかず")
            except Abort as e:
                sys.exit(f"停止: {e}")

    try:
        rows = load()
        top_path = os.path.join(REPO, "index.html")
        src = open(top_path, encoding="utf-8").read()
        out = patch_top(src, to_bake(rows))
    except Abort as e:
        sys.exit(f"停止: {e}")

    today = datetime.date.today().isoformat()
    live = [r for r in rows if r["日付"].strip() <= today][:SHOW]
    ahead = [r for r in rows if r["日付"].strip() > today]

    baked = to_bake(rows)
    print(f"■ updates.csv {len(rows)}行 → {len(baked)}行をHTMLに焼き"
          f"（未来{len(ahead)}＋過去{len(baked) - len(ahead)}）、"
          f"ページ側が新しい{SHOW}件を出す")
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
        for r in drop[:5]:
            print(f"    {r['日付']}  {r['種別']:<3}  {r['本文']}")
        if len(drop) > 5:
            print(f"    … ほか{len(drop) - 5}件")
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
