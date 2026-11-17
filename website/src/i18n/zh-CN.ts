// Simplified Chinese strings. Same shape as en.ts, so the compiler flags a missing key. Brand names,
// the term "Carried-context development" and the quoted agent commands stay in English. A native
// speaker has not reviewed this translation yet, and every translated page says so.
import { en, type Strings } from './en';

export const zhCN: Strings = {
  lang: 'zh-CN',
  dir: 'ltr',
  label: '简体中文',

  site: {
    name: 'Carried-context development',
    skipLink: '跳到主要内容',
    homeLabel: 'Carried-context development，首页',
  },

  nav: {
    label: '主导航',
    definition: '定义',
    github: 'GitHub',
    docs: '文档',
    faq: 'FAQ',
    accessibility: '无障碍声明',
    menu: '菜单',
    docsMenu: '文档菜单',
  },

  controls: {
    themeLabel: '主题',
    themeAuto: '自动',
    themeDark: '深色',
    themeLight: '浅色',
    languageLabel: '语言',
  },

  search: {
    button: '搜索',
    title: '搜索本站',
    close: '关闭',
    unavailable: '搜索在已发布的网站上可用。开发预览中不可用。',
  },

  copyPage: {
    button: '复制页面',
    copied: '已复制',
    menu: '使用本页的更多方式',
    asMarkdown: '以 Markdown 复制页面',
    open: '打开 Markdown',
    source: '在 GitHub 上查看源文件',
    ok: '页面已以 Markdown 形式复制到剪贴板。',
    fail: '无法复制。请打开 Markdown，从那里复制。',
  },

  translation: {
    note: '本翻译尚待母语人士审校。以英文页面为准。',
    link: '阅读英文页面',
  },

  footer: {
    label: '页脚',
    copyright: en.footer.copyright,
  },

  definition: {
    title: 'Carried-context development，定义',
    description:
      'Carried-context development 把团队商定的基准事实向下传递到计划、每一份规格、每一个 issue 和每个编码代理的指令中，并按章节引用，当基准事实变化时再次向下传递。',
    h1: 'Carried-context development',
    status: ['状态：开放方法', '版本 1.0', '2026年11月', 'Will Scott, PhD'],
    contents: '目录',
    sections: ['定义', '规则', '与规格驱动开发的区别', '参考实现', '如何引用', '更新日志'],
    definition:
      'Carried-context development 把团队商定的基准事实向下传递到计划、每一份规格、每一个 issue 和每个编码代理的指令中，并按章节引用，当基准事实变化时再次向下传递。',
    rules: [
      {
        title: '只有一个基准事实。',
        body: '团队商定的文档是唯一由人撰写的输入。下游的一切都由它们派生，下游的任何内容都不能凌驾于它们之上。',
      },
      {
        title: '贴合真实的人员和日期。',
        body: '计划围绕谁有空、能投入多少时间以及何时交付来制定。确定其一，另一个便可推导出来。',
      },
      {
        title: '每个工作项一份规格。',
        body: '工作项是工程师能够完成并演示的最小工作单元。每个工作项都有自己的规格。',
      },
      {
        title: '按章节引用。',
        body: '每份规格、每个 issue 和每条指令都会写明它出自基准事实的哪些章节。检查会从干净的克隆验证每一处引用。',
      },
      {
        title: '经过批准，而非自动生成。',
        body: '负责人、日期、范围和顺序由人来决定，哪些内容可以与谁共享、哪些内容可以发布也由人批准。没有同意，什么都不会发布。',
      },
      {
        title: '传递到代理。',
        body: '工程师的编码代理在规划任何一行代码之前，先阅读规格和所引用的章节。',
      },
      {
        title: '变化时再次传递。',
        body: '基准事实变化时，一次审阅就能找到受影响的工作，并保留工程师的修正。获批的更新会向下传递到每一项工作。',
      },
    ],
    differs:
      '规格驱动开发把每份规格交给撰写它的工程师。质量取决于谁来写。没有两份规格是一致的，也没有什么把它们联系在一起。随着项目变化，它们会逐渐偏离。Carried-context development 从同一个基准事实派生每一份规格，对规格一并审阅，引用来源，并把每一项获批的变更传递给每个编码代理。上下文工程是近邻，它决定模型在一个步骤中看到什么；carried context 决定整个项目必须遵守什么。',
    compare: {
      aspect: '方面',
      specDriven: '规格驱动开发',
      carried: 'Carried-context development',
      rows: [
        ['规划单位', '一个任务或功能', '整个项目'],
        ['传递的内容', '规格', '按章节引用的基准事实'],
        ['来源变化时', '重写规格', '一次审阅。保留工程师的修正'],
        ['谁来写规格', '工程师', '由 AI 代理从基准事实派生，由计划负责人审阅'],
        ['规格之间的一致性', '不强制', '一并审阅，逐一检查引用'],
        ['谁来决定', '开发者', '计划负责人、工程师、利益相关方'],
      ],
    },
    reference: {
      body: 'carrydown，两个 Agent Skills 和一个生成的第三个，Apache 2.0，首次提交于2026年10月24日。',
      link: 'github.com/sct-will/carrydown',
    },
    cite: {
      heading: '如何引用',
      text: en.definition.cite.text,
      bibtex: en.definition.cite.bibtex,
    },
    changelog: '1.0，2026年11月。首次发布。',
  },

  faq: {
    title: '常见问题，carried-context development',
    description:
      '关于 carried-context development 和 carrydown 的解答：它与规格驱动开发的区别、为什么它不是瀑布式、GitHub 上的工作如何与基准事实保持一致，以及 carrydown 不做什么。',
    h1: '常见问题',
    intro: '最常见问题的解答，并在有更多内容处链接到文档。每个问题都有自己的链接。',
    items: [
      {
        id: 'spec-driven',
        q: '这与传统的规格驱动开发有什么不同？',
        a: '在规格驱动开发中，每位工程师为自己的任务编写规格。质量取决于写的人，没有两份规格是一样的，项目一旦开始变化，也没有什么把它们联系在一起。Carried-context development 从更高一层开始。您的 AI 代理从同一个商定的基准事实派生每一份规格，并引用它所出自的章节。计划负责人在发布任何内容之前把规格放在一起审阅，检查会从干净的克隆验证每一处引用。基准事实变化时，一次审阅就把批准的变更传递到每一份规格、每个 issue 和每个编码代理，而不是每位工程师各自重写。',
        more: { label: '在定义页面查看并排对比。', href: '/definition/#differs' },
      },
      {
        id: 'waterfall',
        q: '这不就是瀑布式吗？',
        a: '不是。瀑布式把整个计划预先固定，并把变更视为计划的失败。在这里，计划、规格和 issue 都是 Git 中的文件，所以修改成本低，而且变更像代码一样经过审阅。工作单元按工作所需的时长进行，而不是固定长度的时间盒。每个里程碑以一次演示结束，由相关方决定通过或不通过，团队学到的东西回到基准事实并再次向下传递。您可以规划、构建一点、学习，并按项目需要随时更新计划。',
        more: { label: '在方法页面阅读变更如何向下传递。', href: '/docs/method/#when-the-project-changes' },
      },
      {
        id: 'reconciled',
        q: '项目看板、issue、规格和工程师的 skill 如何与基准事实保持一致？',
        a: '您告诉代理什么变了。说“This changed: …”并描述变更，或交给它修订后的文档。代理把变更与您上次审阅的来源和当前工作比较，找出受影响的规格和 issue，保留仍然适用的工程师修正，并向您展示一次审阅，列出建议的更新和所有冲突。在您批准之前，什么都不会动。批准的更新随后经过与计划相同的发布流程：更新您选择的看板和 issue，不删除任何一项，并重新生成工程师的 skill，这样下次工程师指定工作项时，每个编码代理读到的都是新的规格。',
        more: { label: '按照计划负责人指南中的步骤操作。', href: '/docs/plan-owner-guide/#when-the-project-changes' },
      },
      {
        id: 'certify',
        q: '它能证明我的文档是正确的吗？',
        a: '不能。基准事实是团队商定的内容，代理把它当作既定事实。它增加的是审阅。它渲染每份文档，用提问帮助您审阅，并由第二轮审阅把完成的计划与其来源、约束和人员安排决定进行对照。如果文档是错的，计划也会以同样的方式出错，修正应该放在文档里，而不是计划里。',
      },
      {
        id: 'one-person',
        q: '适合一个人做的 spike 吗？',
        a: '不太适合。当多名工程师在商定的架构下共同承担数周的工作，而规格的偏离会真正耗费时间时，这个方法才划算。对于一个人做的 spike，计划、规格和看板的结构超出了工作的需要。它特别适合企业团队，那里的治理规则、工程标准和公司背景是基准事实的一部分，多个团队在同一个架构上构建。当团队把工作交给编码代理，并且需要每一个代理都从同样的决定出发时，再使用它。',
      },
      {
        id: 'governance',
        q: '它如何支持 AI 治理？',
        a: '治理规则、工程标准和公司背景与技术文档一起作为基准事实输入，格式可以是 Word、Markdown、纯文本，或从 PDF 和图片文件中经审阅的提取内容。计划记录每个来源的版本和优先级，每个工作项引用适用于它的章节，检查在您起草时验证这些引用，并在干净的克隆中再验证一次。生成的工程师 skill 把每个编码代理指向已批准的上下文，代理在规划代码之前会先读取适用的规则。您审阅草稿，并在看过预览和演练之后，准确批准共享什么、与谁共享、在哪里共享。计划、规格、来源版本和记录的决定都留在您的仓库中。自动检查和第二轮审阅记录证据和风险，而工作是否满足组织要求，仍由您的团队判断。',
        more: { label: '阅读 carrydown 如何支持 AI 治理。', href: '/docs/#how-does-carrydown-support-ai-governance' },
      },
      {
        id: 'withhold',
        q: '能否让某些上下文不进入规格、工程师的 skill 和编码代理？',
        a: '可以。工程师及其编码代理只会看到每个工作项的已批准上下文：工作项引用的来源原文和背后的决定，而这些内容在发布前都由您批准。在渲染或复制任何内容之前，代理会先问一个问题：所有能读取这个仓库的人，是否都可以看到这些文档的全部内容和您的人员安排笔记？如果回答否，它会在您机器上的私有工作区起草，仓库只接收您批准的产出，绝不会收到受限的原件或其完整渲染。每次发布都会先向您展示预览，说明将共享什么、与谁共享、在哪里共享，并在写入之前进行一次演练。姓名、休假和投入比例保存在一个私有文件里，绝不会进入计划、规格或 skill。还有两个限制。能读取仓库的人都能读取每一份已批准的上下文，所以无法只让一位工程师看到某个章节而对另一位隐藏，部分读者不得查看的工作会作为受限项留在发布之外。而已经交付的文本无法收回。',
        more: { label: '在设置指南中阅读谁可以看到您的文档。', href: '/docs/setup/#before-you-add-documents-who-may-see-them' },
      },
      {
        id: 'watch',
        q: '它会监视我的文档吗？',
        a: '不会。carrydown 没有文件监视器，也从不自行读取您的文档系统。更新在您说明变更并提供修订材料时开始，在您批准审阅时结束。计划负责人指南中的里程碑审阅也会询问自上次计划以来是否有来源、需求或约束发生了变化，所以变更最迟会在那里被发现。',
      },
      {
        id: 'agents',
        q: '支持哪些编码代理？',
        a: '任何支持 Agent Skills、能够读写项目文件并运行命令的编码代理。工程师继续使用他们已有的代理。生成的 skill 是代理加载的一个指令文件夹，不包含任何凭据。设置指南列出了支持的代理和各自的安装步骤。',
        more: { label: '在设置指南中选择编码代理。', href: '/docs/setup/#choose-a-coding-agent' },
      },
      {
        id: 'license',
        q: '采用什么许可证？',
        a: 'Apache 2.0，涵盖 skill、脚本和模板。仓库中有安全策略、更新日志，以及对企业常见安全问题的解答，每条解答都标注为已支持、有前提条件地支持或计划中。',
        more: { label: '在 GitHub 上打开仓库。', href: 'https://github.com/sct-will/carrydown' },
      },
    ],
    doesNotHeading: 'carrydown 不做什么',
    doesNot: [
      '它不编写应用程序代码。',
      '在你传入 --apply 之前，每一次对 GitHub 的写入都只是试运行。',
      '它从不删除 issue、标签、项目或仓库。',
      '更新比较在你的机器上运行。没有网络，没有令牌，也不调用模型。',
      '机密文档留在你的机器上，除非你说明所有人都可以查看。',
      '姓名、休假日和分配情况保存在私有文件中，绝不写入计划。',
      '如果你不再使用，仍然保留纯 Markdown 和普通的 GitHub issue。',
    ],
  },

  accessibility: {
    title: '无障碍声明',
    description: '本网站旨在让所有人都能使用。目标是达到 Web Content Accessibility Guidelines (WCAG) 2.2 的 AA 级。',
    h1: '无障碍声明',
    intro:
      '本网站旨在让所有人都能使用，包括使用屏幕阅读器、只用键盘、放大显示或减少动态效果的人。目标是达到 Web Content Accessibility Guidelines (WCAG) 2.2 的 AA 级。',
    doneHeading: '已完成的工作',
    done: [
      '文字和界面颜色在浅色和深色两种主题下都检查了对比度，你可以选择其中一种，也可以跟随系统设置。',
      '每个页面都可以只用键盘操作，有可见的焦点指示，并提供跳到主要内容的链接。',
      '图表由文字和矢量图形绘制，因此可以缩放、跟随你的主题，并为屏幕阅读器提供文字说明。',
      '网站上没有任何内容会自行移动。今后的任何动画都会遵守减少动态效果的设置，并提供静态图片。',
      '标题、地标区域和链接文字的写法，便于按顺序阅读，也便于脱离上下文阅读。',
      '网站在每次发布前用自动化工具检查，并由人工使用屏幕阅读器审阅。',
    ],
    notFinishedHeading: '尚未完成的工作',
    notFinished:
      '网站的翻译正在由母语人士审校，将逐种语言上线。文档部分由代码仓库生成，在每个版本检查完成之前，这些方面可能落后于网站的其他部分。',
    contactHeading: '告诉我们遇到的问题',
    contactBefore: '如果本网站的某些内容在使用辅助技术时难以使用，或者你需要其他形式的内容，请写信到 ',
    contactAfter: '。请说明是哪个页面以及发生了什么。你应该会在十个工作日内收到回复。',
    review: '本声明说明网站的意图和当前状态。网站变化时会重新审阅。最近一次审阅是2026年11月16日。',
  },

  home: {
    title: 'Carried context，为每个编码代理提供同一个基准事实',
    description:
      'Carried-context development 是一种智能体开发方法，把项目决策和上下文一直传递到每位工程师的编码代理，让项目保持一致，不再偏离。',
    h1: [
      'Carried-context development 超越规格驱动开发。',
      '上下文与工作同行。',
    ],
    definition:
      '把同样的项目决策和上下文交给每位工程师的编码代理，让项目保持一致。',
    paragraph:
      '你的团队提供项目文档、需求，以及关于人员和截止日期的决策。你的 AI 代理以这些基准事实为依据，创建一份相互关联的计划、每个工作项的规格，以及链接各自规格并引用其背后文档章节的 GitHub issue。你的 AI 代理还会生成一个项目专用的 agent skill，把规格、工作背后的决策和所引用的章节传递给每位工程师的编码代理。文档发生变化时，你只需审阅一次更新。',
    buttons: {
      try: '从这里开始',
      sample: '查看示例项目的 AI 代理产出',
    },
    /** A small line under the buttons. */
    license: '以 Apache 2.0 开源。',
    howHeading: '工作原理',
    /** The last sentence under How it works; the middle word is the link to the README section. */
    learnMore: { before: '更多信息请看', link: '这里', after: '。' },
    sideParagraphs: [
      '工程师各自独立撰写规格时，质量参差不齐，规格也会随着项目的变化而彼此偏离。',
      'Carried-context development 把每份规格绑定到同一个基准事实，引用来源，并把每一项获批的变更交付给每个编码代理。',
    ],
    values: [
      {
        eyebrow: '相互关联的计划',
        title: '作为一个相互关联的整体来规划。',
        body: '一份计划和每一份规格都来自同一个基准事实。依赖关系、接口和验收标准会一并审阅，找出缺口和冲突，检查会验证每一处引用。',
      },
      {
        eyebrow: '工程交接',
        title: '交接直达编码代理。',
        body: '每个 issue 都链接它的规格，并引用基准事实的对应章节。项目专用的 agent skill 会在编码代理规划代码之前，把获批的规格、这些章节和你的约定摆在它面前。',
      },
      {
        eyebrow: '项目上下文保持同步',
        title: '项目负责人或工程师提出的变更会一路传递。',
        body: '项目负责人报告某个来源发生了变化，或者工程师指出某份规格有误。代理会找出受影响的工作，保留仍然适用的修正，并把冲突交给你处理。获批的更新会流向规格、issue 和交接。',
      },
    ],
    carrydown: {
      heading: '试一试',
      intro:
        'Carried-context development 是一种智能体开发方法，实现它的方式不止一种。carrydown 是参考实现：你安装的两个 Agent Skills，它为你的工程师生成的第三个，以及验证每一处引用的检查。它以 Apache 2.0 开源，可与你的团队已经在用的编码代理配合使用。',
      tiles: [
        {
          step: '第 1 步',
          title: '看一份完成的示例计划。',
          body: 'GitHub 上的示例看板及其 issue。',
          command: '',
          button: '打开示例',
        },
        {
          step: '第 2 步',
          title: '在你的项目上运行 carrydown。',
          body: '安装两个 carrydown skill，然后说',
          command: en.home.carrydown.tiles[1].command,
          button: '安装指南',
        },
      ],
      stepsHeading: '你的 AI 代理引导你在项目中运行 carrydown',
      steps: [
        {
          who: '计划负责人',
          what: '安装两个 carrydown skill，并启动计划。',
          say: en.home.carrydown.steps[0].say,
        },
        {
          who: '计划负责人',
          what: '审阅计划和规格，然后发布。',
          say: en.home.carrydown.steps[1].say,
        },
        {
          who: '每位工程师',
          what: '安装一次生成的 agent skill，并指明一个工作项。',
          say: en.home.carrydown.steps[2].say,
        },
        {
          who: '利益相关方',
          what: '报告某个来源有变化，或某份规格似乎有误。一次审阅之后，获批的更新向下传递。',
          say: en.home.carrydown.steps[3].say,
        },
      ],
      reviewNote: '利益相关方、项目负责人和工程经理观看每个里程碑并决定通过与否。人工审核是这一方法明确的一部分。',
    },
    /** The What you get section: the outputs, summarized from the README's list. */
    whatYouGet: {
      heading: '你会得到什么',
      intro:
        '你的 AI 代理用 carrydown 的 skill 生成这些产出。每个工作项都可以引用一个或多个来源的章节，日期和产能会对照指定的团队进行核对。',
      /** The word between a title and the path that follows it, where there is one. */
      inWord: '位于',
      items: [
        { title: '一份计划', path: 'docs/spec/plan.yaml', body: '里程碑、工作线、负责人和日期按你的人员和时间来安排，每个里程碑都写明理由。' },
        { title: '每个工作项一份规格', path: '', body: '工程师能够完成并展示的最小工作单元，引用其依据的章节，并在每次拉取请求时对照计划检查。' },
        { title: '每个工作项一份已批准的上下文', path: 'docs/context/', body: '工作项所引用章节的原文和背后的决策，由你批准。这是你的文档中唯一会到达工程师代理的部分。' },
        { title: '一份发布回执', path: 'docs/release/', body: '一个小的公开文件，写明已批准的发布、其状态和有效期。' },
        { title: '一份二次审阅报告', path: '', body: '覆盖范围、证据、推理和风险，加上你的决定以及对已接受修复的检查。' },
        { title: 'GitHub issue', path: '', body: '每个工作项一个，归在每个里程碑的子史诗之下，每个都告诉工程师的代理该读什么。' },
        { title: '一个 GitHub 项目看板', path: '', body: '工作单元、工作线、日期和检查点均已填好。' },
        { title: '工程师的 AI 代理 skill', path: '', body: '由你的规格生成并提交到你的仓库。工程师通过点名来开始一个工作项，例如“Work on [work item ID]”，编码代理会先读取该工作项的规格和已批准的上下文。' },
      ],
    },
  },

  diagram: {
    ariaLabel:
      '你提供的项目上下文，包括文档、决策以及之后的变更，输入 AI 代理。AI 代理为你的团队生成：供审阅和批准的项目计划、每个工作项的规格、带有 issue 和里程碑的 GitHub 看板（每个 issue 链接其规格并引用其来源），以及项目专用的 agent skill，由每位工程师安装一次，并配合编码代理使用。',
    provideHeading: '你提供的项目上下文',
    generatesHeading: 'AI 代理为团队生成',
    documents: '文档',
    documentsNote: '架构、需求、规则等',
    decisions: '决策',
    decisionsNote: '人员、分配、截止日期',
    later: '之后',
    changed: '有变化',
    changedNote: '文档变更，或规格有误',
    agent: 'AI 代理',
    agentVerbs: ['阅读、规划、引用、', '交接、对账'],
    plans: '规划',
    plansTitle: '供审阅和批准的项目计划',
    plansNote: '里程碑、工作线、贴合人员的日期',
    writes: '撰写',
    writesTitle: '每个工作项一份规格',
    writesNote: '全部出自同一个基准事实',
    opens: '创建',
    opensTitle: '带 issue 和里程碑的 GitHub 看板',
    opensNote: '每个 issue 链接规格并引用来源',
    generates: '生成',
    generatesTitle: '项目专用的 agent skill',
    generatesNote: '由每位工程师安装一次',
    engineers: ['使用编码代理的', '工程师'],
  },
};
