// Renders the Open Graph and Twitter card image, 1200 by 630, into dist/og-image.png after `astro build`.
//
// The card is the "Pinned pages" mark at 160 px and the title "Context that travels with the work." on
// the navy ground, set in Inter from the fontsource package. The text is drawn by Chromium through
// Playwright, which loads the real Inter font file. No network is used.
//
// If Chromium is not installed, the script copies the committed public/og-image.png instead and says so.
// To refresh the committed file after a change, run `node scripts/build-og-image.mjs --public`.
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const websiteDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const dist = join(websiteDir, 'dist');
const committed = join(websiteDir, 'public', 'og-image.png');
const writePublic = process.argv.includes('--public');

const WIDTH = 1200;
const HEIGHT = 630;
const MARK_SIZE = 160;
const NAVY = '#0F1420';
const INK = '#EEF1F6';
const MUTED = '#A9B2C3';

// The mark's drawing sits inside its 64 unit box, so the box is offset to line the glyph up with the text.
const mark = readFileSync(join(websiteDir, 'src/assets/logo/I-pages-dark.svg'), 'utf8')
  .replace(" width='64' height='64'", ` width='${MARK_SIZE}' height='${MARK_SIZE}'`)
  .replace(" role='img'", " aria-hidden='true'");
const fontPath = join(websiteDir, 'node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2');
const font = readFileSync(fontPath).toString('base64');

const html = `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: 'Inter Variable'; font-weight: 100 900; src: url(data:font/woff2;base64,${font}) format('woff2'); }
html, body { margin: 0; width: ${WIDTH}px; height: ${HEIGHT}px; background: ${NAVY}; }
body { position: relative; font-family: 'Inter Variable', sans-serif; color: ${INK}; overflow: hidden; }
.mark { position: absolute; left: 66px; top: 78px; width: ${MARK_SIZE}px; height: ${MARK_SIZE}px; }
.mark svg { display: block; }
h1 { position: absolute; left: 96px; top: 300px; margin: 0; font-size: 84px; line-height: 1.08; font-weight: 700; letter-spacing: -0.02em; width: 900px; }
p { position: absolute; left: 96px; bottom: 64px; margin: 0; font-size: 30px; font-weight: 500; color: ${MUTED}; }
</style></head><body>
<div class="mark">${mark}</div>
<h1>Context that travels with the work.</h1>
<p>Carried-context development</p>
</body></html>`;

async function render() {
  const { chromium } = await import('playwright');
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: WIDTH, height: HEIGHT }, deviceScaleFactor: 1 });
    await page.setContent(html, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    const ok = await page.evaluate(() => document.fonts.check("700 84px 'Inter Variable'"));
    if (!ok) throw new Error('the Inter font did not load');
    return await page.screenshot({ type: 'png', clip: { x: 0, y: 0, width: WIDTH, height: HEIGHT } });
  } finally {
    await browser.close();
  }
}

mkdirSync(dist, { recursive: true });
const target = join(dist, 'og-image.png');
try {
  const png = await render();
  writeFileSync(target, png);
  if (writePublic) writeFileSync(committed, png);
  console.log(`build-og-image: wrote ${target} (${WIDTH}x${HEIGHT})${writePublic ? ' and public/og-image.png' : ''}`);
} catch (err) {
  if (!existsSync(committed)) throw err;
  copyFileSync(committed, target);
  console.warn(`build-og-image: WARNING could not render (${err.message}). Copied the committed public/og-image.png instead.`);
}
