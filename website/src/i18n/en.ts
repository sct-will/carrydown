// Every string the pages use, in English. The other locale modules have the same shape: type them as
// `Strings` so the compiler flags a missing key. Brand names and the quoted agent commands stay in
// English in every locale.

export const en = {
  lang: 'en',
  label: 'English',

  site: {
    name: 'Carried context',
    skipLink: 'Skip to main content',
    homeLabel: 'Carried context, home',
  },

  nav: {
    label: 'Primary',
    definition: 'Definition',
    github: 'GitHub',
    docs: 'Docs',
    faq: 'FAQ',
    accessibility: 'Accessibility statement',
    menu: 'Menu',
  },

  controls: {
    themeLabel: 'Theme',
    themeAuto: 'Auto',
    themeDark: 'Dark',
    themeLight: 'Light',
    languageLabel: 'Language',
  },

  footer: {
    label: 'Footer',
    copyright: '© 2026-2027 Will Scott, PhD. Carried-context development. carrydown is Apache 2.0.',
  },

  /** Text for pages that are not written yet. Replaced when the page lands. */
  stub: {
    body: 'This page is being written.',
  },

  home: {
    title: 'Carried-context development, home',
    description:
      'Carried-context development is an approach to agentic development that carries project decisions and context all the way down to each engineer’s coding agent, so the project stays aligned and nothing drifts.',
    h1: 'Context that travels with the work.',
    definition:
      'Carried-context development is an approach to agentic development that carries project decisions and context all the way down to each engineer’s coding agent, so the project stays aligned and nothing drifts.',
    paragraph:
      'Your team provides the project documents, the requirements and the decisions about people and deadlines. Your AI agent uses this ground truth to create a connected plan, a spec for every work item, and GitHub issues that link each spec and cite the document sections behind it. Your AI agent also generates a project-specific agent skill that carries the spec, the decisions behind the work and the cited sections to each engineer’s coding agent. When a document changes, you review one update.',
    buttons: {
      try: 'Try it on GitHub',
      sample: 'See a sample project’s AI agent outputs',
    },
    howHeading: 'How it works',
    statement: {
      heading: 'Carried-context development goes beyond spec-driven development.',
      body: 'Spec-driven development leaves each spec to the engineer writing it. Quality depends on who wrote it. No two specs match and nothing ties them together. They drift as the project changes. Carried-context development derives every spec from the same ground truth, cites the sources and carries every approved change to every coding agent.',
    },
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
      headingBefore: 'Try ',
      headingBrand: 'carrydown',
      headingAfter: ', the open reference implementation.',
      intro:
        'Carried-context development is an approach to agentic development, and there is more than one way to implement it. carrydown is the reference implementation: two Agent Skills you install, a third it generates for your engineers, and the checks that validate every citation. It is open source under Apache 2.0 and works with the coding agent your team already uses.',
      tryButton: 'Try it on GitHub',
      installCommand: 'npx skills add sct-will/carrydown',
      copy: 'Copy',
      copied: 'Copied',
      copyLabel: 'Copy the install command',
      copiedStatus: 'Install command copied to the clipboard.',
      copyFailedStatus: 'Could not copy. Select the command and copy it.',
      needs: 'Needs Node.js 22.20 or later and Git. No Node.js? There is a manual install.',
      tiles: [
        {
          step: 'Step 1',
          title: 'Look at a finished plan.',
          body: 'The sample board and its issues, on GitHub.',
          command: '',
          button: 'Open the sample',
          time: 'One minute. Nothing to install.',
        },
        {
          step: 'Step 2',
          title: 'Read the first conversation.',
          body: 'The questions the agent asks you, and what to answer.',
          command: '',
          button: 'Owner guide',
          time: 'Five minutes. Nothing to install.',
        },
        {
          step: 'Step 3',
          title: 'Try it with one folder of yours.',
          body: 'Install the two carrydown skills, then say',
          command: '“Set up a project plan from these documents.”',
          button: 'Setup guide',
          time: 'An afternoon, mostly reading.',
        },
      ],
      stepsHeading: 'Steps in running carrydown',
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
          what: 'Watch each milestone demonstration and decide pass or fail. They install nothing.',
          say: '',
        },
        {
          who: 'Anyone',
          what: 'Reports a changed source or a spec that seems wrong. One review, then the approved update carries down.',
          say: '“This changed: …”',
        },
      ],
      noCommand: 'No command to say.',
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
