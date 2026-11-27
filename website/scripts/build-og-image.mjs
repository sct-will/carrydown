// Renders the Open Graph and Twitter card image, 1200 by 630, into dist/og-image.png after `astro build`.
//
// The card is the home page's palette on pine-deep: the mark at 120 px with paper letters and the ochre
// thread, the title "Carried-context development gives each coding agent decisions and sources behind
// the work." in Atkinson Hyperlegible Next at weight 700 in paper, with "decisions and sources" in ochre
// as the home page sets it in amber, and the site name in cream-soft. The text is drawn by Chromium through
// Playwright, which loads the real font files from the fontsource package. No network is used.
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
const MARK_SIZE = 120;
const PINE_DEEP = '#0E241E';
const PAPER = '#F5F1E8';
const OCHRE = '#D9A441';
const CREAM_SOFT = '#B9C2B4';

// The title, as in src/i18n/en.ts (home.h1 and home.h1Emphasis).
const TITLE = 'Carried-context development gives each coding agent decisions and sources behind the work.';
const EMPHASIS = 'decisions and sources';

// The mark from the master file: paper letters and the ochre thread. Its box is wider than tall;
// MARK_SIZE is the height.
const mark = readFileSync(join(websiteDir, 'src/assets/logo/mark.svg'), 'utf8')
  .replace('stroke="#1D1A15"', `stroke="${PAPER}"`)
  .replace('stroke="#A8740C"', `stroke="${OCHRE}"`)
  .replace(' role="img" aria-label="carrydown mark"', ` aria-hidden="true" height="${MARK_SIZE}"`);
const fontFile = (pkg, name) => readFileSync(join(websiteDir, 'node_modules/@fontsource-variable', pkg, 'files', name)).toString('base64');
const text = fontFile('atkinson-hyperlegible-next', 'atkinson-hyperlegible-next-latin-wght-normal.woff2');
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
const [before, after] = TITLE.split(EMPHASIS);

const html = `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: 'Atkinson Hyperlegible Next Variable'; font-weight: 200 800; src: url(data:font/woff2;base64,${text}) format('woff2-variations'); }
html, body { margin: 0; width: ${WIDTH}px; height: ${HEIGHT}px; background: ${PINE_DEEP}; }
body { position: relative; font-family: 'Atkinson Hyperlegible Next Variable', sans-serif; color: ${PAPER}; overflow: hidden; }
.mark { position: absolute; left: 96px; top: 80px; height: ${MARK_SIZE}px; }
.mark svg { display: block; }
h1 { position: absolute; left: 96px; top: 236px; margin: 0; font-size: 58px; line-height: 1.06; font-weight: 700; letter-spacing: -0.022em; width: 1010px; text-wrap: balance; }
h1 em { font-style: normal; font-weight: 700; color: ${OCHRE}; }
p { position: absolute; left: 96px; bottom: 64px; margin: 0; font-size: 30px; font-weight: 500; color: ${CREAM_SOFT}; }
</style></head><body>
<div class="mark">${mark}</div>
<h1>${esc(before)}<em>${esc(EMPHASIS)}</em>${esc(after ?? '')}</h1>
<p>Carried-context development</p>
</body></html>`;

async function render() {
  const { chromium } = await import('playwright');
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: WIDTH, height: HEIGHT }, deviceScaleFactor: 1 });
    await page.setContent(html, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    const ok = await page.evaluate(() => document.fonts.check("700 58px 'Atkinson Hyperlegible Next Variable'") && document.fonts.check("500 30px 'Atkinson Hyperlegible Next Variable'"));
    if (!ok) throw new Error('the fonts did not load');
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
