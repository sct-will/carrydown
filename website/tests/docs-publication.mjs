// Checks that the docs generator publishes only the approved pages. It builds a small repository in a
// temporary folder with every listed page and one unlisted maintainer note, runs the generator into
// another temporary folder and expects: the listed pages in the manifest and the content, no trace of
// the note in any generated file or locale, and a build that stops when a listed page is missing. It
// needs no built dist/.
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, relative } from 'node:path';
import { LOCALES, PUBLIC_PAGES, generate } from '../scripts/build-docs.mjs';

let failures = 0;
const fail = (msg) => {
  failures++;
  console.error(`FAIL ${msg}`);
};

const tmp = mkdtempSync(join(tmpdir(), 'docs-publication-'));
const repo = join(tmp, 'repo');
const out = join(tmp, 'out');
const put = (rel, text) => {
  mkdirSync(dirname(join(repo, rel)), { recursive: true });
  writeFileSync(join(repo, rel), text);
};

let files = [];
try {
  // Every listed page, so the build can succeed: README.md, docs/setup.md, docs/plan-owner-guide.md, the
  // Reference pages and the sample README.
  for (const p of PUBLIC_PAGES) put(p.source, `# Page ${p.slug}\n\nThe ${p.slug} page.\n`);
  // A maintainer note that is not listed, and a translation of it.
  put('docs/maintainer-notes.md', '# Maintainer notes\n\nNot for the public site.\n');
  put('docs/i18n/de/maintainer-notes.md', '# Notizen\n\nNicht öffentlich.\n');

  const manifest = generate({ repo, out });
  const walk = (d) => {
    for (const n of readdirSync(d).sort()) {
      const f = join(d, n);
      if (statSync(f).isDirectory()) walk(f);
      else files.push(relative(out, f).split('\\').join('/'));
    }
  };
  walk(out);

  // The listed pages are published.
  const slugs = manifest.pages.map((p) => p.slug);
  for (const slug of ['docs/setup', 'docs/method', 'docs/sample']) {
    if (!slugs.includes(slug)) fail(`the manifest has no page ${slug}`);
    if (!files.includes(`src/content/docs/${slug}.md`)) fail(`no generated content for ${slug}`);
  }
  if (!manifest.groups.find((g) => g.id === 'reference')?.slugs.includes('docs/method')) fail('docs/method is not in the Reference group');

  // The unlisted note is nowhere: not in a file name, not in a file, in English or any locale.
  if (!LOCALES.every((l) => files.some((f) => f.startsWith(`src/content/docs/${l.toLowerCase()}/docs/`)))) fail('a locale has no generated pages');
  for (const f of files) {
    if (/maintainer-notes/i.test(f)) fail(`a generated file is named for the unlisted page: ${f}`);
    else if (/maintainer-notes/i.test(readFileSync(join(out, f), 'utf8'))) fail(`a generated file names the unlisted page: ${f}`);
  }

  // A listed page that is missing stops the build.
  rmSync(join(repo, 'docs/setup.md'));
  let threw = null;
  try {
    generate({ repo, out: join(tmp, 'out-missing') });
  } catch (e) {
    threw = e;
  }
  if (!threw) fail('the generator did not stop when docs/setup.md, a listed page, was missing');
  else if (!/docs\/setup\.md/.test(threw.message)) fail(`the error does not name the missing page: ${threw.message}`);
} finally {
  rmSync(tmp, { recursive: true, force: true });
}

console.log(`docs-publication: ${files.length} generated files checked, ${failures} failure(s)`);
if (failures) process.exit(1);
