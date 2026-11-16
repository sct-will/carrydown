// Writes dist/llms.txt after `astro build`: the site name, the one-sentence definition and the list of
// pages with their URLs, honoring the base path. Everything is read from the built pages, so the file
// matches what is deployed: the definition comes from the DefinedTerm JSON-LD on the definition page,
// and each page's title and description come from its own tags.
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { site, base, siteName } from '../site.config.mjs';

const dist = join(resolve(dirname(fileURLToPath(import.meta.url)), '..'), 'dist');
const prefix = base === '/' ? '' : base.replace(/\/+$/, '');
const origin = `${site}${prefix}`;
// Locale folders are lowercase: de, fr, ja, es, pt-br, zh-cn.
const localeCode = /^[a-z]{2}(-[a-z]{2})?$/;

const unescape = (s) =>
  s.replace(/&quot;/g, '"').replace(/&#39;|&#x27;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
const oneLine = (s) => unescape(s).replace(/\s+/g, ' ').trim();

/** Every built page as { rel, html }, where rel is the route without base, for example "docs/setup". */
function pages() {
  const out = [];
  const walk = (dir) => {
    for (const name of readdirSync(dir).sort()) {
      const p = join(dir, name);
      if (statSync(p).isDirectory()) walk(p);
      else if (name === 'index.html') out.push({ rel: relative(dist, dirname(p)).split('\\').join('/'), html: readFileSync(p, 'utf8') });
    }
  };
  walk(dist);
  return out;
}

const titleOf = (html) => oneLine(html.match(/<title>([\s\S]*?)<\/title>/)?.[1] ?? '');
const descriptionOf = (html) => oneLine(html.match(/<meta name="description" content="([^"]*)"/)?.[1] ?? '');
const jsonLd = (html) => {
  const m = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/);
  try {
    return m ? JSON.parse(m[1]) : null;
  } catch {
    return null;
  }
};
const url = (rel) => `${origin}/${rel}${rel ? '/' : ''}`;
const entry = (p) => `- [${titleOf(p.html)}](${url(p.rel)})${descriptionOf(p.html) ? `: ${descriptionOf(p.html)}` : ''}`;

if (!existsSync(dist)) throw new Error('dist/ is missing. Run `astro build` first.');
const all = pages();
const english = all.filter((p) => !localeCode.test(p.rel.split('/')[0]));
const home = english.find((p) => p.rel === '');
const definitionPage = english.find((p) => p.rel === 'definition');
const term = jsonLd(definitionPage?.html ?? '')?.['@graph']?.find((n) => n['@type'] === 'DefinedTerm');
const definition = term?.description ?? descriptionOf(home?.html ?? '');

const site_pages = english.filter((p) => p.rel === '' || !p.rel.startsWith('docs')).sort((a, b) => a.rel.localeCompare(b.rel));
const docs = english.filter((p) => p.rel.startsWith('docs'));
const languages = [...new Set(all.map((p) => p.rel.split('/')[0]).filter((s) => localeCode.test(s)))].sort();

const lines = [
  `# ${siteName}`,
  '',
  `> ${definition}`,
  '',
  `${siteName} is the website for carried-context development, a method, and carrydown, its open reference implementation. carrydown is open source under Apache 2.0.`,
  '',
  '## Pages',
  '',
  ...site_pages.map(entry),
  '',
];
if (docs.length) lines.push('## Documentation', '', ...docs.map(entry), '');
lines.push('## Source', '', '- [carrydown on GitHub](https://github.com/sct-will/carrydown): the repository, the skills and the sample project.', '');
if (languages.length) {
  lines.push('## Languages', '', ...languages.map((l) => `- [${l}](${origin}/${l}/)`), '');
}

writeFileSync(join(dist, 'llms.txt'), lines.join('\n'));
console.log(`build-llms: wrote dist/llms.txt with ${site_pages.length + docs.length} pages`);
