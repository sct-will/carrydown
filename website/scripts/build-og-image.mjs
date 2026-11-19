// Renders the Open Graph and Twitter card image, 1200 by 630, into dist/og-image.png after `astro build`.
//
// The card is the mark at 140 px and the title "Carried-context development goes beyond spec-driven development. The context travels with the work." on
// the navy ground, set in Fraunces from the fontsource package, with "travels with the work." in the
// italic amber as on the home page, and the site name in Atkinson Hyperlegible Next. The text is drawn
// by Chromium through Playwright, which loads the real font files. No network is used.
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
const MARK_SIZE = 140;
const NAVY = '#0F1420';
const INK = '#EEF1F6';
const MUTED = '#A9B2C3';

// The mark in the lighter teal of the navy theme. Its box is wider than tall; MARK_SIZE is the height.
const mark = readFileSync(join(websiteDir, 'src/assets/logo/mark.svg'), 'utf8')
  .replace('fill="#4aa4aa"', 'fill="#5fb8b8"')
  .replace(' role="img" aria-label="carrydown mark"', ` aria-hidden="true" height="${MARK_SIZE}"`);
const AMBER = '#E8A33D';
const fontFile = (pkg, name) => readFileSync(join(websiteDir, 'node_modules/@fontsource-variable', pkg, 'files', name)).toString('base64');
const display = fontFile('fraunces', 'fraunces-latin-full-normal.woff2');
const displayItalic = fontFile('fraunces', 'fraunces-latin-full-italic.woff2');
const text = fontFile('atkinson-hyperlegible-next', 'atkinson-hyperlegible-next-latin-wght-normal.woff2');

const html = `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: 'Fraunces Variable'; font-weight: 100 900; font-style: normal; src: url(data:font/woff2;base64,${display}) format('woff2-variations'); }
@font-face { font-family: 'Fraunces Variable'; font-weight: 100 900; font-style: italic; src: url(data:font/woff2;base64,${displayItalic}) format('woff2-variations'); }
@font-face { font-family: 'Atkinson Hyperlegible Next Variable'; font-weight: 200 800; src: url(data:font/woff2;base64,${text}) format('woff2-variations'); }
html, body { margin: 0; width: ${WIDTH}px; height: ${HEIGHT}px; background: ${NAVY}; }
body { position: relative; font-family: 'Atkinson Hyperlegible Next Variable', sans-serif; color: ${INK}; overflow: hidden; }
.mark { position: absolute; left: 96px; top: 84px; height: ${MARK_SIZE}px; }
.mark svg { display: block; }
h1 { position: absolute; left: 96px; top: 250px; margin: 0; font-family: 'Fraunces Variable', serif; font-size: 60px; line-height: 1.08; font-weight: 450; letter-spacing: -0.022em; width: 1010px; font-variation-settings: 'opsz' 144, 'SOFT' 40; }
h1 em { font-style: italic; font-weight: 400; color: ${AMBER}; font-variation-settings: 'opsz' 144, 'SOFT' 100, 'WONK' 1; }
p { position: absolute; left: 96px; bottom: 64px; margin: 0; font-size: 30px; font-weight: 500; color: ${MUTED}; }
</style></head><body>
<div class="mark">${mark}</div>
<h1>Carried-context development goes beyond spec-driven development. The context <em>travels with the work.</em></h1>
<p>Carried-context development</p>
</body></html>`;

async function render() {
  const { chromium } = await import('playwright');
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: WIDTH, height: HEIGHT }, deviceScaleFactor: 1 });
    await page.setContent(html, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    const ok = await page.evaluate(() => document.fonts.check("450 60px 'Fraunces Variable'") && document.fonts.check("500 30px 'Atkinson Hyperlegible Next Variable'"));
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
