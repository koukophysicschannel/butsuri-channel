/* butsuri-channel の Service Worker。
 *
 * ──────────────────────────────────────────────
 * なぜ入れたか
 * ──────────────────────────────────────────────
 * 1. Android Chrome に「アプリをインストール」を出すため。manifest だけでは
 *    メニューが「ホーム画面に追加」止まりで、インストール扱いにならない。
 *    Chrome の要件が「fetch ハンドラを持つ Service Worker」なので、
 *    このファイルの存在自体が要件を満たす役割を持っている。
 * 2. 電車の中など回線が切れた場所でも、一度見た目次を開けるようにするため。
 *
 * ──────────────────────────────────────────────
 * いちばん怖いのは「キャッシュが古いまま出続ける」事故
 * ──────────────────────────────────────────────
 * このサイトは動画や問題を足すたびに更新される。素朴にキャッシュ優先で書くと、
 * 更新したのに生徒の端末では何日も古い目次が出続ける、という最悪の壊れ方をする。
 * しかも Service Worker は端末側に居座るので、こちらから直しにくい。
 *
 * なので **HTML は必ずネットワークを先に叩く**（network-first）。
 * オンラインなら今までと同じで常に最新。キャッシュを使うのは通信が失敗したときだけ。
 * 速度より鮮度を取る。アイコンや manifest のような、めったに変わらず
 * 古くても実害の無いものだけ stale-while-revalidate で先にキャッシュから返す。
 *
 * ──────────────────────────────────────────────
 * 外したくなったとき（キルスイッチ）
 * ──────────────────────────────────────────────
 * このファイルを消すだけでは、既に登録済みの端末からは消えない。
 * 中身を下記だけにして push すると、次回アクセス時に各端末から自分を外す。
 *
 *     self.addEventListener('install', () => self.skipWaiting());
 *     self.addEventListener('activate', (e) => e.waitUntil((async () => {
 *       await self.registration.unregister();
 *       for (const k of await caches.keys()) await caches.delete(k);
 *       for (const c of await self.clients.matchAll()) c.navigate(c.url);
 *     })()));
 *
 * index.html 側の register() の行も一緒に消すこと。
 */

// 中身の持ち方を変えたときはここを上げる。activate で古い版を全部消す。
const CACHE = 'butsuri-channel-v1';

// インストール時に取っておくもの。オフラインの入口になるトップページと、
// ホーム画面アイコンまわりだけ。各ページのHTMLは入れない
// （数が増えるし、実際に見たページだけ後からキャッシュされれば足りる）。
const SHELL = [
  './',
  './favicon.ico',
  './apple-touch-icon.png',
  './icon-192.png',
  './icon-512.png',
  './icon-512-maskable.png',
  './site.webmanifest',
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    // addAll は1つでも失敗すると全部落ちてインストール自体が失敗する。
    // アイコンを1枚差し替え損ねただけでSWが入らなくなるのは割に合わないので、
    // 1件ずつ入れて失敗は握りつぶす。
    await Promise.all(SHELL.map((url) => cache.add(url).catch(() => {})));
    self.skipWaiting();   // 新しい版をすぐ有効にする（不具合を直したとき早く行き渡る）
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

// 保存してよい応答か。opaque（CORS外）や 404 を保存すると、
// 壊れたものを配り続けることになるので弾く。
function storable(res) {
  return res && res.status === 200 && res.type === 'basic';
}

self.addEventListener('fetch', (event) => {
  const req = event.request;

  // GET 以外は触らない。
  if (req.method !== 'GET') return;

  // 別オリジンには一切手を出さない。Google Analytics・YouTube・Google Fonts が該当する。
  // 特に Analytics を横取りすると計測が壊れるし、キャッシュしてよいものでもない。
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // ページの表示（HTML）はネットワーク優先。ここが鮮度の担保。
  if (req.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const res = await fetch(req);
        if (storable(res)) {
          const cache = await caches.open(CACHE);
          cache.put(req, res.clone());
        }
        return res;
      } catch (err) {
        // ここに来るのは通信が無いときだけ。
        const cached = await caches.match(req, { ignoreSearch: true });
        if (cached) return cached;
        // 見たことのないページなら、せめてトップの目次を出す。
        const top = await caches.match('./');
        if (top) return top;
        throw err;
      }
    })());
    return;
  }

  // それ以外の同一オリジン（アイコン・manifest など）は stale-while-revalidate。
  // まずキャッシュを返して即座に表示し、裏で取り直して次回に備える。
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(req);
    const network = fetch(req).then((res) => {
      if (storable(res)) cache.put(req, res.clone());
      return res;
    }).catch(() => null);
    return cached || (await network) || Response.error();
  })());
});
