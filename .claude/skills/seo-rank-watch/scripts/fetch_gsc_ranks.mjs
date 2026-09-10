#!/usr/bin/env node
/**
 * fetch_gsc_ranks.mjs — Google Search Console から watchwords.json の
 * キーワードの平均順位・impressions・clicksを取得し、rank-history.json に追記する。
 *
 * 【未実装スタブ】2026-09-10時点、このマシンにGSC APIの認証情報が見つからなかったため、
 * 実際にAPIを呼ぶ部分はまだ書かれていない。認証情報を用意したら下記TODOを実装すること。
 * 詳しくは ../SKILL.md の「GSC接続状況」を参照。
 *
 * 想定する使い方（実装後）:
 *   node fetch_gsc_ranks.mjs --repo . --append        # 直近の実測値を rank-history.json に追記
 *   node fetch_gsc_ranks.mjs --repo . --days 7         # 直近7日分を取得（改善レビュー用）
 *
 * TODO:
 *   1. `npm install googleapis` をこのリポジトリに追加する
 *   2. サービスアカウントキーのパスを環境変数（例 GSC_SERVICE_ACCOUNT_KEY）で受け取る。
 *      認証情報をリポジトリにコミットしないこと。
 *   3. google.auth.GoogleAuth でJWTクライアントを作り、
 *      searchconsole('v1').searchanalytics.query を
 *      siteUrl: "https://koukophysicschannel.github.io/butsuri-channel/",
 *      dimensions: ["query"], rowLimit: 25000 で呼ぶ
 *   4. watchwords.json の各 keyword に一致する行を突き合わせ、
 *      { date, keyword, targetPath, method: "gsc", rank, impressions, clicks } を
 *      data/seo/rank-history.json に追記する（既存データは書き換えない）
 */

console.error(
  "[fetch_gsc_ranks.mjs] 未実装です。GSC APIの認証情報が用意でき次第、このスクリプトを実装してください。" +
  "詳しくは .claude/skills/seo-rank-watch/SKILL.md を参照。"
);
process.exit(1);
