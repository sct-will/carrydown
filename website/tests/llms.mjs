// Checks dist/llms.txt and dist/llms-full.txt after `npm run build`: the llms.txt format, that every
// English page is listed once and no redirect is, that the docs links go to the Markdown forms, the
// reading order, the "What to tell your agent, and when" phrases against the README, that llms-full.txt follows the same
// order, that every listed address answers 200 from `astro preview`, and that a second run of the
// generator writes byte-identical files.
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { site } from '../site.config.mjs';
import { dist, basePath, listRoutes, startPreview, websiteDir } from './lib.mjs';

let failures = 0;
const fail = (msg) => {
  failures++;
  console.error(`FAIL ${msg}`);
};
const read = (name) => readFileSync(join(dist, name), 'utf8');
const origin = `${site}${basePath}`;

for (const name of ['llms.txt', 'llms-full.txt']) if (!existsSync(join(dist, name))) throw new Error(`dist/${name} is missing. Run \`npm run build\` first.`);
const llms = read('llms.txt');
const full = read('llms-full.txt');
const lines = llms.split('\n');

// Format: an H1 first, a blockquote, no other heading before the first H2, and H2 sections that hold
// only list items with a link.
if (!/^# \S/.test(lines[0])) fail('llms.txt does not start with an H1');
if (!lines.slice(1).find((l) => l.trim())?.startsWith('> ')) fail('llms.txt has no blockquote after the H1');
const firstH2 = lines.findIndex((l) => l.startsWith('## '));
if (lines.slice(1, firstH2).some((l) => /^#{1,6}\s/.test(l))) fail('llms.txt has a heading before its first H2 section');
const sections = new Map();
let current = null;
for (const l of lines.slice(firstH2)) {
  if (l.startsWith('## ')) sections.set((current = l.slice(3)), []);
  else if (l.trim()) {
    if (!/^- \[[^\]]+\]\([^)\s]+\)(: .+)?$/.test(l)) fail(`llms.txt section ${current} has a line that is not a link item: ${l}`);
    else sections.get(current).push(l.match(/\]\(([^)]+)\)/)[1]);
  }
}
for (const s of ['Documentation', 'Pages', 'Optional']) if (!sections.has(s)) fail(`llms.txt has no ${s} section`);
if ([...sections.keys()].pop() !== 'Optional') fail('the Optional section of llms.txt is not the last one');
if (/Redirecting/i.test(llms)) fail('llms.txt lists a redirect page');

// Every English page that is not a redirect is listed once, by its Markdown form where there is one.
const localeCode = /^[a-z]{2}(-[a-z]{2})?$/;
const listed = [...sections.values()].flat();
const pageLinks = [];
for (const route of listRoutes()) {
  const rel = route.slice(basePath.length).replace(/^\/|\/$/g, '');
  if (localeCode.test(rel.split('/')[0])) continue;
  if (/http-equiv="refresh"/i.test(readFileSync(join(dist, rel, 'index.html'), 'utf8'))) continue;
  const md = rel && existsSync(join(dist, `${rel}.md`));
  const want = md ? `${origin}/${rel}.md` : `${origin}/${rel}${rel ? '/' : ''}`;
  const count = listed.filter((u) => u === want).length;
  if (count !== 1) fail(`${route} is listed ${count} times in llms.txt as ${want}`);
  pageLinks.push(want);
}

// The reading order: the start of the documentation, as the build script lists it.
const docs = sections.get('Documentation') ?? [];
const order = ['docs', 'docs/setup', 'docs/plan-owner-guide', 'docs/method', 'docs/sample'].map((r) => `${origin}/${r}.md`);
const positions = order.map((u) => docs.indexOf(u));
if (positions.some((p, i) => p !== i)) fail(`the Documentation section does not start in reading order: ${positions.join(', ')}`);

// The "What to tell your agent, and when" phrases are the README's, word for word.
const readme = readFileSync(join(websiteDir, '..', 'README.md'), 'utf8');
const say = readme.match(/^## What to tell your agent, and when\n([\s\S]*?)^## /m)?.[1] ?? '';
const phrases = [...say.matchAll(/^\|[^|]+\|\s*("[^"]+")\s*\|$/gm)].map((m) => m[1]);
if (phrases.length < 5) fail(`found ${phrases.length} phrases in the README's What to tell your agent, and when section, expected at least 5`);
for (const p of phrases) if (!llms.includes(p)) fail(`llms.txt is missing the phrase ${p}`);

// llms-full.txt has the Documentation and Pages entries in the same order, and no Optional page.
const fullUrls = [...full.matchAll(/^URL: (\S+)$/gm)].map((m) => m[1]);
const expected = [...(sections.get('Documentation') ?? []), ...(sections.get('Pages') ?? [])].map((u) => u.replace(/\.md$/, '/'));
if (JSON.stringify(fullUrls) !== JSON.stringify(expected)) fail(`llms-full.txt does not follow llms.txt:\n  ${fullUrls.join('\n  ')}`);
for (const u of sections.get('Optional') ?? []) if (fullUrls.includes(u.replace(/\.md$/, '/'))) fail(`llms-full.txt holds the optional page ${u}`);
// Each docs section is the page's Markdown form, whole.
for (const u of sections.get('Documentation') ?? []) {
  const rel = u.slice(origin.length + 1);
  if (!rel.endsWith('.md')) {
    fail(`the Documentation entry ${u} is not a Markdown form`);
    continue;
  }
  const body = readFileSync(join(dist, rel), 'utf8').replace(/^# [^\n]*\n+/, '').trim();
  if (!full.includes(body)) fail(`llms-full.txt does not hold the whole Markdown of ${rel}`);
}

// A second run writes the same bytes.
execFileSync(process.execPath, [join(websiteDir, 'scripts/build-llms.mjs')], { stdio: 'ignore' });
if (read('llms.txt') !== llms) fail('a second run of build-llms.mjs wrote a different llms.txt');
if (read('llms-full.txt') !== full) fail('a second run of build-llms.mjs wrote a different llms-full.txt');

// Every address on the site answers 200, and the Markdown forms answer as Markdown.
const { origin: preview, stop } = await startPreview(4398);
try {
  const local = [...new Set([`${origin}/llms.txt`, `${origin}/llms-full.txt`, ...pageLinks, ...listed.filter((u) => u.startsWith(origin))])];
  for (const u of local) {
    const res = await fetch(preview + basePath + u.slice(origin.length));
    await res.arrayBuffer();
    if (res.status !== 200) fail(`${res.status} ${u}`);
    else if (u.endsWith('.md') && !/text\/markdown/.test(res.headers.get('content-type') ?? '')) fail(`${u} is served as ${res.headers.get('content-type')}`);
  }
} finally {
  await stop();
}

console.log(`llms: ${pageLinks.length} pages listed, ${phrases.length} phrases, ${fullUrls.length} pages in llms-full.txt (${Buffer.byteLength(full)} bytes), ${failures} failure(s)`);
if (failures) process.exit(1);
