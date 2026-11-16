#!/usr/bin/env node
// Fails when the generated docs in the website differ from what the repository's Markdown would produce.
// It regenerates into a temporary folder and compares that with the files on disk. Exit code 1 with a
// diff when they differ. Run it after `node scripts/build-docs.mjs`, and in CI.
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, relative } from 'node:path';
import { MANAGED, generate, websiteDir } from './build-docs.mjs';

function listFiles(root, rel) {
  const p = join(root, rel);
  if (!existsSync(p)) return [];
  if (statSync(p).isFile()) return [rel];
  const out = [];
  const walk = (d) => {
    for (const n of readdirSync(d).sort()) {
      const f = join(d, n);
      if (statSync(f).isDirectory()) walk(f);
      else out.push(relative(root, f).split('\\').join('/'));
    }
  };
  walk(p);
  return out;
}

const tmp = mkdtempSync(join(tmpdir(), 'docs-sync-'));
let failures = 0;
try {
  generate({ out: tmp });
  const expected = new Set(MANAGED.flatMap((m) => listFiles(tmp, m)));
  const actual = new Set(MANAGED.flatMap((m) => listFiles(websiteDir, m)));
  for (const f of [...new Set([...expected, ...actual])].sort()) {
    if (!actual.has(f)) {
      failures++;
      console.error(`MISSING  ${f} (the sources produce it, the site does not have it)`);
    } else if (!expected.has(f)) {
      failures++;
      console.error(`STALE    ${f} (the site has it, the sources no longer produce it)`);
    } else {
      const a = readFileSync(join(tmp, f));
      const b = readFileSync(join(websiteDir, f));
      if (!a.equals(b)) {
        failures++;
        console.error(`DIFFERS  ${f}`);
        if (/\.(md|json)$/.test(f)) {
          const d = spawnSync('diff', ['-u', '--label', `sources:${f}`, '--label', `site:${f}`, join(tmp, f), join(websiteDir, f)], { encoding: 'utf8' });
          if (d.stdout) console.error(d.stdout.split('\n').slice(0, 40).join('\n'));
        } else console.error('  (binary files differ)');
      }
    }
  }
  console.log(failures ? `docs-sync: ${failures} difference(s). Run: node scripts/build-docs.mjs` : `docs-sync: ok, ${expected.size} generated files match the sources.`);
} finally {
  rmSync(tmp, { recursive: true, force: true });
}
process.exit(failures ? 1 : 0);
