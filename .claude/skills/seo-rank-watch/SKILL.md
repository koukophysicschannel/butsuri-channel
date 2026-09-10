---
name: seo-rank-watch
description: 高校物理解説チャンネル（https://koukophysicschannel.github.io/butsuri-channel/）のSEO順位を定点観測し、1回の実行につき1キーワードだけ改善する。Google Search Consoleの実測順位（未接続の場合はWebSearch概算）を使い、data/seo/ 配下のJSONに記録を積み上げていく。
---

# seo-rank-watch

高校物理解説チャンネルのSEO改善を、少しずつ・記録を残しながら進めるためのスキル。
**1回の実行で改善するキーワードは1つだけ**。無理に対象を作らない。

- 対象サイト: `https://koukophysicschannel.github.io/butsuri-channel/`
- リポジトリ: `~/Projects/butsuri-channel`
- データ: `data/seo/watchwords.json`（監視キーワード）/ `data/seo/rank-history.json`（順位の実測履歴・追記専用）/ `data/seo/improvement-log.json`（改善の記録）

## GSC接続状況（2026-09-10時点）

このマシン上にGoogle Search Console APIの認証情報（サービスアカウントJSON、OAuthクライアント、gcloud ADCのいずれも）が見つからなかったため、
`scripts/fetch_gsc_ranks.mjs` は**未実装のスタブ**になっている。2026-09-10の初回ラウンドはGSCなしで、WebSearchによる概算のみで実施した。

GSC接続ができるようになったら:
1. サービスアカウントJSON（推奨）を用意し、対象プロパティに閲覧権限で追加する
2. `npm install googleapis`（このリポジトリにはまだ入っていない）
3. `scripts/fetch_gsc_ranks.mjs` を実装する（Search Console API `searchanalytics.query`、`dimensions: ["query"]` で `watchwords.json` の各キーワードのaverage position / impressions / clicksを取得し、`rank-history.json` に追記する）
4. 認証情報のパスは環境変数（例 `GSC_SERVICE_ACCOUNT_KEY`）で渡し、**リポジトリにはコミットしない**

## 手順

1. **順位を測定する**
   `node .claude/skills/seo-rank-watch/scripts/fetch_gsc_ranks.mjs --repo . --append` を実行し、
   `data/seo/watchwords.json` のキーワードについてGSCの平均順位・impressions・clicksを取得する。
   GSCが使えない場合のみWebSearchで概算順位を確認する（GSCを正とする。GSC実測が復活したらWebSearch概算のrank:nullを実測で上書きしていく）。

2. **7日経過した改善をレビューする**
   `data/seo/improvement-log.json` を確認し、`nextReviewDate <= 今日` のキーワードがあれば
   `node .claude/skills/seo-rank-watch/scripts/fetch_gsc_ranks.mjs --repo . --days 7` で7日GSCを取得し、
   - 1位 → `achieved`
   - 改善したが未達 → `active`
   - 効果なし → `active`（次回は別の改善方法を試す）
   と判定して `improvement-log.json` に記録する。

3. **今日改善するキーワードを1つだけ選ぶ**
   `observing` と `achieved` は除外。優先順位:
   1. 2〜10位＋impressionsあり
   2. 11〜20位＋impressions多い
   3. 改善したが未達／効果なし
   4. 高優先度のrank:null
   5. GSCで見つかった有望な未登録クエリ

   候補がなければ順位チェックとレポートだけで終了する（無理に対象を作らない）。

4. **検索ニーズを分析する**
   - 「誰が・何を知りたくて検索しているか」を1〜2文で定義する
   - WebSearchで現在の上位1〜3ページを確認する
   - 上位ページと対象ページを比較し、不足情報をギャップとして特定する
   - 方針: 文章量を増やすのではなく、検索ユーザーが欲しい情報を追加する

5. **選んだキーワードを1つだけ改善する**
   title/description/intro/FAQ改善、不足コンテンツ追加、内部リンク、実データ追加など、
   ギャップに応じて必要なものだけ実装する。
   **noindex変更や大きなページ構造変更は勝手に適用せず、提案だけして承認を待つ。**

6. **改善を記録する**
   `data/seo/improvement-log.json` に以下を追記し、`data/seo/*.json` の変更をコミットする。
   ```json
   {
     "keyword": "...",
     "targetPath": "...",
     "status": "observing",
     "nextReviewDate": "今日+7日",
     "actions": [{
       "date": "...",
       "rankAtAction": null,
       "needs": "検索ニーズ",
       "done": "実際に行った改善"
     }]
   }
   ```
   既存キーワードへの追加アクションは、同じキーワードのオブジェクトの `actions` 配列に追記する（新規オブジェクトを作らない）。

## ガードレール

- Google SERPを独自スクリプトでスクレイピングしない
- 1回につき改善は1キーワードだけ
- `observing` の7日間クールダウンを厳守する（`nextReviewDate` まで再改善しない）
- `rank-history.json` の過去データは書き換えない（追記専用）
- 認証キーや秘密情報を出力・コミットしない
- 改善効果を断定しない（変更内容を報告し、効果判定は次回の実測で行う）
