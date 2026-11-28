// Every excerpt on the sample page is verbatim. For each fragment that src/lib/sample-excerpts.mjs
// exports, this test finds it in the repository file it names and fails on any that is not there. A
// fragment abridged with "…" is checked piece by piece. The issue excerpt is checked against the copy
// of the issue body in tests/fixtures/issue-9.md, and the board image against docs/images/board.png.
// It reads only repository files, so it needs no built site and no network.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { websiteDir } from './lib.mjs';
import { tiles, change, trial, boardImage } from '../src/lib/sample-excerpts.mjs';

const repo = join(websiteDir, '..');
const cache = new Map();
const read = (rel) => {
  if (!cache.has(rel)) cache.set(rel, readFileSync(join(repo, rel), 'utf8'));
  return cache.get(rel);
};

let checked = 0;
const failures = [];
/** Fails unless `needle` is in the file. Empty pieces and lone punctuation left by a split are skipped. */
const expect = (rel, needle, where) => {
  const s = needle.trim();
  if (!s || /^[\s"“”.,;:]+$/.test(s)) return;
  checked += 1;
  if (!read(rel).includes(s)) failures.push(`${where}: not verbatim in ${rel}:\n    ${s}`);
};
/** The pieces of a shown text: its own text split on the abridgment mark, or its `verify` strings. */
const pieces = (text, verify) => verify ?? text.split('…');
/** Fails unless `needle` ends where a line of the file ends: a shown line without "…" is not cut short. */
const expectLineEnd = (rel, needle, where) => {
  const s = needle.trim();
  if (!s) return;
  checked += 1;
  const file = read(rel).replace(/\r\n/g, '\n');
  if (!file.includes(`${s}\n`) && !file.trimEnd().endsWith(s)) failures.push(`${where}: shown without "…" but its line in ${rel} goes on after:\n    ${s}`);
};
const unabridgedEnd = (text) => !text.replace(/[“”"]/g, '').trimEnd().endsWith('…');
const abridgedLabels = new Set(['abridged', 'milestones']);

for (const tile of tiles) {
  // A path heading names the source file itself. The issue's heading is checked with its fixture below.
  if (tile.heading && !tile.heading.includes('#')) {
    checked += 1;
    if (!tile.source.endsWith(tile.heading)) failures.push(`${tile.key} heading: ${tile.heading} is not the source ${tile.source}`);
  }
  // The label says "abridged" exactly when the preview marks an abridgment.
  const marked = tile.blocks.some((b) => (b.lines ?? [b.text]).some((x) => x.includes('…')));
  checked += 1;
  if (marked !== abridgedLabels.has(tile.label)) failures.push(`${tile.key}: label '${tile.label}' ${marked ? 'does not say abridged, but the preview is abridged' : 'says abridged, but nothing is abridged'}`);
  tile.blocks.forEach((b, i) => {
    const rel = b.from ?? tile.source;
    const where = `${tile.key} block ${i + 1}`;
    if (b.t === 'code') {
      b.lines.forEach((line, j) => {
        pieces(line).forEach((p) => expect(rel, p, `${where} line ${j + 1}`));
        if (unabridgedEnd(line)) expectLineEnd(rel, line.split('…').pop(), `${where} line ${j + 1}`);
      });
    } else {
      pieces(b.text, b.verify).forEach((p) => expect(rel, p, where));
      // A heading is a name, not a sentence: the issue's title comes from the fixture's source note.
      if (b.t !== 'h' && unabridgedEnd(b.text)) (b.verify ?? [b.text.split('…').pop()]).forEach((p) => expectLineEnd(rel, p, where));
      // A line shown in another shape than the file's still says only what its verify strings say:
      // without the table pipes, heading marks, list markers and quotes, each shown piece is in them.
      if (b.verify) {
        const plain = b.verify.map((v) => v.replace(/^(#+|- \[ \]|-|\d+\.|description:)\s*/, '').replace(/\|/g, ' ').replace(/"/g, '')).join(' ').replace(/\s+/g, ' ');
        for (const piece of b.text.split(/…| · /)) {
          const shown = piece.replace(/[“”]/g, '').trim();
          checked += 1;
          if (shown && !plain.includes(shown)) failures.push(`${where}: the shown text is not in its verify strings:\n    ${shown}`);
        }
      }
    }
  });
}

const spec = tiles.find((t) => t.key === 'specification');

// The issue fixture records the title the preview shows.
const issue = tiles.find((t) => t.key === 'issues');
if (!read(issue.source).startsWith('<!--') || !read(issue.source).includes('sct-will/carrydown-sample, title "WI-03 Approval routing engine"') || !read(issue.source).includes(`issue ${issue.heading.split('#')[1]} of`)) failures.push('tests/fixtures/issue-9.md does not start with its source note and the issue title');
checked += 1;

// The board image is a byte-for-byte copy of the published one.
const board = tiles.find((t) => t.key === 'project');
if (!readFileSync(join(repo, boardImage)).equals(readFileSync(join(repo, board.source)))) failures.push(`${boardImage} differs from ${board.source}`);
checked += 1;

// The change: the section, the added rule and the two work items' names.
expect(change.source, change.section, 'change section');
expect(change.source, `+5. ${change.rule}`, 'change rule');
expectLineEnd(change.source, `+5. ${change.rule}`, 'change rule');
for (const item of change.items) expect(change.source, item.name, `change ${item.id}`);
expect(spec.source, `# ${change.items[0].id} ${change.items[0].name}`, 'change WI-03 title');
expect('sample/expense-approvals/docs/spec/m2-route-to-approvers/wi-04-approver-inbox.md', `# ${change.items[1].id} ${change.items[1].name}`, 'change WI-04 title');
if (!change.href.endsWith('#10-an-update-after-planning')) failures.push(`change link ${change.href} does not name the section's anchor`);

// The expected output is what the check prints for WI-03 when it passes.
trial.expectedTemplate.forEach((line) => expect(trial.expectedSource, line, 'expected output template'));
const filled = trial.expectedTemplate.map((line) => line.slice(2, -1).replace('{tag}', 'WI-03').replace('{md_rel}', 'docs/context/wi-03.md'));
if (JSON.stringify(filled) !== JSON.stringify(trial.expected)) failures.push(`the expected output differs from the check's success lines:\n    ${filled.join('\n    ')}`);
checked += 1;
// The installer line and the skill file are the sample skill's own.
expect('sample/expense-approvals/docs/dev/skills/expense-approvals-dev/README.md', trial.commands[2].replace(' -a <your agent>', ' -a '), 'installer command');
expect('sample/expense-approvals/docs/dev/skills/expense-approvals-dev/SKILL.md', 'name: expense-approvals-dev', 'skill file');

if (failures.length) {
  for (const f of failures) console.error(`FAIL ${f}`);
  console.error(`sample-excerpts: ${failures.length} of ${checked} check(s) failed`);
  process.exit(1);
}
console.log(`sample-excerpts: ${checked} fragment(s) verbatim in their files`);
