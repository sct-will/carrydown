// Brazilian Portuguese strings. Same shape as en.ts, so the compiler flags a missing key. Brand names,
// the term "Carried-context development" and the quoted agent commands stay in English. A native
// speaker has not reviewed this translation yet, and every translated page says so.
import { en, type Strings } from './en';

export const ptBR: Strings = {
  lang: 'pt-BR',
  dir: 'ltr',
  label: 'Português (Brasil)',

  site: {
    name: 'Carried-context development',
    skipLink: 'Ir para o conteúdo principal',
    homeLabel: 'Carried-context development, início',
  },

  nav: {
    label: 'Principal',
    definition: 'Definição',
    github: 'GitHub',
    docs: 'Docs',
    faq: 'FAQ',
    accessibility: 'Declaração de acessibilidade',
    menu: 'Menu',
    docsMenu: 'Menu dos docs',
  },

  controls: {
    themeLabel: 'Tema',
    themeAuto: 'Auto',
    themeDark: 'Escuro',
    themeLight: 'Claro',
    languageLabel: 'Idioma',
  },

  search: {
    button: 'Buscar',
    title: 'Buscar neste site',
    close: 'Fechar',
    unavailable: 'A busca funciona no site publicado. Ela não está disponível na prévia de desenvolvimento.',
  },

  copyPage: {
    button: 'Copiar página',
    copied: 'Copiado',
    menu: 'Mais formas de usar esta página',
    asMarkdown: 'Copiar a página como Markdown',
    open: 'Abrir o Markdown',
    source: 'Ver a fonte no GitHub',
    ok: 'Página copiada para a área de transferência como Markdown.',
    fail: 'Não foi possível copiar. Abra o Markdown e copie a partir dele.',
  },

  translation: {
    note: 'Esta tradução aguarda revisão de um falante nativo. A página em inglês é a referência.',
    link: 'Ler a página em inglês',
  },

  footer: {
    label: 'Rodapé',
    copyright: en.footer.copyright,
  },

  definition: {
    title: 'Carried-context development, definição',
    description:
      'Carried-context development leva a verdade de referência acordada por uma equipe até o plano, cada especificação, cada issue e as instruções de cada agente de programação, citada por seção, e a leva de novo quando ela muda.',
    h1: 'Carried-context development',
    status: ['Status: método aberto', 'Versão 1.0', 'Novembro de 2026', 'Will Scott, PhD'],
    contents: 'Conteúdo',
    sections: [
      'Definição',
      'As regras',
      'Como difere do desenvolvimento orientado por especificações',
      'Implementação de referência',
      'Como citar',
      'Histórico de alterações',
    ],
    definition:
      'Carried-context development leva a verdade de referência acordada por uma equipe até o plano, cada especificação, cada issue e as instruções de cada agente de programação, citada por seção, e a leva de novo quando ela muda.',
    rules: [
      {
        title: 'Uma única verdade de referência.',
        body: 'Os documentos que a equipe acordou são a única entrada escrita por pessoas. Tudo o que vem depois é derivado deles, e nada posterior prevalece sobre eles.',
      },
      {
        title: 'Ajustado a pessoas e datas reais.',
        body: 'O plano é construído em torno de quem está disponível, de quanto tempo tem e de quando é o prazo. Defina um e o outro é derivado.',
      },
      {
        title: 'Uma especificação por item de trabalho.',
        body: 'Um item de trabalho é a menor parte do trabalho que um engenheiro consegue concluir e demonstrar. Cada um tem sua própria especificação.',
      },
      {
        title: 'Citado por seção.',
        body: 'Cada especificação, issue e instrução nomeia as seções da verdade de referência de onde veio. Uma verificação valida cada citação, a partir de um clone limpo.',
      },
      {
        title: 'Aprovado, não gerado.',
        body: 'Uma pessoa decide responsáveis, datas, escopo e ordem, aprova o que pode ser compartilhado e com quem, e aprova o que é publicado. Nada é postado sem um sim.',
      },
      {
        title: 'Levado até o agente.',
        body: 'O agente de programação do engenheiro lê a especificação e as seções citadas antes de planejar uma linha de código.',
      },
      {
        title: 'Levado de novo a cada mudança.',
        body: 'Quando a verdade de referência muda, uma única revisão encontra o trabalho afetado e mantém as correções dos engenheiros. A atualização aprovada desce até cada parte do trabalho.',
      },
    ],
    differs:
      'O desenvolvimento orientado por especificações deixa cada especificação para o engenheiro que a escreve. A qualidade depende de quem a escreveu. Não há duas especificações iguais e nada as une. Elas se afastam à medida que o projeto muda. Carried-context development deriva cada especificação da mesma verdade de referência, revisa as especificações em conjunto, cita as fontes e leva cada mudança aprovada a cada agente de programação. A engenharia de contexto, uma vizinha, decide o que um modelo vê em uma etapa; o contexto levado decide o que o projeto inteiro deve obedecer.',
    compare: {
      aspect: 'Aspecto',
      specDriven: 'Desenvolvimento orientado por especificações',
      carried: 'Carried-context development',
      rows: [
        ['Unidade de planejamento', 'Uma tarefa ou funcionalidade', 'O projeto inteiro'],
        ['O que viaja', 'A especificação', 'A verdade de referência, citada por seção'],
        [
          'Quando as fontes mudam',
          'Reescrever a especificação',
          'Uma revisão. Correções dos engenheiros mantidas',
        ],
        [
          'Quem escreve a especificação',
          'O engenheiro',
          'Derivada pelo agente de IA a partir da verdade de referência, revisada pelo responsável pelo plano',
        ],
        [
          'Consistência entre especificações',
          'Nenhuma imposta',
          'Revisadas em conjunto, cada citação verificada',
        ],
        ['Quem decide', 'O desenvolvedor', 'O responsável pelo plano, os engenheiros, as partes interessadas'],
      ],
    },
    reference: {
      body: 'carrydown, dois Agent Skills e um terceiro gerado, Apache 2.0, primeiro commit em 24 de outubro de 2026.',
      link: 'github.com/sct-will/carrydown',
    },
    cite: {
      heading: 'Como citar',
      text: en.definition.cite.text,
      bibtex: en.definition.cite.bibtex,
    },
    changelog: '1.0, novembro de 2026. Primeira publicação.',
  },

  faq: {
    title: 'Perguntas, carried-context development',
    description:
      'Respostas sobre carried-context development e carrydown: como difere do desenvolvimento orientado por especificações, por que não é cascata, como o trabalho no GitHub se mantém reconciliado com a verdade de referência e o que o carrydown não faz.',
    h1: 'Perguntas',
    intro: 'Respostas às perguntas mais frequentes, com links para a documentação onde há mais. Cada pergunta tem um link próprio.',
    methodHeading: 'Sobre carried-context development',
    toolHeading: 'Sobre o carrydown',
    anchorLabel: 'Link para esta pergunta',
    items: [
      {
        id: 'what-is-carried-context-development',
        group: 'method',
        q: 'O que é carried-context development?',
        a: 'Carried-context development é uma abordagem de desenvolvimento com agentes que leva as decisões e o contexto do projeto até o agente de programação de cada engenheiro e ajuda a manter especificações e agentes de programação alinhados à medida que o projeto muda. Carried-context development leva a verdade de referência acordada por uma equipe até o plano, cada especificação, cada issue e as instruções de cada agente de programação, citada por seção, e a leva de novo quando ela muda.',
        more: { label: 'Ler a definição e as regras na página de definição.', href: '/definition/' },
      },
      {
        id: 'spec-driven',
        group: 'method',
        q: 'Em que carried-context development difere do desenvolvimento orientado por especificações tradicional?',
        a: 'No desenvolvimento orientado por especificações, cada engenheiro escreve a especificação da própria tarefa. A qualidade depende de quem escreveu, não há duas especificações iguais e nada as mantém unidas quando o projeto começa a mudar. Carried-context development começa um nível acima. Seu agente de IA deriva cada especificação da mesma verdade de referência acordada e cita as seções de onde ela veio. O responsável pelo plano revisa as especificações em conjunto antes de publicar qualquer coisa, e uma verificação valida cada citação a partir de um clone limpo. Quando a verdade de referência muda, uma única revisão leva a mudança aprovada a cada especificação, cada issue e cada agente de programação, em vez de cada engenheiro reescrever a sua.',
        more: { label: 'Ver a comparação lado a lado na página de definição.', href: '/definition/#differs' },
      },
      {
        id: 'rag',
        group: 'method',
        q: 'Em que carried-context development difere da geração aumentada por recuperação?',
        a: 'A geração aumentada por recuperação fornece a um modelo o material que ele encontra no momento da solicitação. Carried-context development registra, durante o planejamento e após uma revisão humana, quais seções de origem aprovadas um trabalho deve seguir, e oferece a você um caminho revisado para alterá-las depois. A recuperação pode fazer parte de uma implementação. Sozinha, ela não define essas decisões do projeto nem a revisão delas.',
      },
      {
        id: 'prompts',
        group: 'method',
        q: 'Não são só prompts?',
        a: 'Não. O verificador é código, e ele faz a integração contínua falhar quando uma especificação quebra as regras. Scripts montam o quadro pela interface de programação de aplicações do GitHub. O plano e as especificações são arquivos no Git que você pode ler, comparar e revisar. Os prompts são a menor parte.',
      },
      {
        id: 'waterfall',
        group: 'method',
        q: 'Carried-context development não é só cascata?',
        a: 'Não. A cascata fixa o plano inteiro de antemão e trata uma mudança como falha do plano. Aqui o plano, as especificações e as issues são arquivos no Git, então mudá-los é barato e a mudança é revisada como código. As unidades de trabalho duram o que o trabalho precisa, não caixas de tamanho fixo. Cada marco termina com uma demonstração que as partes interessadas aprovam ou reprovam, e o que a equipe aprende volta para a verdade de referência e se propaga de novo. Você pode planejar, construir um pouco, aprender e atualizar o plano quantas vezes o projeto precisar.',
        more: { label: 'Ler no método como uma mudança se propaga.', href: '/docs/method/#when-the-project-changes' },
      },
      {
        id: 'what-is-carrydown',
        group: 'carrydown',
        q: 'O que é o carrydown e em que ele difere de carried-context development?',
        a: 'Carried-context development é uma abordagem de desenvolvimento com agentes. Carried-context development leva a verdade de referência acordada por uma equipe até o plano, cada especificação, cada issue e as instruções de cada agente de programação, citada por seção, e a leva de novo quando ela muda. O carrydown é a implementação de referência: dois Agent Skills que você instala juntos com um único comando, um terceiro que ele gera para seus engenheiros e as verificações que validam cada citação. É de código aberto sob Apache 2.0 e funciona com o agente de programação que sua equipe já usa.',
        more: { label: 'Ler na documentação como funciona.', href: '/docs/#how-it-works' },
      },
      {
        id: 'reconciled',
        group: 'carrydown',
        q: 'Como o carrydown mantém o quadro do projeto, as issues, as especificações e o skill dos engenheiros reconciliados com a verdade de referência?',
        a: 'Você diz ao seu agente o que mudou. Diga “This changed: …” e descreva a mudança ou entregue os documentos revisados. O agente compara a mudança com as fontes que você revisou por último e com o trabalho atual, encontra as especificações e as issues que a mudança atinge, mantém as correções dos engenheiros que ainda se encaixam e mostra a você uma única revisão das atualizações propostas e de qualquer conflito. Nada se move até você aprovar. A atualização aprovada passa então pela mesma publicação que o plano: atualiza o quadro e as issues que você escolher, não exclui nenhuma delas e regenera o skill dos engenheiros. Depois que um engenheiro atualiza os arquivos do projeto, a próxima verificação desse item de trabalho informa qualquer mudança nas entradas aprovadas e orienta o agente de programação a reavaliar seu plano. Uma conversa de programação em andamento não se atualiza automaticamente.',
        more: { label: 'Seguir os passos do guia do responsável pelo plano.', href: '/docs/plan-owner-guide/#when-the-project-changes' },
      },
      {
        id: 'certify',
        group: 'carrydown',
        q: 'O carrydown certifica que meus documentos estão certos?',
        a: 'Não. A verdade de referência é o que a sua equipe acordou, e o agente a toma como dada. O que ele acrescenta é revisão. Ele renderiza cada documento, ajuda você a revisá-lo com perguntas, e uma segunda revisão confronta o plano pronto com suas fontes, suas restrições e suas escolhas de alocação. Se um documento está errado, o plano está errado do mesmo jeito, e a correção pertence ao documento, não ao plano.',
      },
      {
        id: 'one-person',
        group: 'method',
        q: 'Carried-context development serve para um spike de uma pessoa só?',
        a: 'Não muito. O método compensa quando vários engenheiros compartilham semanas de trabalho sob uma arquitetura acordada e especificações que se afastam custam tempo real. Para um spike de uma pessoa só, o plano, as especificações e o quadro são mais estrutura do que o trabalho precisa. Ele é especialmente adequado a equipes corporativas, em que regras de governança, padrões de engenharia e contexto da empresa fazem parte da verdade de referência e várias equipes constroem sobre uma mesma arquitetura. Use-o quando uma equipe entrega trabalho a agentes de programação e precisa que todos partam das mesmas decisões.',
      },
      {
        id: 'midway',
        group: 'carrydown',
        q: 'Posso adotar carried-context development com o carrydown no meio de um projeto em andamento?',
        a: 'Hoje não como fluxo de trabalho suportado. O carrydown permite criar novos planos de projeto, incluindo novas fases de bases de código existentes. Ele ainda não oferece um processo de conversão para adotar um quadro do GitHub existente e seu trabalho em andamento.',
      },
      {
        id: 'governance',
        group: 'carrydown',
        q: 'Como o carrydown apoia a governança de IA?',
        a: 'Regras de governança, padrões de engenharia e contexto da empresa entram como verdade de referência ao lado dos documentos técnicos, em Word, Markdown, texto simples ou extrações revisadas de arquivos PDF e de imagem. O plano registra a versão e a precedência de cada fonte, cada item de trabalho cita as seções que se aplicam a ele, e as verificações validam essas citações enquanto você redige e de novo em um clone limpo. O skill gerado dos engenheiros aponta cada agente de programação para o contexto aprovado, de modo que o agente lê as regras aplicáveis antes de planejar o código. Você revisa os rascunhos e aprova exatamente o que é compartilhado, com quem e onde, depois de uma prévia e de um ensaio, e o plano, as especificações, as versões das fontes e as decisões registradas ficam no seu repositório. As verificações automáticas e a segunda revisão registram evidências e riscos, e a sua equipe continua a julgar se o trabalho atende aos requisitos da sua organização.',
        more: { label: 'Ler como o carrydown apoia a governança de IA.', href: '/docs/#how-does-carrydown-support-ai-governance' },
      },
      {
        id: 'withhold',
        group: 'carrydown',
        q: 'Com o carrydown, posso manter certo contexto fora das especificações, do skill dos engenheiros e dos agentes de programação?',
        a: 'Sim. Os engenheiros e seus agentes de programação só veem o contexto aprovado de cada item de trabalho: o texto exato da fonte que o item cita e as decisões por trás dele, que você aprova antes de qualquer publicação. Antes de renderizar ou copiar qualquer coisa, o agente faz uma pergunta: todos que podem ler este repositório podem ver todos esses documentos e suas notas de alocação? Se a resposta for não, ele redige em um espaço de trabalho privado na sua máquina, e o repositório recebe só os resultados que você aprova, nunca um original restrito nem a sua renderização completa. Cada publicação mostra a você uma prévia do que será compartilhado, com quem e onde, e um ensaio antes de escrever qualquer coisa. Nomes, dias de folga e alocação ficam em um arquivo privado e nunca chegam ao plano, a uma especificação ou ao skill. Restam dois limites. Todos que podem ler o repositório podem ler cada contexto aprovado, então uma seção não pode ser mostrada a um engenheiro e escondida de outro, e o trabalho que alguns leitores não devem ver fica fora da publicação como item restrito. E um texto já entregue não pode ser recolhido.',
        more: { label: 'Ler quem pode ver seus documentos, no guia de configuração.', href: '/docs/setup/#before-you-add-documents-who-may-see-them' },
      },
      {
        id: 'watch',
        group: 'carrydown',
        q: 'O carrydown vigia meus documentos?',
        a: 'Não. O carrydown não tem observador de arquivos e nunca lê seu sistema de documentos por conta própria. Uma atualização começa quando você diz o que mudou e fornece o material revisado, e termina quando você aprova a revisão. As revisões de marco também levam o responsável pelo plano a informar mudanças em fontes, requisitos ou restrições.',
      },
      {
        id: 'agents',
        group: 'carrydown',
        q: 'Com quais agentes de programação o carrydown funciona?',
        a: 'Qualquer agente de programação que suporte Agent Skills e possa ler e editar os arquivos do projeto e executar comandos. Seus engenheiros continuam com o que já usam. O skill gerado é uma pasta de instruções que o agente deles carrega, e não contém nenhuma credencial. O guia de configuração lista os agentes suportados e os passos de instalação de cada um.',
        more: { label: 'Escolher um agente de programação no guia de configuração.', href: '/docs/setup/#choose-a-coding-agent' },
      },
      {
        id: 'tracker',
        group: 'carrydown',
        q: 'Posso usar o Jira ou outro gerenciador de tarefas?',
        a: 'Hoje o gerenciador de tarefas é o GitHub. Jira, Azure Boards, GitLab e Linear são convites abertos à comunidade. De qualquer forma, o plano, as especificações e o skill dos engenheiros ficam no seu repositório como arquivos simples.',
        more: { label: 'Ler o convite aberto no GitHub.', href: 'https://github.com/sct-will/carrydown/issues/1' },
      },
      {
        id: 'cost',
        group: 'carrydown',
        q: 'Quanto custa em uso de IA?',
        a: 'Aqui, custo é o uso do modelo pelo seu agente, o texto que o modelo de IA lê e escreve. Ele é separado do token do GitHub. O planejamento lê os documentos e escreve uma especificação por item de trabalho, então o custo cresce com o número de itens. Uma atualização lê o material alterado, um índice compacto de todos os itens de trabalho e as especificações completas dos candidatos que encontra, e reescreve só o que precisa de um ajuste. O agente informa o tamanho desse índice antes de avaliar. Os números são estimativas, e uma mudança ampla de regra ainda pode exigir uma leitura ampla. Quando um engenheiro começa um item de trabalho, o skill gerado carrega uma especificação e as seções citadas, não o documento inteiro. As descrições dos dois skills continuam curtas para caber na lista de cada sessão.',
      },
      {
        id: 'does-not',
        group: 'carrydown',
        q: 'Onde o carrydown para?',
        a: 'O carrydown redige o plano e as especificações, verifica tudo e publica o que você aprova. As decisões ficam com pessoas, e o código da aplicação também.',
        /** The literal text --apply is set in a monospace face wherever it appears. */
        list: [
          'Ele não escreve código de aplicação.',
          'Toda escrita no GitHub é um ensaio até você passar --apply.',
          'Ele nunca apaga issues, rótulos, projetos nem repositórios.',
          'A comparação de atualização roda na sua máquina. Sem rede, sem token, sem chamada a modelo.',
          'Uma atualização verifica o trabalho que consegue observar e relata o que não conseguiu observar. Ela não afirma encontrar todos os itens afetados.',
          'Documentos confidenciais ficam na sua máquina, a menos que você diga que todos podem vê-los.',
          'Nomes, folgas e alocação ficam em um arquivo privado, nunca no plano.',
          'Se você parar, fica com Markdown simples e issues comuns do GitHub.',
        ],
      },
      {
        id: 'license',
        group: 'carrydown',
        q: 'Qual licença o carrydown usa?',
        a: 'Apache 2.0, para os skills, os scripts e os modelos. O repositório traz a política de segurança, o histórico de alterações e as respostas às perguntas de segurança comuns das empresas, cada uma marcada como suportada, suportada com pré-requisitos ou planejada.',
        more: { label: 'Abrir o repositório no GitHub.', href: 'https://github.com/sct-will/carrydown' },
      },
    ],
  },

  accessibility: {
    title: 'Declaração de acessibilidade',
    description:
      'Este site foi feito para ser utilizável por todos. Ele busca atender às Web Content Accessibility Guidelines (WCAG) 2.2 no nível AA.',
    h1: 'Declaração de acessibilidade',
    intro:
      'Este site foi feito para ser utilizável por todos, inclusive por pessoas que usam leitor de tela, apenas o teclado, ampliação ou movimento reduzido. Ele busca atender às Web Content Accessibility Guidelines (WCAG) 2.2 no nível AA.',
    doneHeading: 'O que foi feito',
    done: [
      'As cores do texto e da interface são verificadas quanto ao contraste nos temas claro e escuro, e você pode escolher um deles ou seguir o seu sistema.',
      'Todas as páginas funcionam apenas com o teclado, com indicador de foco visível e um link para pular ao conteúdo principal.',
      'O diagrama é desenhado com texto e formas vetoriais, então ele escala, respeita o seu tema e traz uma descrição escrita para leitores de tela.',
      'As animações, as transições entre páginas e o esmaecimento na troca de tema se desativam quando o seu sistema está configurado para reduzir o movimento. Continuam breves mudanças de cor e de sublinhado em links e botões, e também o giro de uma seta da barra lateral da documentação.',
      'Títulos, regiões e textos de links são escritos para serem lidos em ordem e fora de contexto.',
      'O site é verificado com ferramentas automáticas antes de cada versão e revisado à mão com um leitor de tela.',
    ],
    notFinishedHeading: 'O que não está concluído',
    notFinished:
      'As traduções do site estão sendo revisadas por falantes nativos e entram no ar um idioma por vez. As páginas de documentação ainda não estão traduzidas. Cada idioma mostra a página em inglês com uma nota. Elas são geradas a partir do Markdown do repositório, então seus diagramas e capturas de tela são imagens rasterizadas com descrição escrita e não seguem o tema escuro.',
    contactHeading: 'Conte-nos sobre um problema',
    contactBefore:
      'Se algo neste site for difícil de usar com tecnologia assistiva, ou se você precisar do conteúdo em outra forma, escreva para ',
    contactAfter: '. Diga qual página e o que aconteceu. Você deve receber uma resposta em até dez dias úteis.',
    review:
      'Esta declaração descreve a intenção do site e seu estado atual. Ela é revisada quando o site muda. Última revisão em 22 de novembro de 2026.',
  },

  home: {
    title: 'Carried context, uma verdade de referência para cada agente de programação',
    description:
      'Carried-context development é uma abordagem de desenvolvimento com agentes que leva as decisões e o contexto do projeto até o agente de programação de cada engenheiro e ajuda a manter especificações e agentes de programação alinhados à medida que o projeto muda.',
    h1: [
      'Carried-context development vai além do desenvolvimento orientado por especificações.',
      'O contexto viaja com o trabalho.',
    ],
    /** The part of the second title line set in the amber, a styling choice a native reviewer may move or empty. */
    h1Emphasis: 'viaja com o trabalho.',
    definition:
      'Mantenha o projeto alinhado dando ao agente de programação de cada engenheiro as mesmas decisões e o mesmo contexto do projeto.',
    paragraph:
      'Sua equipe fornece os documentos do projeto, os requisitos e as decisões sobre pessoas e prazos. Seu agente de IA usa essa verdade de referência para criar um plano conectado, uma especificação para cada item de trabalho e issues do GitHub que ligam cada especificação e citam as seções de documentos por trás dela. Seu agente de IA também gera um agent skill específico do projeto que leva a especificação, as decisões por trás do trabalho e as seções citadas até o agente de programação de cada engenheiro. Quando um documento muda, você revisa uma única atualização.',
    buttons: {
      try: 'Comece aqui',
      sample: 'Ver os resultados do agente de IA de um projeto de exemplo',
    },
    /** A small line under the buttons. */
    license: 'Código aberto sob Apache 2.0.',
    howHeading: 'Como funciona',
    /** The last sentence under How it works; the middle word is the link to the README section. */
    learnMore: { before: 'Saiba mais ', link: 'aqui', after: '.' },
    sideParagraphs: [
      'Quando os engenheiros escrevem as especificações por conta própria, a qualidade varia e as especificações se afastam à medida que o projeto muda.',
      'Carried-context development liga cada especificação à mesma verdade de referência, cita as fontes e entrega cada mudança aprovada a cada agente de programação.',
    ],
    values: [
      {
        eyebrow: 'Plano conectado',
        title: 'As decisões do projeto continuam conectadas entre as especificações.',
        body: 'Seu agente monta o plano e as especificações a partir dos mesmos documentos e decisões acordados. Dependências, interfaces compartilhadas e critérios de aceitação são revisados em conjunto para achar lacunas e conflitos. Verificações validam as citações das fontes.',
      },
      {
        eyebrow: 'Passagem para a engenharia',
        title: 'Decisões e fontes chegam a cada agente de programação.',
        body: 'Um skill gerado para o seu projeto orienta o agente de programação de cada engenheiro a ler a especificação aprovada, os trechos citados das fontes e as convenções do projeto antes de planejar o código. Cada issue liga sua especificação, para que os engenheiros também possam inspecionar o contexto.',
      },
      {
        eyebrow: 'Contexto do projeto sempre em dia',
        title: 'Mantenha a passagem alinhada conforme o projeto muda.',
        body: 'Avise o agente com que você planeja quando uma fonte mudar ou uma especificação parecer errada. Ele identifica o trabalho que pode ser afetado e mantém as correções dos engenheiros que ainda servem. Você decide como os conflitos são resolvidos e aprova as atualizações das especificações, das issues e do contexto dos agentes de programação.',
      },
    ],
    carrydown: {
      heading: 'Experimente',
      intro:
        'Carried-context development é uma abordagem de desenvolvimento com agentes, e há mais de uma forma de implementá-la. O carrydown é a implementação de referência: dois Agent Skills que você instala, um terceiro que ele gera para seus engenheiros e as verificações que validam cada citação. É de código aberto sob Apache 2.0 e funciona com o agente de programação que sua equipe já usa.',
      tiles: [
        {
          step: 'Passo 1',
          title: 'Veja um exemplo de plano pronto.',
          body: 'O quadro de exemplo e suas issues, no GitHub.',
          command: '',
          button: 'Abrir o exemplo',
        },
        {
          step: 'Passo 2',
          title: 'Execute o carrydown no seu projeto.',
          body: 'Instale os dois skills do carrydown e então diga',
          command: en.home.carrydown.tiles[1].command,
          button: 'Guia de instalação',
        },
      ],
      stepsHeading: 'Seu agente de IA orienta você ao usar o carrydown no seu projeto',
      steps: [
        {
          who: 'Responsável pelo plano',
          what: 'Instala os dois skills do carrydown e inicia o plano.',
          say: en.home.carrydown.steps[0].say,
        },
        {
          who: 'Responsável pelo plano',
          what: 'Revisa o plano e as especificações e depois publica.',
          say: en.home.carrydown.steps[1].say,
        },
        {
          who: 'Cada engenheiro',
          what: 'Instala uma vez o agent skill gerado e cita um item de trabalho.',
          say: en.home.carrydown.steps[2].say,
        },
        {
          who: 'Partes interessadas',
          what: 'Informam uma fonte alterada ou uma especificação que parece errada. Uma revisão, e a atualização aprovada se propaga.',
          say: en.home.carrydown.steps[3].say,
        },
      ],
      reviewNote: 'Partes interessadas, responsáveis pelo projeto e gerentes de engenharia assistem a cada marco e decidem se passou ou não. A revisão humana é explicitamente parte do método.',
    },
    /** The What you get section: the outputs, summarized from the README's list. */
    whatYouGet: {
      heading: 'O que você recebe',
      intro:
        'Seu agente de IA gera estes itens com os skills do carrydown. Cada item de trabalho pode citar seções de uma ou mais fontes, e as datas e a capacidade são verificadas contra a equipe nomeada.',
      /** The word between a title and the path that follows it, where there is one. */
      inWord: 'em',
      items: [
        { title: 'Um plano que você revisa como uma página no seu navegador web', path: '', body: 'Marcos, trilhas, responsáveis e datas ajustados às suas pessoas e ao seu tempo, com uma tabela de carga e um caminho crítico, e uma razão escrita para cada marco. O plano confirmado no repositório, docs/spec/plan.yaml, contém apenas identificadores e trilhas.' },
        { title: 'Uma especificação por item de trabalho', path: '', body: 'A menor parte do trabalho que um engenheiro consegue terminar e mostrar, citando suas seções e verificada contra o plano a cada pull request.' },
        { title: 'Um contexto aprovado por item de trabalho', path: 'docs/context/', body: 'O texto exato das seções que o item cita e as decisões por trás dele, aprovados por você. A única parte dos seus documentos que chega aos agentes dos engenheiros.' },
        { title: 'Um recibo de release', path: 'docs/release/', body: 'Um pequeno arquivo público que nomeia o release aprovado, seu estado e sua validade.' },
        { title: 'Um relatório de segunda revisão', path: '', body: 'Cobertura, evidências, raciocínio e risco, com suas decisões e as verificações dos reparos aceitos.' },
        { title: 'Issues do GitHub', path: '', body: 'Uma por item de trabalho sob um sub-épico por marco, cada uma dizendo ao agente do engenheiro o que ler.' },
        { title: 'Um quadro do GitHub Projects', path: '', body: 'Unidades de trabalho, trilhas, datas e pontos de verificação preenchidos.' },
        { title: 'O skill de agente de IA do engenheiro', path: '', body: 'Gerado a partir das suas especificações e commitado no seu repositório. Um engenheiro começa um item de trabalho nomeando-o, por exemplo “Work on [work item ID]”, e o agente de programação lê primeiro a especificação e o contexto aprovado desse item.' },
      ],
    },
  },

  diagram: {
    ariaLabel:
      'O contexto de projeto que você fornece, documentos, decisões e mais tarde uma mudança, alimenta o agente de IA. Ele gera para sua equipe um plano de projeto para revisão e aprovação, uma especificação para cada item de trabalho, um quadro do GitHub com issues e marcos em que cada issue liga sua especificação e cita suas fontes, e um agent skill específico do projeto que cada engenheiro instala uma vez e usa com um agente de programação.',
    provideHeading: 'Contexto que você fornece',
    generatesHeading: 'O agente de IA gera para a equipe',
    documents: 'Documentos',
    documentsNote: 'arquitetura, requisitos, regras',
    decisions: 'Decisões',
    decisionsNote: 'pessoas, alocação, prazos',
    later: 'Depois',
    changed: 'Algo mudou',
    changedNote: 'documento alterado ou spec errada',
    agent: 'Agente de IA',
    agentVerbs: ['lê, planeja, cita,', 'passa, reconcilia'],
    plans: 'Planeja',
    plansTitle: 'Plano para revisão e aprovação',
    plansNote: 'marcos, trilhas, datas ajustadas à equipe',
    writes: 'Escreve',
    writesTitle: 'Uma especificação por item',
    writesNote: 'todas da mesma verdade de referência',
    opens: 'Abre',
    opensTitle: 'Quadro do GitHub com issues e marcos',
    opensNote: 'cada issue liga especificação e fontes',
    generates: 'Gera',
    generatesTitle: 'Agent skill do projeto',
    generatesNote: 'instalado uma vez por cada engenheiro',
    engineers: ['Engenheiros com', 'agentes de código'],
  },
};
