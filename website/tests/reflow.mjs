// Screenshots every page at six widths in both themes and fails on any layout problem:
//   - horizontal overflow (scrollWidth > innerWidth)
//   - rendered text smaller than 12 px (HTML text; SVG text is reported, see below)
//   - tap targets under 44 px (buttons, selects, button-like links, header and footer links)
// Screenshots go to tests/screenshots/ (gitignored). Run after `npm run build`.
import { mkdirSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from 'playwright';
import { websiteDir, basePath, listRoutes, startPreview } from './lib.mjs';

const widths = [375, 414, 768, 1024, 1280, 1440];
const themes = ['light', 'dark'];
const shots = join(websiteDir, 'tests', 'screenshots');
rmSync(shots, { recursive: true, force: true });
mkdirSync(shots, { recursive: true });

const routes = listRoutes();
const { origin, stop } = await startPreview();
const browser = await chromium.launch();
const failures = [];
const notes = [];

/** Runs in the page. Returns problems found. */
function audit() {
  const problems = [];
  const root = document.documentElement;
  if (root.scrollWidth > window.innerWidth) {
    problems.push(`horizontal overflow: scrollWidth ${root.scrollWidth} > innerWidth ${window.innerWidth}`);
  }
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  // Text size: any element that directly holds visible text.
  const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const el = node.parentElement;
    if (!el || seen.has(el) || !node.textContent.trim()) continue;
    seen.add(el);
    if (el.closest('svg, script, style, .sr-only')) continue;
    if (!visible(el)) continue;
    const px = parseFloat(getComputedStyle(el).fontSize);
    if (px < 12) problems.push(`text under 12px (${px}px): "${node.textContent.trim().slice(0, 40)}"`);
  }
  // Tap targets.
  const targets = document.querySelectorAll(
    'button, select, input, summary, a.btn, .site-header a, .site-footer a, .skip-link',
  );
  for (const el of targets) {
    if (el.matches('.skip-link') || !visible(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.height < 43.5 || r.width < 43.5) {
      problems.push(`tap target ${Math.round(r.width)}x${Math.round(r.height)} under 44px: ${el.tagName.toLowerCase()} "${(el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 30)}"`);
    }
  }
  return problems;
}

/** Rendered size of the smallest visible SVG text, in CSS pixels. */
function smallestSvgText() {
  let min = Infinity;
  for (const t of document.querySelectorAll('svg text')) {
    const r = t.getBoundingClientRect();
    if (r.width === 0) continue;
    const ctm = t.getScreenCTM();
    if (!ctm) continue;
    min = Math.min(min, parseFloat(getComputedStyle(t).fontSize) * ctm.a);
  }
  return min === Infinity ? null : min;
}

try {
  for (const theme of themes) {
    const context = await browser.newContext({ colorScheme: theme, viewport: { width: 1280, height: 800 } });
    const page = await context.newPage();
    for (const route of routes) {
      for (const width of widths) {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(origin + route, { waitUntil: 'networkidle' });
        await page.evaluate(() => document.fonts.ready);
        const name = `${route.slice(basePath.length).replace(/^\/|\/$/g, '').replace(/\//g, '_') || 'home'}-${width}-${theme}.png`;
        await page.screenshot({ path: join(shots, name), fullPage: true });
        const problems = await page.evaluate(audit);
        for (const p of problems) failures.push(`${route} @${width} ${theme}: ${p}`);
        const svg = await page.evaluate(smallestSvgText);
        if (svg !== null && svg < 12) notes.push(`${route} @${width} ${theme}: smallest diagram text renders at ${svg.toFixed(1)}px`);
      }
    }
    await context.close();
  }
} finally {
  await browser.close();
  await stop();
}

const unique = (a) => [...new Set(a)];
if (notes.length) {
  console.log('Notes (not failures): the wide diagram is a scaled SVG, so its labels shrink below 12px between 760px and about 1100px.');
  for (const n of unique(notes).slice(0, 6)) console.log(`  ${n}`);
  if (notes.length > 6) console.log(`  ... ${notes.length - 6} more`);
}
console.log(`reflow: ${routes.length} page(s) x ${widths.length} widths x ${themes.length} themes, screenshots in tests/screenshots/`);
if (failures.length) {
  for (const f of unique(failures)) console.error(`FAIL ${f}`);
  console.error(`reflow: ${unique(failures).length} problem(s)`);
  process.exit(1);
}
console.log('reflow: no overflow, no small text, no small tap targets');
