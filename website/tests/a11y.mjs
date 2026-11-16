// Runs axe-core over a bounded set of built pages and fails on any violation.
// The rules are the WCAG 2.0, 2.1 and 2.2 level A and AA sets. Run after `npm run build`.
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
import { startPreview } from './lib.mjs';
import { localeCodes } from '../src/i18n/locales.mjs';
import { siteRoutes, englishDocsRoutes, fallbackDocsRoute, otherLocales, requireBuilt } from './sets.mjs';

const tags = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
// A bounded set, so the run takes minutes even with hundreds of docs pages. In both themes: the four
// site pages in every locale. In the light theme only: every English docs page and one fallback docs
// page per other locale.
const both = requireBuilt(localeCodes.flatMap((l) => siteRoutes(l)));
const lightOnly = requireBuilt([...englishDocsRoutes(), ...otherLocales.map(fallbackDocsRoute)]);
const plan = { light: [...both, ...lightOnly], dark: both };
const themes = Object.keys(plan);
const routes = [...new Set([...both, ...lightOnly])];
const { origin, stop } = await startPreview(4401);
const browser = await chromium.launch();
let violations = 0;
let scans = 0;

try {
  for (const theme of themes) {
    const context = await browser.newContext({ colorScheme: theme, viewport: { width: 1280, height: 800 } });
    const page = await context.newPage();
    for (const route of plan[theme]) {
      await page.goto(origin + route, { waitUntil: 'networkidle' });
      await page.evaluate(() => document.fonts.ready);
      const result = await new AxeBuilder({ page }).withTags(tags).analyze();
      scans++;
      for (const v of result.violations) {
        violations += v.nodes.length;
        console.error(`FAIL ${route} (${theme}) ${v.id} [${v.impact}] ${v.help}`);
        for (const n of v.nodes.slice(0, 3)) console.error(`       ${n.target.join(' ')}\n       ${n.failureSummary?.split('\n').slice(0, 2).join(' ')}`);
      }
    }
    await context.close();
  }
} finally {
  await browser.close();
  await stop();
}

console.log(`a11y: ${routes.length} page(s), ${scans} scans (${both.length} pages in both themes, ${lightOnly.length} in light only), ${violations} violation(s)`);
if (violations) process.exit(1);
