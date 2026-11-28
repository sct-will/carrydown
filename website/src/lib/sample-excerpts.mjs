// The excerpts and links of the sample page, /sample/. Plain JavaScript so that the page and the test
// read the same data: src/components/pages/SamplePage.astro renders it, and tests/sample-excerpts.mjs
// checks every fragment against the repository file it quotes.
//
// Nothing here is translated. The excerpts are quoted from the sample's files, so they stay in English
// on every locale's page, marked lang="en". The words around them (titles, values, labels, notes) are
// in the locale strings, src/i18n/<locale>.ts, under `sample`.
//
// The rules for a fragment:
// - Its text is verbatim from the file named by `source` (or by the block's own `from`). Inline code is
//   written with backticks, as in the file, and the page sets it in code.
// - An abridgment is marked with "…". The test splits the text on it and checks each piece on its own.
//   A line that does not end with "…" is shown to the end of its line in the file. A tile with any "…"
//   carries an abridged label ('abridged', or 'milestones', which names the abridged rationale), and a
//   tile without one carries none.
// - Where the page shows a line in another shape than the file holds it (a row of a Markdown table, a
//   list item without its marker), `verify` lists the exact strings of the file the line comes from.

/**
 * @typedef {Object} Block
 * @property {'code' | 'h' | 'p' | 'li' | 'sub' | 'cite' | 'small'} t The kind of block: a preformatted
 *   excerpt, a heading inside the excerpt, a paragraph, a numbered item (with `n`), an item under it, a
 *   reference line, a small line.
 * @property {string} [text] The text as shown.
 * @property {string[]} [lines] For `code`: the lines as shown, indentation included.
 * @property {number} [n] For `li`: the item's number in the file.
 * @property {string[]} [verify] The strings of the file that prove the line, when the line is not
 *   shown exactly as the file holds it.
 * @property {string} [from] A repository file other than the tile's source.
 */

/**
 * @typedef {Object} Tile
 * @property {string} key The key of the tile's strings in `sample.tiles` of the locale strings.
 * @property {string} href The real artifact on GitHub. The tile title links to it.
 * @property {string} path The path line under the tile's text.
 * @property {string} source The repository file the excerpt quotes, relative to the repository root.
 * @property {'milestones' | 'excerpt' | 'abridged' | 'board'} label The key of the preview's visible
 *   label in `sample.labels`.
 * @property {string} [heading] A mono line at the top of the preview, verbatim from the source.
 * @property {Block[]} blocks
 */

const sampleRepo = 'https://github.com/sct-will/carrydown-sample';
const sampleBlob = `${sampleRepo}/blob/main`;
const sampleRoot = 'sample/expense-approvals';

/** The sample's public repository, where the trial starts. */
export const sampleRepoUrl = sampleRepo;

/** @type {Tile[]} The six artifacts, in the order the workflow writes them. */
export const tiles = [
  {
    key: 'plan',
    href: `${sampleBlob}/docs/spec/plan.yaml`,
    path: 'docs/spec/plan.yaml',
    source: `${sampleRoot}/docs/spec/plan.yaml`,
    label: 'milestones',
    blocks: [
      {
        t: 'code',
        lines: [
          'milestones:',
          '  - number: 2',
          '    name: "Route to approvers"',
          '    start: "2027-02-15"',
          '    end: "2027-03-05"',
          '    gate: "A submitted report reaches the right approvers in order and an approver decides it from the inbox."',
          '    rationale: "Routing and the inbox are the two halves of one capability: a submitted report reaches its approvers and they decide it. …"',
          '    joint_demonstration: "The Workflow engineer submits reports in each band of section 3.5 and shows the steps built for them. The Experience engineer approves one report as two approvers in turn from the inbox, and it reaches Approved only after the last step."',
        ],
      },
    ],
  },
  {
    key: 'specification',
    href: `${sampleBlob}/docs/spec/m2-route-to-approvers/wi-03-routing-engine.md`,
    path: 'docs/spec/m2-route-to-approvers/wi-03-routing-engine.md',
    source: `${sampleRoot}/docs/spec/m2-route-to-approvers/wi-03-routing-engine.md`,
    label: 'excerpt',
    heading: 'wi-03-routing-engine.md',
    blocks: [
      { t: 'small', text: 'Depends on WI-01 · Unblocks WI-04, WI-06, WI-07', verify: ['| Depends on | WI-01 |', '| Unblocks | WI-04, WI-06, WI-07 |'] },
      { t: 'h', text: 'Contract', verify: ['## Contract'] },
      {
        t: 'li',
        n: 3,
        text: 'A reminder goes to the current approver after 3 business days without a decision. After 5 business days the step escalates to the next person up the reporting line, and the audit trail records the escalation.',
        verify: ['3. A reminder goes to the current approver after 3 business days without a decision. After 5 business days the step escalates to the next person up the reporting line, and the audit trail records the escalation.'],
      },
      { t: 'h', text: 'Acceptance criteria', verify: ['## Acceptance criteria'] },
      {
        t: 'sub',
        text: 'The reminder is due after 3 business days and the escalation after 5, and a weekend submission counts from the next Monday (`tests/routing.business-days.test.js`).',
        verify: ['- [ ] The reminder is due after 3 business days and the escalation after 5, and a weekend submission counts from the next Monday (`tests/routing.business-days.test.js`).'],
      },
      { t: 'h', text: 'References', verify: ['## References'] },
      { t: 'cite', text: 'architecture section 3.4, Report lifecycle', verify: ['- architecture section 3.4, Report lifecycle'] },
      { t: 'cite', text: 'architecture section 3.5, Routing', verify: ['- architecture section 3.5, Routing'] },
      { t: 'cite', text: 'architecture section 7.1, REST API', verify: ['- architecture section 7.1, REST API'] },
      { t: 'cite', text: 'architecture section 6.2, Edge cases the interviews surfaced', verify: ['- architecture section 6.2, Edge cases the interviews surfaced'] },
    ],
  },
  {
    key: 'context',
    href: `${sampleBlob}/docs/context/wi-03.md`,
    path: 'docs/context/wi-03.md',
    source: `${sampleRoot}/docs/context/wi-03.md`,
    label: 'excerpt',
    heading: 'docs/context/wi-03.md',
    blocks: [
      { t: 'h', text: 'Approved context for WI-03, Approval routing engine', verify: ['# Approved context for WI-03, Approval routing engine'] },
      { t: 'cite', text: "Downstream use: approved for implementation in this repository's code and tests. Not for quoting in issue text. Evidence may include response bodies with synthetic data only." },
      { t: 'small', text: 'architecture 3.4 Report lifecycle · architecture 3.5 Routing · architecture 6.2 Edge cases the interviews surfaced · architecture 7.1 REST API', verify: ['### architecture 3.4 Report lifecycle', '### architecture 3.5 Routing', '### architecture 6.2 Edge cases the interviews surfaced', '### architecture 7.1 REST API'] },
      { t: 'h', text: 'architecture 6.2 Edge cases the interviews surfaced', verify: ['### architecture 6.2 Edge cases the interviews surfaced'] },
      {
        t: 'li',
        n: 6,
        text: 'Finance asked for a reminder after 2 business days (BA-6). Section 3.5 says 3. The architecture document is the ground truth, so work items use 3. The next version of this document should settle the number.',
        verify: ['6. Finance asked for a reminder after 2 business days (BA-6). Section 3.5 says 3. The architecture document is the ground truth, so work items use 3. The next version of this document should settle the number.'],
      },
    ],
  },
  {
    key: 'skill',
    href: `${sampleBlob}/docs/dev/skills/expense-approvals-dev/SKILL.md`,
    path: 'docs/dev/skills/expense-approvals-dev/',
    source: `${sampleRoot}/docs/dev/skills/expense-approvals-dev/SKILL.md`,
    label: 'abridged',
    heading: 'docs/dev/skills/expense-approvals-dev/SKILL.md',
    blocks: [
      { t: 'p', text: '“Orients on one Expense approvals work item before any code change, reading its spec, the ground truth sections it cites and the conventions. …”', verify: ['description: "Orients on one Expense approvals work item before any code change, reading its spec, the ground truth sections it cites and the conventions.'] },
      {
        t: 'li',
        n: 2,
        text: 'Run `python3 <skill folder>/scripts/check_context.py <ID>` with the repository as the working folder, … This is the first command for every work item. …',
        verify: ['2. Run `python3 <skill folder>/scripts/check_context.py <ID>` with the repository as the working folder,', 'This is the first command for every work item.'],
      },
      { t: 'sub', text: 'On exit 0, read `docs/context/<id in lower case>.md`. …' },
      { t: 'sub', text: 'If the output has a block that starts `carrydown: approved inputs changed since your last check`, … read the current specification and context again. Reassess your plan against them. …' },
      { t: 'p', text: 'Do not open `docs/ground-truth/` or any source; the approved context is complete for this item. …' },
    ],
  },
  {
    key: 'issues',
    href: `${sampleRepo}/issues`,
    path: 'github.com/sct-will/carrydown-sample/issues',
    // Issue 9 lives on GitHub. The test checks the excerpt against the copy of its body committed in
    // tests/fixtures/issue-9.md, which names the issue, its title and the day it was read.
    source: 'website/tests/fixtures/issue-9.md',
    label: 'abridged',
    heading: 'sct-will/carrydown-sample#9',
    blocks: [
      { t: 'h', text: 'WI-03 Approval routing engine' },
      { t: 'p', text: 'Target completion on or before 2027-02-19. Checkpoint 2027-02-26, Routing meets inbox.' },
      { t: 'h', text: 'AI engineering notes', verify: ['### AI engineering notes'] },
      { t: 'small', text: 'Specification: https://github.com/sct-will/carrydown-sample/blob/main/docs/spec/m2-route-to-approvers/wi-03-routing-engine.md' },
      { t: 'small', text: "Engineers' skill: https://github.com/sct-will/carrydown-sample/tree/main/docs/dev/skills/expense-approvals-dev" },
      { t: 'small', text: 'Install it once following its README, then start this item by asking your coding agent to work on WI-03. …' },
      { t: 'small', text: 'Ground truth: Architecture document: Sections 3.4, 3.5, 7.1' },
      { t: 'h', text: 'Depends on', verify: ['### Depends on'] },
      { t: 'small', text: 'WI-01 (#7) Service scaffold, flag and API contract', verify: ['- WI-01 (#7) Service scaffold, flag and API contract'] },
    ],
  },
  {
    key: 'project',
    href: 'https://github.com/users/sct-will/projects/2',
    path: 'github.com/users/sct-will/projects/2',
    // The board's published image: the page shows src/assets/sample/board.png, a byte-for-byte copy of
    // this file, and the test compares the two.
    source: 'docs/images/board.png',
    label: 'board',
    blocks: [],
  },
];

/** The page's copy of the board image, relative to the repository root. */
export const boardImage = 'website/src/assets/sample/board.png';

/** The seventh tile: one change followed through the project, from the recorded exercise. */
export const change = {
  key: 'change',
  href: 'https://github.com/sct-will/carrydown/blob/main/docs/sample-run.md#10-an-update-after-planning',
  path: 'docs/sample-run.md · 10. An update after planning',
  source: 'docs/sample-run.md',
  /** The section the path names, checked in the source. */
  section: '## 10. An update after planning',
  /** The changed document, before the "added rule" label of the strings. */
  docPath: 'architecture.md · 3.5',
  /** Rule 5 of architecture section 3.5, the line the update added. */
  rule: 'If an approver in a step has a delegate record that covers the day of routing, the step is assigned to the approver and to the delegate. Either one may decide it, and the first decision closes the step.',
  /** The two work items the agent updated. Their notes are in the strings: WI-03's lines are printed in
   * the record, WI-04's are described, so its note says it is a summary. */
  items: [
    { id: 'WI-03', name: 'Approval routing engine' },
    { id: 'WI-04', name: 'Approver inbox and decisions' },
  ],
};

/** The trial: four steps, each a command or a sentence to copy, and the check's output when it passes
 * (templates/dev-skill/scripts/check_context.py, the success lines). */
export const trial = {
  commands: [
    'git clone https://github.com/sct-will/carrydown-sample.git',
    'cd carrydown-sample',
    'npx skills add https://github.com/sct-will/carrydown-sample/tree/main/docs/dev/skills/expense-approvals-dev -a <your agent>',
    'Work on WI-03. Give me the plan here and stop before any implementation.',
  ],
  /** The file an agent reads when nothing is installed, named in step 3. */
  skillFile: 'docs/dev/skills/expense-approvals-dev/SKILL.md',
  expected: ['carrydown: approved context for WI-03 is ready', 'Read docs/context/wi-03.md. Do not open docs/ground-truth/ or any source.'],
  /** Where the expected lines come from, and the WI-03 values that fill them. */
  expectedSource: 'templates/dev-skill/scripts/check_context.py',
  expectedTemplate: [
    'f"carrydown: approved context for {tag} is ready"',
    'f"Read {md_rel}. Do not open docs/ground-truth/ or any source."',
  ],
};
