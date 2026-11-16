// Starts `astro preview`, requests every built route in every locale and every internal link and asset
// those pages reference, and expects 200 for each. Run after `npm run build`.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { dist, basePath, listRoutes, startPreview } from './lib.mjs';

const routes = listRoutes();
const { origin, stop } = await startPreview();
let failures = 0;
const checked = new Set();

async function check(path, from) {
  if (checked.has(path)) return;
  checked.add(path);
  const res = await fetch(origin + path);
  const ok = res.status === 200;
  if (!ok) {
    failures++;
    console.error(`FAIL ${res.status} ${path}${from ? `  (linked from ${from})` : ''}`);
  } else if (!from) {
    console.log(`ok   200 ${path}`);
  }
  await res.arrayBuffer();
}

try {
  for (const route of routes) await check(route);

  // Internal links and assets: every same-site href and src in the built pages.
  for (const route of routes) {
    const rel = route.slice(basePath.length);
    const html = readFileSync(join(dist, rel, 'index.html'), 'utf8');
    for (const m of html.matchAll(/\b(?:href|src)="([^"#?]+)(?:[#?][^"]*)?"/g)) {
      const target = m[1];
      if (!target.startsWith('/') || target.startsWith('//')) continue;
      if (basePath && !target.startsWith(`${basePath}/`) && target !== basePath) {
        failures++;
        console.error(`FAIL outside base path ${target}  (linked from ${route})`);
        continue;
      }
      await check(target, route);
    }
  }
} finally {
  await stop();
}

console.log(`routes: ${routes.length} pages, ${checked.size} URLs checked, ${failures} failure(s)`);
if (failures) process.exit(1);
