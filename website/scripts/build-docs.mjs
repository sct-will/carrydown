#!/usr/bin/env node
// Builds the docs section of the site from the repository's Markdown. It runs before `astro build`.
//
// Reads README.md, every docs/*.md and sample/expense-approvals/README.md from the repository root and
// writes them into Starlight's content collection with front matter (title from the first heading, or
// the title the page list below names; description from the first paragraph). Relative links between
// those files become links between site routes. A link to any other repository file becomes its GitHub
// URL. Referenced images are copied into the site. A line at the top of each page says where it came
// from.
//
// Locales: a file at docs/i18n/<locale>/<name>.md is served at /<locale>/docs/<name>/. When a locale has
// no translation of a page, the English page is served there with a note in that locale.
//
// The output is deterministic: the same input gives byte-identical output, so check-docs-sync.mjs can
// compare it with the files on disk.
//
//   node scripts/build-docs.mjs                 write into the website folder
//   node scripts/build-docs.mjs --out DIR       write into another folder (used by the sync check)
//   node scripts/build-docs.mjs --repo DIR      read another repository root
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync, copyFileSync } from 'node:fs';
import { posix } from 'node:path';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const websiteDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const repoRootDefault = resolve(websiteDir, '..');

export const GITHUB = 'https://github.com/sct-will/carrydown';
export const LOCALES = ['de', 'fr', 'ja', 'es', 'pt-BR', 'zh-CN'];

// The note a locale sees on a page that has no translation yet. The English page follows the note.
export const FALLBACK_NOTES = {
  de: 'Diese Seite ist noch nicht übersetzt. Sie sehen die englische Seite.',
  fr: 'Cette page n’est pas encore traduite. Vous voyez la page en anglais.',
  ja: 'このページはまだ翻訳されていません。英語のページを表示しています。',
  es: 'Esta página aún no está traducida. Se muestra la página en inglés.',
  'pt-BR': 'Esta página ainda não foi traduzida. Você está vendo a página em inglês.',
  'zh-CN': '此页面尚未翻译。当前显示英文页面。',
};

// Starlight lowercases the ids of its content, so the generated folders and the docs routes are lowercase:
// pt-BR is served at /pt-br/docs/ and zh-CN at /zh-cn/docs/. The folders under docs/i18n/ keep the tag as
// written.
export const localeDir = (locale) => locale.toLowerCase();

// Where the generated files live inside the website folder. The sync check compares exactly these.
export const MANAGED = [
  'src/content/docs/docs',
  ...LOCALES.map((l) => `src/content/docs/${localeDir(l)}/docs`),
  'src/assets/docs',
  'src/generated/docs-manifest.json',
];

const IMAGE_EXT = /\.(png|jpe?g|gif|svg|webp|avif)$/i;
const SAMPLE_README = 'sample/expense-approvals/README.md';

/**
 * The English pages: repository path, slug, group. The order here is the Start here order. A page with a
 * title here is titled so on the site instead of by its first heading: the README's heading is the
 * product name, right on GitHub, while on the site the page is what the Docs link promises.
 */
function listEnglishPages(repo) {
  const pages = [
    { source: 'README.md', slug: 'docs', group: 'start', title: 'Documentation' },
    { source: 'docs/setup.md', slug: 'docs/setup', group: 'start' },
    { source: 'docs/plan-owner-guide.md', slug: 'docs/plan-owner-guide', group: 'start' },
  ];
  const startSources = new Set(pages.map((p) => p.source));
  const names = readdirSync(join(repo, 'docs'))
    .filter((n) => n.endsWith('.md'))
    .sort();
  for (const n of names) {
    const source = `docs/${n}`;
    if (startSources.has(source)) continue;
    pages.push({ source, slug: `docs/${n.slice(0, -3)}`, group: 'reference' });
  }
  if (existsSync(join(repo, SAMPLE_README))) pages.push({ source: SAMPLE_README, slug: 'docs/sample', group: 'sample' });
  return pages;
}

const read = (p) => readFileSync(p, 'utf8').replace(/\r\n?/g, '\n');

/** Strips inline Markdown to plain text. */
function plain(text) {
  return text
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/<[^>]+>/g, '')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/(\*\*|__)(.+?)\1/g, '$2')
    .replace(/(^|[\s(])[*_]([^*_]+)[*_](?=[\s).,;:!?]|$)/g, '$1$2')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Splits a document into its first heading, the first paragraph and the body without that heading. */
function readDocument(text) {
  const lines = text.split('\n');
  let fence = null;
  let h1 = -1;
  for (let i = 0; i < lines.length; i++) {
    const f = lines[i].match(/^\s*(```+|~~~+)/);
    if (f) {
      if (!fence) fence = f[1][0];
      else if (f[1][0] === fence) fence = null;
      continue;
    }
    if (!fence && /^#\s+\S/.test(lines[i])) {
      h1 = i;
      break;
    }
  }
  const title = h1 >= 0 ? plain(lines[h1].replace(/^#\s+/, '').replace(/\s+#+\s*$/, '')) : '';
  const rest = lines.slice(h1 + 1);
  while (rest.length && rest[0].trim() === '') rest.shift();
  const body = (h1 >= 0 ? rest : lines).join('\n');

  // First paragraph: the first run of plain text lines after the heading. A page that opens with a list
  // before any paragraph uses the text of its first list item.
  let paragraph = '';
  let block = [];
  const flush = () => {
    if (!block.length) return false;
    const first = block[0].trim();
    const listItem = /^([-*+]|\d+[.)])\s+/;
    let lines = block;
    let ok = !/^(#|>|<|!|\[!|\||```|~~~|:::)/.test(first);
    if (ok && listItem.test(first)) {
      const next = block.findIndex((l, i) => i > 0 && listItem.test(l.trim()));
      lines = block.slice(0, next === -1 ? block.length : next).map((l, i) => (i === 0 ? l.trim().replace(listItem, '') : l));
    }
    if (ok) paragraph = plain(lines.join(' '));
    block = [];
    return ok && paragraph !== '';
  };
  for (const line of rest) {
    if (line.trim() === '' || /^#{1,6}\s/.test(line)) {
      if (flush()) break;
    } else block.push(line);
  }
  if (!paragraph) flush();
  return { title, paragraph, body };
}

/** One to a few sentences, at most 300 characters, cut at a word boundary. */
function describe(paragraph) {
  const limit = 300;
  if (paragraph.length <= limit) return paragraph;
  const sentences = (paragraph.match(/\S.*?[.!?](?=\s|$)/gs) || []).map((x) => `${x} `);
  let out = '';
  for (const s of sentences) {
    if ((out + s).trim().length > 220 && out) break;
    out += s;
  }
  out = out.trim();
  if (out && out.length <= limit) return out;
  const cut = paragraph.slice(0, limit - 3);
  return `${cut.slice(0, cut.lastIndexOf(' '))}...`;
}

const routeFor = (slug, locale) => `/${locale === 'en' ? '' : `${localeDir(locale)}/`}${slug}/`;

/** The relative URL from one route to another, so links hold under any base path. */
function relativeRoute(from, to, hash) {
  const f = from.replace(/\/$/, '');
  const t = to.replace(/\/$/, '');
  let rel = posix.relative(f, t);
  rel = rel === '' ? './' : `${rel}/`;
  return rel + (hash || '');
}

function maskCode(line) {
  return line.replace(/`[^`\n]*`/g, (m) => 'x'.repeat(m.length));
}

/** Link rewriting for one document. `ctx` carries the source path, the locale and the site-side paths. */
function makeRewriter(repo, pagesByPath, translations, imagesOut, ctx) {
  const pageDirs = new Map([['', 'README.md'], ['.', 'README.md'], ['sample/expense-approvals', SAMPLE_README]]);

  const pageFor = (repoPath) => {
    if (pagesByPath.has(repoPath)) return { slug: pagesByPath.get(repoPath).slug, locale: ctx.locale };
    const t = repoPath.match(/^docs\/i18n\/([^/]+)\/([^/]+)\.md$/);
    if (t && LOCALES.includes(t[1]) && pagesByPath.has(`docs/${t[2]}.md`)) {
      return { slug: pagesByPath.get(`docs/${t[2]}.md`).slug, locale: t[1] };
    }
    return null;
  };

  function rewrite(raw, isImage) {
    if (/^[a-z][a-z0-9+.-]*:/i.test(raw) || raw.startsWith('//') || raw.startsWith('#') || raw === '') return raw;
    const m = raw.match(/^([^#?]*)([?#].*)?$/);
    let path = m[1];
    const suffix = m[2] || '';
    try {
      path = decodeURIComponent(path);
    } catch {
      /* keep as written */
    }
    if (path === '') return raw;
    const dir = posix.dirname(ctx.source);
    const candidates = [path.startsWith('/') ? posix.normalize(path.slice(1)) : posix.normalize(posix.join(dir, path))];
    // A translated copy often keeps the links of the English file it was copied from.
    if (ctx.translated && !path.startsWith('/')) candidates.push(posix.normalize(posix.join('docs', path)));
    let chosen = null;
    for (const c of candidates) {
      if (c.startsWith('..')) continue;
      const bare = c.replace(/\/+$/, '');
      if (pageFor(c) || pageDirs.has(bare) || existsSync(join(repo, c))) {
        chosen = c;
        break;
      }
    }
    if (chosen === null) chosen = candidates.find((c) => !c.startsWith('..'));
    if (chosen === undefined) return raw;
    const bare = chosen.replace(/\/+$/, '');

    if (!isImage) {
      const page = pageFor(chosen) || (pageDirs.has(bare) ? pageFor(pageDirs.get(bare)) : null);
      if (page) return relativeRoute(ctx.route, routeFor(page.slug, page.locale), suffix.startsWith('#') ? suffix : '');
    }
    const abs = join(repo, chosen);
    if (isImage && IMAGE_EXT.test(chosen) && existsSync(abs) && statSync(abs).isFile()) {
      imagesOut.add(chosen);
      return posix.relative(posix.dirname(ctx.mdPath), `src/assets/docs/${chosen}`);
    }
    const kind = existsSync(abs) && statSync(abs).isDirectory() ? 'tree' : 'blob';
    return `${GITHUB}/${kind}/main/${bare}${suffix}`;
  }

  /** Rewrites every link and image target in the document body, outside fenced code and code spans. */
  return (body) => {
    let fence = null;
    return body
      .split('\n')
      .map((line) => {
        const f = line.match(/^\s*(```+|~~~+)/);
        if (f) {
          if (!fence) fence = f[1][0];
          else if (f[1][0] === fence) fence = null;
          return line;
        }
        if (fence) return line;
        const masked = maskCode(line);
        const edits = [];
        for (const m of masked.matchAll(/\]\(\s*(<[^>\n]*>|[^)\s]*)[^)]*\)/dg)) {
          let [s, e] = m.indices[1];
          const wrapped = masked[s] === '<';
          if (wrapped) {
            s += 1;
            e -= 1;
          }
          // Walk back to the matching "[" to see whether this is an image.
          let depth = 0;
          let open = -1;
          for (let i = m.index - 1; i >= 0; i--) {
            if (masked[i] === ']') depth++;
            else if (masked[i] === '[') {
              if (depth === 0) {
                open = i;
                break;
              }
              depth--;
            }
          }
          const isImage = open > 0 && masked[open - 1] === '!';
          edits.push([s, e, rewrite(line.slice(s, e), isImage)]);
        }
        for (const m of masked.matchAll(/<a\s[^>]*?\bhref="([^"]*)"/dg)) {
          const [s, e] = m.indices[1];
          edits.push([s, e, rewrite(line.slice(s, e), false)]);
        }
        const def = masked.match(/^(\s{0,3}\[[^\]]+\]:\s*)(\S+)/d);
        if (def) {
          const [s, e] = def.indices[2];
          edits.push([s, e, rewrite(line.slice(s, e), false)]);
        }
        edits.sort((a, b) => b[0] - a[0]);
        let out = line;
        for (const [s, e, v] of edits) out = out.slice(0, s) + v + out.slice(e);
        return out;
      })
      .join('\n');
  };
}

const yaml = (s) => JSON.stringify(s);

// Styles for the generated pages only, added to each page's head through its front matter. The note line,
// image links such as the README badges (a 24 px target), and tables that wrap instead of scrolling, so no
// table needs a keyboard stop to be reachable.
const PAGE_CSS = [
  '.sl-markdown-content .synced{font-size:0.85rem;color:var(--sl-color-gray-3);margin:0 0 1.5rem}',
  '.sl-markdown-content .synced-locale{font-size:0.95rem;margin:0 0 0.5rem}',
  '.sl-markdown-content a:has(>img){display:inline-block;padding:2px 0;margin-right:6px}',
  '.sl-markdown-content table{display:table;width:100%;overflow-wrap:anywhere}',
].join('');

/** Removes what an earlier run wrote. */
function clean(out) {
  for (const rel of MANAGED) rmSync(join(out, rel), { recursive: true, force: true });
}

function write(out, rel, data) {
  const p = join(out, rel);
  mkdirSync(dirname(p), { recursive: true });
  writeFileSync(p, data);
}

/** Generates the docs into `out` (a website folder). Returns the manifest. */
export function generate({ repo = repoRootDefault, out = websiteDir } = {}) {
  const pages = listEnglishPages(repo);
  const pagesByPath = new Map(pages.map((p) => [p.source, p]));
  clean(out);

  // Translations: docs/i18n/<locale>/<name>.md for any docs/<name>.md page. README.md is the folder note.
  const translations = new Map();
  for (const locale of LOCALES) {
    const folder = join(repo, 'docs', 'i18n', locale);
    if (!existsSync(folder)) continue;
    for (const n of readdirSync(folder).filter((x) => x.endsWith('.md') && x !== 'README.md').sort()) {
      const english = pagesByPath.get(`docs/${n}`);
      if (!english) {
        console.warn(`build-docs: docs/i18n/${locale}/${n} has no English page docs/${n}. Skipped.`);
        continue;
      }
      translations.set(`${locale}/${english.slug}`, `docs/i18n/${locale}/${n}`);
    }
  }

  const images = new Set();
  const manifestPages = [];
  const manifestLocalized = [];

  const contentPath = (slug, locale) =>
    `src/content/docs/${locale === 'en' ? '' : `${localeDir(locale)}/`}${slug === 'docs' ? 'docs/index' : slug}.md`;

  function emit({ page, locale, source, fallbackOf }) {
    const text = read(join(repo, source));
    const doc = readDocument(text);
    // The page list's title applies to the English file wherever it is served; a translation keeps its own heading.
    const title = page.title && source === page.source ? page.title : doc.title;
    const route = routeFor(page.slug, locale);
    const mdPath = contentPath(page.slug, locale);
    const rewriter = makeRewriter(repo, pagesByPath, translations, images, {
      source,
      locale,
      route,
      mdPath,
      translated: source.startsWith('docs/i18n/'),
    });
    let body = rewriter(doc.body).replace(/\s+$/, '');
    const note = `<p class="synced">From the repository, ${source}. Generated at build time and checked against the source.</p>`;
    let top = note;
    if (fallbackOf) {
      top = `<p class="synced-locale" lang="${locale}">${FALLBACK_NOTES[locale]}</p>\n\n${note}`;
      body = `<div lang="en">\n\n${body}\n\n</div>`;
    }
    const description = describe(doc.paragraph);
    const front = `---\ntitle: ${yaml(title)}\n${description ? `description: ${yaml(description)}\n` : ''}head:\n  - tag: style\n    content: ${yaml(PAGE_CSS)}\n---\n`;
    write(out, mdPath, `${front}\n${top}\n\n${body}\n`);
    return { slug: page.slug, locale, title, description, source, fallback: Boolean(fallbackOf) };
  }

  for (const page of pages) {
    const r = emit({ page, locale: 'en', source: page.source });
    manifestPages.push({ slug: page.slug, group: page.group, title: r.title, description: r.description, source: page.source });
  }
  for (const locale of LOCALES) {
    for (const page of pages) {
      const translated = translations.get(`${locale}/${page.slug}`);
      const r = translated
        ? emit({ page, locale, source: translated })
        : emit({ page, locale, source: page.source, fallbackOf: true });
      manifestLocalized.push({ locale, slug: page.slug, title: r.title, source: r.source, fallback: r.fallback });
    }
  }

  for (const rel of [...images].sort()) {
    const dest = join(out, 'src/assets/docs', rel);
    mkdirSync(dirname(dest), { recursive: true });
    copyFileSync(join(repo, rel), dest);
  }

  // Sidebar order: Start here keeps its listed order, Reference is alphabetical by title, Sample is one page.
  const byTitle = (a, b) => (a.title.toLowerCase() < b.title.toLowerCase() ? -1 : a.title.toLowerCase() > b.title.toLowerCase() ? 1 : 0);
  const group = (id, label) => ({
    id,
    label,
    slugs: (id === 'reference' ? manifestPages.filter((p) => p.group === id).sort(byTitle) : manifestPages.filter((p) => p.group === id)).map((p) => p.slug),
  });
  const manifest = {
    groups: [group('start', 'Start here'), group('reference', 'Reference'), group('sample', 'Sample')],
    pages: manifestPages,
    localized: manifestLocalized,
    images: [...images].sort(),
  };
  write(out, 'src/generated/docs-manifest.json', `${JSON.stringify(manifest, null, 2)}\n`);
  return manifest;
}

// Run from the command line.
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const arg = (name) => {
    const i = process.argv.indexOf(name);
    return i > 0 ? resolve(process.argv[i + 1]) : undefined;
  };
  const m = generate({ repo: arg('--repo') || repoRootDefault, out: arg('--out') || websiteDir });
  const fb = m.localized.filter((l) => l.fallback).length;
  console.log(`build-docs: ${m.pages.length} pages, ${m.localized.length - fb} translated and ${fb} fallback locale pages, ${m.images.length} image(s).`);
}
