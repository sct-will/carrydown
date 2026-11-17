// Every string the pages use, in English. The other locale modules have the same shape: type them as
// `Strings` so the compiler flags a missing key. Brand names and the quoted agent commands stay in
// English in every locale.

export const en = {
  lang: 'en',
  dir: 'ltr',
  /** The name of the language in that language, for the language control. */
  label: 'English',

  site: {
    name: 'Carried-context development',
    skipLink: 'Skip to main content',
    homeLabel: 'Carried-context development, home',
  },

  nav: {
    label: 'Primary',
    definition: 'Definition',
    github: 'GitHub',
    docs: 'Docs',
    faq: 'FAQ',
    accessibility: 'Accessibility statement',
    menu: 'Menu',
    /** The label of Starlight's docs sidebar button. It must differ from the site menu button. */
    docsMenu: 'Docs menu',
  },

  controls: {
    themeLabel: 'Theme',
    themeAuto: 'Auto',
    themeDark: 'Dark',
    themeLight: 'Light',
    languageLabel: 'Language',
  },

  /** The site search: the header button, and the dialog it opens. Pagefind supplies the strings inside
   * the results list in the page's language. */
  search: {
    button: 'Search',
    title: 'Search this site',
    close: 'Close',
    unavailable: 'Search works on the published site. It is not available in the development preview.',
  },

  /** The Copy page control at the top of each docs page: the page as Markdown, to copy or to open, and
   * its source in the repository. */
  copyPage: {
    button: 'Copy page',
    copied: 'Copied',
    menu: 'More ways to use this page',
    asMarkdown: 'Copy page as Markdown',
    open: 'Open Markdown',
    source: 'View the source on GitHub',
    ok: 'Page copied to the clipboard as Markdown.',
    fail: 'Could not copy. Open the Markdown and copy it from there.',
  },

  /** Shown at the top of every translated page. The English locale never shows it. */
  translation: {
    note: 'This translation is pending review by a native speaker. The English page is the reference.',
    link: 'Read the English page',
  },

  footer: {
    label: 'Footer',
    copyright: '© 2026-present Will Scott, PhD. Carried-context development. carrydown is Apache 2.0.',
  },

  definition: {
    title: 'Carried-context development, definition',
    description:
      'Carried-context development carries a team’s agreed ground truth down into the plan, every specification, every issue and every coding agent’s instructions, cited by section, and carries it down again when the ground truth changes.',
    h1: 'Carried-context development',
    status: ['Status: open method', 'Version 1.0', 'November 2026', 'Will Scott, PhD'],
    contents: 'Contents',
    sections: [
      'Definition',
      'The rules',
      'How it differs from spec-driven development',
      'Reference implementation',
      'How to cite',
      'Changelog',
    ],
    definition:
      'Carried-context development carries a team’s agreed ground truth down into the plan, every specification, every issue and every coding agent’s instructions, cited by section, and carries it down again when the ground truth changes.',
    rules: [
      {
        title: 'One ground truth.',
        body: 'The documents the team agreed are the only human-authored input. Everything downstream is derived from them, and nothing downstream outranks them.',
      },
      {
        title: 'Fitted to real people and dates.',
        body: 'The plan is built around who is available, how much of their time, and when it is due. Give one and the other is derived.',
      },
      {
        title: 'One specification per work item.',
        body: 'A work item is the smallest piece of work an engineer can finish and show. Each one has a specification of its own.',
      },
      {
        title: 'Cited by section.',
        body: 'Every specification, issue and instruction names the sections of the ground truth it came from. A check validates every citation, from a clean clone.',
      },
      {
        title: 'Approved, not generated.',
        body: 'A person decides owners, dates, scope and order, approves what may be shared and with whom, and approves what is published. Nothing posts without a yes.',
      },
      {
        title: 'Carried to the agent.',
        body: 'The engineer’s coding agent reads the specification and the cited sections before it plans a line of code.',
      },
      {
        title: 'Carried again on change.',
        body: 'When the ground truth changes, one review finds the work it touches and keeps the engineers’ corrections. The approved update carries down to every piece of work.',
      },
    ],
    differs:
      'Spec-driven development leaves each spec to the engineer writing it. Quality depends on who wrote it. No two specs match and nothing ties them together. They drift as the project changes. Carried-context development derives every spec from the same ground truth, reviews the specs together, cites the sources and carries every approved change to every coding agent. Context engineering, a neighbor, decides what a model sees in one step; carried context decides what the whole project must obey.',
    compare: {
      aspect: 'Aspect',
      specDriven: 'Spec-driven development',
      carried: 'Carried-context development',
      rows: [
        ['Unit of planning', 'One task or feature', 'The whole project'],
        ['What travels', 'The spec', 'The ground truth, cited by section'],
        ['When the sources change', 'Rewrite the spec', 'One review. Engineer corrections kept'],
        [
          'Who writes the spec',
          'The engineer',
          'Derived by the AI agent from the ground truth, reviewed by the plan owner',
        ],
        ['Consistency between specs', 'None enforced', 'Reviewed together, every citation checked'],
        ['Who decides', 'The developer', 'The plan owner, the engineers, the stakeholders'],
      ],
    },
    reference: {
      body: 'carrydown, two Agent Skills and a generated third, Apache 2.0, first commit 24 October 2026.',
      link: 'github.com/sct-will/carrydown',
    },
    cite: {
      heading: 'How to cite',
      text: 'Scott, W. (2026). Carried-context development, version 1.0. https://carried-context.dev/definition. DOI: to be minted on the first carrydown release.',
      bibtex: `@misc{scott2026carriedcontext,
  author = {Scott, Will},
  title  = {Carried-context development},
  year   = {2026},
  note   = {Version 1.0. Reference implementation: carrydown},
  url    = {https://carried-context.dev/definition}
}`,
    },
    changelog: '1.0, November 2026. First publication.',
  },

  faq: {
    title: 'Questions, carried-context development',
    description:
      'Answers about carried-context development and carrydown: how it differs from spec-driven development, why it is not waterfall, how the GitHub work stays reconciled with the ground truth, and what carrydown does not do.',
    h1: 'Questions',
    intro: 'Answers to the questions that come up most, with links into the docs where there is more. Each question has a link of its own.',
    /** Each item has a stable id, the same in every language, so a link to a question holds across
     * translations. An optional `more` link under the answer leads into the docs or the repository: a
     * site path gets the locale prefix, an address is used as written. */
    items: [
      {
        id: 'spec-driven',
        q: 'How is this different from traditional spec-driven development?',
        a: 'In spec-driven development each engineer writes the spec for their own task. Quality depends on who wrote it, no two specs match, and nothing ties them together once the project starts to change. Carried-context development starts one level up. Your AI agent derives every spec from the same agreed ground truth and cites the sections each one came from. The plan owner reviews the specs together before anything is published, and a check validates every citation from a clean clone. When the ground truth changes, one review carries the approved change to every spec, issue and coding agent, instead of each engineer rewriting their own.',
        more: { label: 'See the side-by-side comparison on the definition page.', href: '/definition/#differs' },
      },
      {
        id: 'waterfall',
        q: 'Isn’t this just waterfall?',
        a: 'No. Waterfall fixes the whole plan up front and treats a change as a failure of the plan. Here the plan, the specs and the issues are files in Git, so changing them is cheap and the change is reviewed like code. Work units take the length the work needs rather than fixed-length boxes. Each milestone ends with a demonstration that the stakeholders pass or fail, and what the team learns goes back into the ground truth and is carried down again. You can plan, build a little, learn and update the plan as often as the project needs.',
        more: { label: 'Read how a change is carried down in the method.', href: '/docs/method/#when-the-project-changes' },
      },
      {
        id: 'reconciled',
        q: 'How do the project board, the issues, the specs and the engineers’ skill stay reconciled with the ground truth?',
        a: 'You tell your agent what changed. Say “This changed: …” and describe the change or hand over the revised documents. The agent compares the change with the sources you last reviewed and with the current work, finds the specs and issues the change touches, keeps the engineers’ corrections that still fit, and shows you one review of the proposed updates and any conflicts. Nothing moves until you approve. The approved update then goes through the same release as the plan: it updates the board and the issues you choose, never deletes any of them, and regenerates the engineers’ skill, so each coding agent reads the new specification the next time an engineer names a work item.',
        more: { label: 'Follow the steps in the plan owner guide.', href: '/docs/plan-owner-guide/#when-the-project-changes' },
      },
      {
        id: 'certify',
        q: 'Does it certify that my documents are right?',
        a: 'No. The ground truth is whatever your team agreed, and the agent takes it as given. What it adds is review. It renders each document, helps you review it with prompts, and a second-pass review challenges the finished plan against its sources, its constraints and its staffing choices. If a document is wrong, the plan is wrong in the same way, and the fix belongs in the document rather than in the plan.',
      },
      {
        id: 'one-person',
        q: 'Is it for a one-person spike?',
        a: 'Not really. The method pays off when several engineers share weeks of work under an agreed architecture and specs that drift apart cost real time. For a one-person spike the plan, the specs and the board are more structure than the work needs. It is particularly well suited to enterprise teams, where governance rules, engineering standards and company context are part of the ground truth and several teams build on one architecture. Use it when a team hands work to coding agents and needs every one of them to start from the same decisions.',
      },
      {
        id: 'governance',
        q: 'How does this support AI governance?',
        a: 'Governance rules, engineering standards and company context go in as ground truth beside the technical documents, in Word, Markdown, plain text or reviewed extractions from PDF and image files. The plan records each source’s version and precedence, every work item cites the sections that apply to it, and the checks validate those citations while you draft and again in a clean clone. The generated engineers’ skill points each coding agent at the approved context, so the agent reads the applicable rules before it plans code. You review the drafts and approve exactly what is shared, with whom and where, after a preview and a dry run, and the plan, the specs, the source versions and the recorded decisions stay in your repository. The automated checks and the second-pass review record evidence and risk, and your team still judges whether the work meets your organization’s requirements.',
        more: { label: 'Read how carrydown supports AI governance.', href: '/docs/#how-does-carrydown-support-ai-governance' },
      },
      {
        id: 'watch',
        q: 'Does it watch my documents?',
        a: 'No. carrydown has no file watcher and never reads your document system on its own. An update starts when you say what changed and provide the revised material, and it ends when you approve the review. The milestone review in the plan owner guide also asks whether any source, requirement or constraint has changed since the last plan, so a change is caught there at the latest.',
      },
      {
        id: 'agents',
        q: 'Which coding agents?',
        a: 'Any coding agent that supports Agent Skills and can read and edit project files and run commands. Your engineers keep the one they already use. The generated skill is a folder of instructions that their agent loads, and it holds no credential. The setup guide lists the supported agents and the install steps for each.',
        more: { label: 'Choose a coding agent in the setup guide.', href: '/docs/setup/#choose-a-coding-agent' },
      },
      {
        id: 'license',
        q: 'Which license?',
        a: 'Apache 2.0, for the skills, the scripts and the templates. The repository carries the security policy, the changelog and the answers to common enterprise security questions, each labeled supported, supported with prerequisites or planned.',
        more: { label: 'Open the repository on GitHub.', href: 'https://github.com/sct-will/carrydown' },
      },
    ],
    doesNotHeading: 'What carrydown does not do',
    /** The literal text --apply is set in a monospace face wherever it appears. */
    doesNot: [
      'It writes no application code.',
      'Every GitHub write is a dry run until you pass --apply.',
      'It never deletes issues, labels, projects or repositories.',
      'The update comparison runs on your machine. No network, no token, no model call.',
      'Confidential documents stay on your machine unless you say everyone may see them.',
      'Names, days off and allocation stay in a private file, never in the plan.',
      'If you stop, you keep plain Markdown and ordinary GitHub issues.',
    ],
  },

  accessibility: {
    title: 'Accessibility statement',
    description:
      'This site is meant to be usable by everyone. It aims to meet the Web Content Accessibility Guidelines (WCAG) 2.2 at level AA.',
    h1: 'Accessibility statement',
    intro:
      'This site is meant to be usable by everyone, including people who use a screen reader, a keyboard alone, magnification, or reduced motion. It aims to meet the Web Content Accessibility Guidelines (WCAG) 2.2 at level AA.',
    doneHeading: 'What has been done',
    done: [
      'Text and interface colors are checked for contrast in both the light and the dark theme, and you can choose either theme or follow your system.',
      'Every page works with a keyboard alone, with a visible focus indicator and a skip link to the main content.',
      'The diagram is drawn as text and vector shapes, so it scales, respects your theme, and carries a written description for screen readers.',
      'Nothing on the site moves on its own. Any future animation will respect the reduced-motion setting and offer a still picture.',
      'Headings, landmarks and link text are written to be read in order and out of context.',
      'The site is checked with automated tools before each release and reviewed by hand with a screen reader.',
    ],
    notFinishedHeading: 'What is not finished',
    notFinished:
      'Translations of the site are being reviewed by native speakers and go live one language at a time. The documentation section is generated from the repository and may lag the rest of the site on these points until each release is checked.',
    contactHeading: 'Tell us about a problem',
    contactBefore:
      'If something on this site is hard to use with assistive technology, or you need the content in another form, write to ',
    contactAfter: '. Say which page and what happened. You should hear back within ten working days.',
    review:
      'This statement describes the site’s intent and its current state. It is reviewed when the site changes. Last reviewed 16 November 2026.',
  },

  home: {
    title: 'Carried context, one ground truth for every coding agent',
    description:
      'Carried-context development is an approach to agentic development that carries project decisions and context all the way down to each engineer’s coding agent, so the project stays aligned and nothing drifts.',
    h1: [
      'Carried-context development goes beyond spec-driven development.',
      'The context travels with the work.',
    ],
    definition:
      'Keep the project aligned by giving each engineer’s coding agent the same project decisions and context.',
    paragraph:
      'Your team provides the project documents, the requirements and the decisions about people and deadlines. Your AI agent uses this ground truth to create a connected plan, a spec for every work item, and GitHub issues that link each spec and cite the document sections behind it. Your AI agent also generates a project-specific agent skill that carries the spec, the decisions behind the work and the cited sections to each engineer’s coding agent. When a document changes, you review one update.',
    buttons: {
      try: 'Start here',
      sample: 'See a sample project’s AI agent outputs',
    },
    /** A small line under the buttons. */
    license: 'Open source under Apache 2.0.',
    howHeading: 'How it works',
    /** The last sentence under How it works; the middle word is the link to the README section. */
    learnMore: { before: 'Learn more ', link: 'here', after: '.' },
    sideParagraphs: [
      'When engineers write specs independently, quality varies and the specs drift apart as the project changes.',
      'Carried-context development ties every spec to the same ground truth, cites the sources, and delivers every approved change to every coding agent.',
    ],
    values: [
      {
        eyebrow: 'Connected plan',
        title: 'Planned as one connected whole.',
        body: 'One plan and every spec come from the same ground truth. Dependencies, interfaces and acceptance criteria are reviewed together for gaps and conflicts, and a check validates every citation.',
      },
      {
        eyebrow: 'Engineering handoff',
        title: 'A handoff that reaches the coding agent.',
        body: 'Each issue links its spec and cites its ground-truth sections. A project-specific agent skill puts the approved spec, those sections and your conventions in front of the coding agent before it plans code.',
      },
      {
        eyebrow: 'Project context kept in sync',
        title: 'Changes raised by the project lead or the engineers carry through.',
        body: 'A project lead reports a changed source, or an engineer flags a wrong spec. The agent finds the affected work, keeps corrections that still fit and brings conflicts to you. Approved updates flow through the specs, issues and handoff.',
      },
    ],
    carrydown: {
      heading: 'Try it out',
      intro:
        'Carried-context development is an approach to agentic development, and there is more than one way to implement it. carrydown is a reference implementation: two Agent Skills you install, a third it generates for your engineers, and the checks that validate every citation. It is open source under Apache 2.0 and works with the coding agent your team already uses.',
      tiles: [
        {
          step: 'Step 1',
          title: 'Look at a sample finished plan.',
          body: 'The sample board and its issues, on GitHub.',
          command: '',
          button: 'Open the sample',
        },
        {
          step: 'Step 2',
          title: 'Run carrydown on your project.',
          body: 'Install the two carrydown skills, then say',
          command: '“Set up a project plan from these documents.”',
          button: 'Setup guide',
        },
      ],
      stepsHeading: 'Your AI agent guides you through running carrydown on your project',
      steps: [
        {
          who: 'Plan owner',
          what: 'Installs the two carrydown skills and starts the plan.',
          say: '“Set up a project plan from these documents.”',
        },
        {
          who: 'Plan owner',
          what: 'Reviews the plan and the specs, then publishes.',
          say: '“Put the plan on GitHub.”',
        },
        {
          who: 'Each engineer',
          what: 'Installs the generated agent skill once and names a work item.',
          say: '“Work on WI-03.”',
        },
        {
          who: 'Stakeholders',
          what: 'Report a changed source or a spec that seems wrong. One review, then the approved update carries down.',
          say: '“This changed: …”',
        },
      ],
      reviewNote: 'Stakeholders, project owners and engineering managers watch each milestone and decide pass or fail. Human-in-the-loop review is explicitly part of the method.',
    },
    /** The What you get section: the outputs, summarized from the README's list. */
    whatYouGet: {
      heading: 'What you get',
      intro:
        'Your AI agent generates these with the carrydown skills. Every work item can cite sections from one or more sources, with dates and capacity checked against the named team.',
      /** The word between a title and the path that follows it, where there is one. */
      inWord: 'in',
      items: [
        { title: 'A plan', path: 'docs/spec/plan.yaml', body: 'Milestones, tracks, owners and dates fitted to your people and time, with a reason for every milestone.' },
        { title: 'One specification per work item', path: '', body: 'The smallest piece of work an engineer can finish and show, citing its sections and checked against the plan on every pull request.' },
        { title: 'One approved context per work item', path: 'docs/context/', body: 'The exact source text the item cites and the decisions behind it, approved by you. The only part of your documents that reaches the engineers’ agents.' },
        { title: 'A release receipt', path: 'docs/release/', body: 'A small public file naming the approved release, its state and its expiry.' },
        { title: 'A second-pass review report', path: '', body: 'Coverage, evidence, reasoning and risk, with your decisions and the checks on accepted repairs.' },
        { title: 'GitHub issues', path: '', body: 'One per work item under a sub-epic per milestone, each telling the engineer’s agent what to read.' },
        { title: 'A GitHub Project board', path: '', body: 'Work units, tracks, dates and checkpoints filled in.' },
        { title: 'The engineer’s AI agent skill', path: '', body: 'Generated from your specifications and committed in your repository. An engineer starts a work item by naming it, for example “Work on [work item ID]”, and the coding agent reads that item’s specification and approved context before it touches code.' },
      ],
    },
  },

  /** Labels of the How it works diagram, in the wide drawing and in the stacked variant. */
  diagram: {
    ariaLabel:
      'Project context you provide, documents and decisions and later a change, feeds the AI agent, which generates for your team a project plan for review and approval, a spec for each work item, a GitHub board with issues and milestones where each issue links its spec and cites its sources, and a project-specific agent skill installed once by each engineer using a coding agent.',
    provideHeading: 'Project context you provide',
    generatesHeading: 'AI agent generates for your team',
    documents: 'Documents',
    documentsNote: 'architecture, requirements, rules, or other',
    decisions: 'Decisions',
    decisionsNote: 'people, allocation, deadlines',
    later: 'Later',
    changed: 'Something changed',
    changedNote: 'a changed document, or a wrong spec',
    agent: 'AI agent',
    agentVerbs: ['reads, plans, cites,', 'briefs, reconciles'],
    plans: 'Plans',
    plansTitle: 'Project plan for review and approval',
    plansNote: 'milestones, tracks, dates fitted to your people',
    writes: 'Writes',
    writesTitle: 'A spec for each work item',
    writesNote: 'all from the same ground truth',
    opens: 'Opens',
    opensTitle: 'GitHub board with issues and milestones',
    opensNote: 'each issue links its spec and cites its sources',
    generates: 'Generates',
    generatesTitle: 'Project-specific agent skill',
    generatesNote: 'installed once by each engineer',
    engineers: ['Engineers using', 'coding agents'],
  },
};

export type Strings = typeof en;

/** The not-found page's text. Starlight renders one not-found page, in English, at the site root. */
export const notFoundText = 'Page not found. Check the address, search the site, or use the links above.';
