// Load public Amazon list pages (Movers & Shakers / New Releases / Best Sellers) ONCE each
// in a normal headless browser and read the rendered product grid.
// No retries, no bot-check circumvention: a page that shows a bot check is logged as BLOCKED.
// Usage: node fetch_amazon_lists.js <urls.txt> <out.json>
const { chromium } = require('playwright');
const fs = require('fs');
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const [list, out] = process.argv.slice(2);
  const urls = fs.readFileSync(list, 'utf8').split('\n').map(s => s.trim()).filter(Boolean);
  const browser = await chromium.launch();
  const page = await browser.newPage({ locale: 'en-GB' });
  const results = [];
  for (const url of urls) {
    const rec = { url, fetched_utc: new Date().toISOString() };
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await sleep(2500);
      for (let i = 0; i < 8; i++) { await page.mouse.wheel(0, 2500); await sleep(350); }
      rec.title = await page.title();
      rec.items = await page.$$eval('#gridItemRoot', els => els.map(e => {
        const a = e.querySelector('a.a-link-normal[href*="/dp/"]');
        const asin = a ? (a.href.match(/\/dp\/(\w{10})/) || [])[1] : '';
        return { text: e.innerText.replace(/\s+/g, ' ').trim().slice(0, 400), asin };
      }));
      rec.status = rec.items.length ? 'OK' : 'BLOCKED_OR_EMPTY';
    } catch (e) { rec.status = 'ERROR ' + e.message; }
    console.error(rec.status, (rec.items || []).length, url);
    results.push(rec);
    fs.writeFileSync(out, JSON.stringify(results, null, 1));
    await sleep(3000);
  }
  await browser.close();
})();
