// Writes dist/llms.txt and dist/llms-full.txt after `astro build`. Both follow the llms.txt format
// (https://llmstxt.org/) and honor the base path. Everything is read from the built site, so the files
// match what is deployed:
//
// - The definition comes from the DefinedTerm JSON-LD on the definition page.
// - Each page's title, description and canonical address come from its own tags.
// - A docs page links to its Markdown form, the file `src/pages/[...path].md.ts` writes next to it.
//   A page with no Markdown form links to its HTML page.
// - The "What to tell your agent, and when" phrases come from the Markdown form of the docs home page, which is the README.
// - llms-full.txt holds the Markdown forms of the pages in the same reading order. A site page has no
//   Markdown form, so its main content is converted from the built HTML.
//
// Redirect pages are skipped. The output depends only on the built site, so the same build gives
// byte-identical files.
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { site, base } from '../site.config.mjs';

const dist = join(resolve(dirname(fileURLToPath(import.meta.url)), '..'), 'dist');
const prefix = base === '/' ? '' : base.replace(/\/+$/, '');
const origin = `${site}${prefix}`;
// Locale folders are lowercase: de, fr, ja, es, pt-br, zh-cn.
const localeCode = /^[a-z]{2}(-[a-z]{2})?$/;

// The reading order. A page listed here comes in this order. A docs page not listed in either list is
// added at the end of the Documentation section, so a new docs page appears without an edit here; a new
// site page is added at the end of the Pages section.
const DOCS_ORDER = [
  'docs',
  'docs/setup',
  'docs/plan-owner-guide',
  'docs/method',
  'docs/sample',
  'docs/troubleshooting',
  'docs/inputs',
  'docs/install-options',
  'docs/security',
  'docs/enterprise-security',
  'docs/recovery',
  'docs/organization-setup',
  'docs/delivery-modes',
];
const PAGES_ORDER = ['', 'definition', 'sample', 'faq'];
// Pages a reader may skip: a worked example and the site's accessibility statement. They are listed in
// llms.txt under Optional and left out of llms-full.txt.
const OPTIONAL_ORDER = ['docs/derive-the-date', 'accessibility'];

const unescape = (s) =>
  s
    .replace(/&#x([0-9a-f]+);/gi, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_m, d) => String.fromCodePoint(Number(d)))
    .replace(/&nbsp;/g, ' ')
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&');
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

// Starlight titles the docs pages "<page> | <site name>". The list names the page alone.
const titleOf = (html) => oneLine(html.match(/<title>([\s\S]*?)<\/title>/)?.[1] ?? '').replace(/ \| [^|]+$/, '');
const descriptionOf = (html) => oneLine(html.match(/<meta name="description" content="([^"]*)"/)?.[1] ?? '');
const isRedirect = (html) => /<meta http-equiv="refresh"/i.test(html);
const jsonLd = (html) => {
  const m = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/);
  try {
    return m ? JSON.parse(m[1]) : null;
  } catch {
    return null;
  }
};
const htmlUrl = (rel) => `${origin}/${rel}${rel ? '/' : ''}`;
const canonicalOf = (p) => p.html.match(/<link rel="canonical" href="([^"]+)"/)?.[1] ?? htmlUrl(p.rel);
// The Markdown form of a page, as the .md route builds it: /docs/setup/ has /docs/setup.md.
const markdownFile = (rel) => (rel ? join(dist, `${rel}.md`) : null);
const markdownUrl = (rel) => `${origin}/${rel}.md`;
const hasMarkdown = (p) => Boolean(markdownFile(p.rel) && existsSync(markdownFile(p.rel)));
const linkOf = (p) => (hasMarkdown(p) ? markdownUrl(p.rel) : htmlUrl(p.rel));
const entry = (p) => `- [${titleOf(p.html)}](${linkOf(p)})${descriptionOf(p.html) ? `: ${descriptionOf(p.html)}` : ''}`;

// ---------------------------------------------------------------------------------------------------
// A small HTML to Markdown converter for the main content of the site pages. It covers the elements
// those pages use: headings, paragraphs, lists, tables, links, emphasis and code. Anything hidden from
// assistive technology is left out, and an element with role="img" becomes its text alternative.

const VOID = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr']);
const SKIP = new Set(['script', 'style', 'template', 'nav', 'caption', 'svg', 'noscript']);
const BLOCK = new Set(['address', 'article', 'aside', 'blockquote', 'details', 'div', 'dl', 'dd', 'dt', 'figcaption', 'figure', 'footer', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'hr', 'li', 'main', 'ol', 'p', 'pre', 'section', 'summary', 'table', 'ul']);

/** Parses HTML into a tree of { tag, attrs, children } and strings. Tolerant of what Astro writes. */
function parse(html) {
  const root = { tag: '#root', attrs: {}, children: [] };
  const stack = [root];
  const re = /<!--[\s\S]*?-->|<(\/?)([a-zA-Z][a-zA-Z0-9-]*)((?:\s+[^\s"'>/=]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'>]+))?)*)\s*(\/?)>|([^<]+)|</g;
  for (const m of html.matchAll(re)) {
    const top = stack[stack.length - 1];
    if (m[0].startsWith('<!--')) continue;
    if (m[5] !== undefined || m[0] === '<') {
      top.children.push(m[0]);
      continue;
    }
    const tag = m[2].toLowerCase();
    if (m[1]) {
      const i = stack.map((n) => n.tag).lastIndexOf(tag);
      if (i > 0) stack.length = i;
      continue;
    }
    const attrs = {};
    for (const a of m[3].matchAll(/([^\s"'>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?/g)) {
      attrs[a[1].toLowerCase()] = unescape(a[2] ?? a[3] ?? a[4] ?? '');
    }
    const node = { tag, attrs, children: [] };
    top.children.push(node);
    if (!VOID.has(tag) && !m[4]) stack.push(node);
  }
  return root;
}

const hidden = (n) => n.attrs['aria-hidden'] === 'true' || 'hidden' in n.attrs || SKIP.has(n.tag);
const isBlock = (n) => typeof n !== 'string' && (BLOCK.has(n.tag) || n.attrs.role === 'img');
const textOf = (n) => (typeof n === 'string' ? unescape(n) : n.children.map(textOf).join(''));
const endsSentence = (s) => /[.!?:;”"’)]$/.test(s.replace(/[*_`]+$/, ''));

function converter(pageUrl) {
  const abs = (href) => {
    try {
      return new URL(href, pageUrl).href;
    } catch {
      return href;
    }
  };

  /** The inline Markdown of a run of nodes. */
  function inline(nodes) {
    let out = '';
    let prevElement = false;
    for (const n of nodes) {
      if (typeof n === 'string') {
        out += unescape(n).replace(/\s+/g, ' ');
        prevElement = false;
        continue;
      }
      if (hidden(n)) continue;
      let s = '';
      if (n.attrs.role === 'img') s = n.attrs['aria-label'] ?? '';
      else if (n.tag === 'br') s = ' ';
      else if (n.tag === 'img') s = n.attrs.alt ?? '';
      else if (n.tag === 'code') s = `\`${textOf(n)}\``;
      else {
        const inner = inline(n.children).replace(/\s+/g, ' ');
        const t = inner.trim();
        if (n.tag === 'a') s = t ? `[${t}](${abs(n.attrs.href ?? '')})` : '';
        else if (n.tag === 'b' || n.tag === 'strong') s = t ? `**${t}**` : '';
        else if (n.tag === 'em' || n.tag === 'i') s = t ? `*${t}*` : '';
        else s = inner;
        // Keep the spaces at the edges of an emphasized run outside the markers.
        if (s && s !== inner) s = (inner.match(/^\s*/)[0] ? ' ' : '') + s + (inner.match(/\s*$/)[0] ? ' ' : '');
      }
      // Two elements side by side, such as the status items, are separate words on the page.
      if (s && prevElement && /\S$/.test(out) && /^\S/.test(s)) out += ' ';
      out += s;
      prevElement = s !== '';
    }
    return out;
  }

  /** The Markdown blocks of a run of nodes, as an array of strings. */
  function blocks(nodes, ctx = {}) {
    const out = [];
    let run = [];
    const flush = () => {
      const t = inline(run).trim();
      if (t) out.push(t);
      run = [];
    };
    for (const n of nodes) {
      if (!isBlock(n)) {
        run.push(n);
        continue;
      }
      flush();
      if (hidden(n)) continue;
      out.push(...block(n, ctx));
    }
    flush();
    return out;
  }

  function block(n, ctx) {
    if (n.attrs.role === 'img') return n.attrs['aria-label'] ? [`Diagram: ${n.attrs['aria-label']}`] : [];
    const h = n.tag.match(/^h([1-6])$/);
    if (h) {
      const t = inline(n.children).trim();
      if (!t) return [];
      return ctx.inItem ? [`**${t}**`] : [`${'#'.repeat(Number(h[1]))} ${t}`];
    }
    if (n.tag === 'pre') return [`\`\`\`\n${textOf(n).replace(/\n+$/, '')}\n\`\`\``];
    if (n.tag === 'ul' || n.tag === 'ol') {
      const items = n.children.filter((c) => typeof c !== 'string' && c.tag === 'li' && !hidden(c));
      // A numbered list keeps the number it starts at, as the sample page's excerpts do.
      const start = Number(n.attrs.start) || 1;
      const lines = items.map((li, i) => {
        // A block that holds only the item's number repeats the list marker, so it is dropped.
        const parts = blocks(li.children, { inItem: true }).filter((b) => !(n.tag === 'ol' && /^\d+$/.test(b)));
        const text = parts.reduce((acc, b) => (acc ? `${acc}${endsSentence(acc) ? ' ' : ': '}${b}` : b), '');
        return `${n.tag === 'ol' ? `${start + i}.` : '-'} ${text.replace(/\n/g, ' ')}`;
      });
      return lines.length ? [lines.join('\n')] : [];
    }
    if (n.tag === 'table') {
      const rows = [];
      const walk = (x) => {
        for (const c of x.children) {
          if (typeof c === 'string' || hidden(c)) continue;
          if (c.tag === 'tr') rows.push(c.children.filter((d) => typeof d !== 'string' && (d.tag === 'th' || d.tag === 'td')).map((d) => inline(d.children).trim().replace(/\|/g, '\\|')));
          else walk(c);
        }
      };
      walk(n);
      if (!rows.length) return [];
      const width = Math.max(...rows.map((r) => r.length));
      const line = (r) => `| ${Array.from({ length: width }, (_v, i) => r[i] ?? '').join(' | ')} |`;
      return [[line(rows[0]), `| ${Array(width).fill('---').join(' | ')} |`, ...rows.slice(1).map(line)].join('\n')];
    }
    if (n.tag === 'blockquote') return blocks(n.children, ctx).map((b) => b.replace(/^/gm, '> '));
    if (n.tag === 'p') {
      const t = inline(n.children).trim();
      return t ? [t] : [];
    }
    return blocks(n.children, ctx);
  }

  return (html) => {
    const out = [];
    for (const b of blocks(parse(html).children)) if (out[out.length - 1] !== b) out.push(b);
    return out;
  };
}

/** The main content of a site page as Markdown blocks, without the page's own first heading. */
function siteMarkdown(p) {
  const main = p.html.match(/<main\b[^>]*>([\s\S]*?)<\/main>/)?.[1] ?? '';
  const out = converter(canonicalOf(p))(main);
  const title = titleOf(p.html);
  const first = out.findIndex((b) => b.startsWith('# '));
  if (first >= 0) {
    const h1 = out[first].slice(2);
    // The first heading becomes the section title. One that says more than the title stays as text.
    if (title.startsWith(h1) || h1 === title) out.splice(first, 1);
    else out[first] = `**${h1}**`;
  }
  return out.join('\n\n');
}

// ---------------------------------------------------------------------------------------------------
// The "What to tell your agent, and when" section of the README, read from the Markdown form of the docs home page.

/** { intro, groups: [{ label, rows: [{ want, say }] }] }, or null when the section is missing. */
function whatToSay(markdown) {
  const section = markdown.match(/^## What to tell your agent, and when\n([\s\S]*?)(?=^## |(?![\s\S]))/m)?.[1];
  if (!section) return null;
  const lines = section.split('\n');
  const intro = lines.find((l) => l.trim() && !/^(\*\*|\||<|>)/.test(l.trim()))?.trim() ?? '';
  const groups = [];
  for (const l of lines) {
    const label = l.trim().match(/^\*\*([^*]+)\*\*$/);
    if (label) groups.push({ label: label[1], rows: [] });
    const row = l.trim().match(/^\|(.+)\|$/);
    if (row && groups.length) {
      const cells = row[1].split('|').map((c) => c.trim());
      if (cells.length < 2 || /^:?-+:?$/.test(cells[0]) || cells[0] === 'What you want to do') continue;
      groups[groups.length - 1].rows.push({ want: cells[0], say: cells[1] });
    }
  }
  return groups.some((g) => g.rows.length) ? { intro, groups: groups.filter((g) => g.rows.length) } : null;
}

// ---------------------------------------------------------------------------------------------------

if (!existsSync(dist)) throw new Error('dist/ is missing. Run `astro build` first.');
const all = pages();
const english = all.filter((p) => !localeCode.test(p.rel.split('/')[0]) && !isRedirect(p.html));
const byRel = new Map(english.map((p) => [p.rel, p]));
const home = byRel.get('');
const definitionPage = byRel.get('definition');
const term = jsonLd(definitionPage?.html ?? '')?.['@graph']?.find((n) => n['@type'] === 'DefinedTerm');
const definition = term?.description ?? descriptionOf(home?.html ?? '');
const name = term?.name ?? titleOf(home?.html ?? '');

const isDocs = (rel) => rel === 'docs' || rel.startsWith('docs/');
const ordered = (order, rest) => [...order.filter((r) => byRel.has(r)), ...rest.filter((r) => !order.includes(r)).sort()].map((r) => byRel.get(r));
const optionalSet = new Set(OPTIONAL_ORDER);
const docsPages = ordered(DOCS_ORDER, english.map((p) => p.rel).filter((r) => isDocs(r) && !optionalSet.has(r)));
const sitePages = ordered(PAGES_ORDER, english.map((p) => p.rel).filter((r) => !isDocs(r) && !optionalSet.has(r)));
const optionalPages = OPTIONAL_ORDER.filter((r) => byRel.has(r)).map((r) => byRel.get(r));
const languages = [...new Set(all.map((p) => p.rel.split('/')[0]).filter((s) => localeCode.test(s)))].sort();

const docsHome = byRel.get('docs');
const phrases = docsHome && hasMarkdown(docsHome) ? whatToSay(readFileSync(markdownFile('docs'), 'utf8')) : null;
if (!phrases) console.warn('build-llms: no "What to tell your agent, and when" section found in the docs home page. The phrases are left out.');

const lines = [
  `# ${name}`,
  '',
  `> ${definition}`,
  '',
  // The site's own words, from the home page's Try it out section.
  'This site defines carried-context development, an approach to agentic development, and documents carrydown, its reference implementation: two Agent Skills you install, a third it generates for your engineers, and the checks that validate every citation. carrydown is open source under Apache 2.0 and works with the coding agent your team already uses.',
  '',
  `The documentation links below go to the Markdown form of each page. [llms-full.txt](${origin}/llms-full.txt) holds the documentation and the site pages in one file, in the same order.`,
  '',
];
if (phrases) {
  lines.push(`${phrases.intro} These are the phrases from [What to tell your agent, and when](${htmlUrl('docs')}#what-to-tell-your-agent-and-when) in the documentation:`, '');
  for (const g of phrases.groups) {
    lines.push(`${g.label}:`, '', ...g.rows.map((r) => `- ${r.want}: ${r.say}`), '');
  }
}
if (docsPages.length) lines.push('## Documentation', '', ...docsPages.map(entry), '');
if (sitePages.length) lines.push('## Pages', '', ...sitePages.map(entry), '');
lines.push('## Source', '', '- [carrydown on GitHub](https://github.com/sct-will/carrydown): the repository, the skills and the sample project.', '');
if (languages.length) lines.push('## Languages', '', ...languages.map((l) => `- [${l}](${origin}/${l}/)`), '');
if (optionalPages.length) lines.push('## Optional', '', ...optionalPages.map(entry), '');

writeFileSync(join(dist, 'llms.txt'), lines.join('\n'));

// llms-full.txt: every page of the Documentation and Pages sections, whole, in the same order. Each
// section starts with the page title as a first-level heading and its canonical address.
const sections = [...docsPages, ...sitePages].map((p) => {
  const title = titleOf(p.html);
  const body = hasMarkdown(p)
    ? readFileSync(markdownFile(p.rel), 'utf8').replace(/^# [^\n]*\n+/, '').trim()
    : siteMarkdown(p);
  return `# ${title}\n\nURL: ${canonicalOf(p)}\n\n${body}\n`;
});
const full = [
  `# ${name}, full text`,
  '',
  `> ${definition}`,
  '',
  `This file holds the full Markdown of the pages listed in [llms.txt](${origin}/llms.txt), in reading order: the documentation first, then the site pages. Each page starts with its title and its address.`,
  '',
  ...sections,
].join('\n');
writeFileSync(join(dist, 'llms-full.txt'), full);

console.log(
  `build-llms: wrote dist/llms.txt with ${docsPages.length + sitePages.length + optionalPages.length} pages (${optionalPages.length} optional) and dist/llms-full.txt with ${sections.length} pages, ${Buffer.byteLength(full)} bytes`,
);
