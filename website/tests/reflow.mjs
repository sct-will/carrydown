// Screenshots every page at six widths in the site's one theme and fails on any layout problem:
//   - horizontal overflow (scrollWidth > innerWidth)
//   - rendered text smaller than 12 px (HTML text; SVG text is reported, see below)
//   - tap targets under 44 px (buttons, selects, button-like links, header and footer links)
// Screenshots go to tests/screenshots/ (gitignored). Run after `npm run build`.
import { mkdirSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from 'playwright';
import { websiteDir, basePath, startPreview } from './lib.mjs';
import { siteRoutes, routeFor, requireBuilt } from './sets.mjs';

const widths = [375, 414, 768, 1024, 1280, 1440];

// A bounded set, so the run takes minutes even with hundreds of docs pages. Each job is a page and the
// widths to check it at: the four site pages in English at every width, the same pages in Japanese
// (the CJK check) at the narrowest and a wide width, the docs index and the setup page in English, and
// one fallback docs page.
const jobs = [
  ...siteRoutes('en').map((route) => ({ route, widths })),
  ...siteRoutes('ja').map((route) => ({ route, widths: [375, 1280] })),
  ...['/docs/', '/docs/setup/'].map((p) => ({ route: routeFor('en', p), widths: [375, 768, 1440] })),
  { route: routeFor('de', '/docs/setup/'), widths: [375, 1280] },
];
requireBuilt(jobs.map((j) => j.route));
// The site has one theme, light.
const themes = ['light'];
const shots = join(websiteDir, 'tests', 'screenshots');
rmSync(shots, { recursive: true, force: true });
mkdirSync(shots, { recursive: true });

const { origin, stop } = await startPreview();
const browser = await chromium.launch();
const failures = [];
const notes = [];

/** Runs in the page. Returns problems found. */
function audit(isDocs) {
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
    // Docs pages hold generated Markdown. Their code copy buttons, sidebar group toggles and details
    // summaries are Starlight's own and meet the 24 px WCAG 2.2 minimum that axe checks, not the 44 px
    // target of the site pages and the shared header and footer. The 44 px check stays on the chrome.
    if (isDocs && el.closest('.expressive-code, .sidebar-content, main details')) continue;
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
    for (const { route, widths } of jobs) {
      for (const width of widths) {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(origin + route, { waitUntil: 'networkidle' });
        await page.evaluate(() => document.fonts.ready);
        // The page's timed animations (the hero rising on load) end before the audit, so it sees every
        // element in its final state. Scroll-driven animations have no end and are left alone.
        await page.evaluate(() => Promise.all(document.getAnimations().filter((a) => a.timeline instanceof DocumentTimeline).map((a) => a.finished.catch(() => {}))));
        const name = `${route.slice(basePath.length).replace(/^\/|\/$/g, '').replace(/\//g, '_') || 'home'}-${width}-${theme}.png`;
        await page.screenshot({ path: join(shots, name), fullPage: true });
        const problems = await page.evaluate(audit, route.includes('/docs/'));
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
const shotCount = jobs.reduce((n, j) => n + j.widths.length, 0) * themes.length;
console.log(`reflow: ${jobs.length} page(s), ${shotCount} screenshots (widths per page), in tests/screenshots/`);
if (failures.length) {
  for (const f of unique(failures)) console.error(`FAIL ${f}`);
  console.error(`reflow: ${unique(failures).length} problem(s)`);
  process.exit(1);
}
console.log('reflow: no overflow, no small text, no small tap targets');
