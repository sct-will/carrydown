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
    items: [
      {
        id: 'spec-driven',
        q: 'Em que isso difere do desenvolvimento orientado por especificações tradicional?',
        a: 'No desenvolvimento orientado por especificações, cada engenheiro escreve a especificação da própria tarefa. A qualidade depende de quem escreveu, não há duas especificações iguais e nada as mantém unidas quando o projeto começa a mudar. Carried-context development começa um nível acima. Seu agente de IA deriva cada especificação da mesma verdade de referência acordada e cita as seções de onde ela veio. O responsável pelo plano revisa as especificações em conjunto antes de publicar qualquer coisa, e uma verificação valida cada citação a partir de um clone limpo. Quando a verdade de referência muda, uma única revisão leva a mudança aprovada a cada especificação, cada issue e cada agente de programação, em vez de cada engenheiro reescrever a sua.',
        more: { label: 'Ver a comparação lado a lado na página de definição.', href: '/definition/#differs' },
      },
      {
        id: 'waterfall',
        q: 'Isso não é só cascata?',
        a: 'Não. A cascata fixa o plano inteiro de antemão e trata uma mudança como falha do plano. Aqui o plano, as especificações e as issues são arquivos no Git, então mudá-los é barato e a mudança é revisada como código. As unidades de trabalho duram o que o trabalho precisa, não caixas de tamanho fixo. Cada marco termina com uma demonstração que as partes interessadas aprovam ou reprovam, e o que a equipe aprende volta para a verdade de referência e se propaga de novo. Você pode planejar, construir um pouco, aprender e atualizar o plano quantas vezes o projeto precisar.',
        more: { label: 'Ler no método como uma mudança se propaga.', href: '/docs/method/#when-the-project-changes' },
      },
      {
        id: 'reconciled',
        q: 'Como o quadro do projeto, as issues, as especificações e o skill dos engenheiros se mantêm reconciliados com a verdade de referência?',
        a: 'Você diz ao seu agente o que mudou. Diga “This changed: …” e descreva a mudança ou entregue os documentos revisados. O agente compara a mudança com as fontes que você revisou por último e com o trabalho atual, encontra as especificações e as issues que a mudança atinge, mantém as correções dos engenheiros que ainda se encaixam e mostra a você uma única revisão das atualizações propostas e de qualquer conflito. Nada se move até você aprovar. A atualização aprovada passa então pela mesma publicação que o plano: atualiza o quadro e as issues que você escolher, não exclui nenhuma delas e regenera o skill dos engenheiros, de modo que cada agente de programação lê a nova especificação na próxima vez que um engenheiro citar um item de trabalho.',
        more: { label: 'Seguir os passos do guia do responsável pelo plano.', href: '/docs/plan-owner-guide/#when-the-project-changes' },
      },
      {
        id: 'certify',
        q: 'Ele certifica que meus documentos estão certos?',
        a: 'Não. A verdade de referência é o que a sua equipe acordou, e o agente a toma como dada. O que ele acrescenta é revisão. Ele renderiza cada documento, ajuda você a revisá-lo com perguntas, e uma segunda revisão confronta o plano pronto com suas fontes, suas restrições e suas escolhas de alocação. Se um documento está errado, o plano está errado do mesmo jeito, e a correção pertence ao documento, não ao plano.',
      },
      {
        id: 'one-person',
        q: 'Serve para um spike de uma pessoa só?',
        a: 'Não muito. O método compensa quando vários engenheiros compartilham semanas de trabalho sob uma arquitetura acordada e especificações que se afastam custam tempo real. Para um spike de uma pessoa só, o plano, as especificações e o quadro são mais estrutura do que o trabalho precisa. Ele é especialmente adequado a equipes corporativas, em que regras de governança, padrões de engenharia e contexto da empresa fazem parte da verdade de referência e várias equipes constroem sobre uma mesma arquitetura. Use-o quando uma equipe entrega trabalho a agentes de programação e precisa que todos partam das mesmas decisões.',
      },
      {
        id: 'governance',
        q: 'Como isso apoia a governança de IA?',
        a: 'Regras de governança, padrões de engenharia e contexto da empresa entram como verdade de referência ao lado dos documentos técnicos, em Word, Markdown, texto simples ou extrações revisadas de arquivos PDF e de imagem. O plano registra a versão e a precedência de cada fonte, cada item de trabalho cita as seções que se aplicam a ele, e as verificações validam essas citações enquanto você redige e de novo em um clone limpo. O skill gerado dos engenheiros aponta cada agente de programação para o contexto aprovado, de modo que o agente lê as regras aplicáveis antes de planejar o código. Você revisa os rascunhos e aprova exatamente o que é compartilhado, com quem e onde, depois de uma prévia e de um ensaio, e o plano, as especificações, as versões das fontes e as decisões registradas ficam no seu repositório. As verificações automáticas e a segunda revisão registram evidências e riscos, e a sua equipe continua a julgar se o trabalho atende aos requisitos da sua organização.',
        more: { label: 'Ler como o carrydown apoia a governança de IA.', href: '/docs/#how-does-carrydown-support-ai-governance' },
      },
      {
        id: 'watch',
        q: 'Ele vigia meus documentos?',
        a: 'Não. O carrydown não tem observador de arquivos e nunca lê seu sistema de documentos por conta própria. Uma atualização começa quando você diz o que mudou e fornece o material revisado, e termina quando você aprova a revisão. A revisão de marco do guia do responsável pelo plano também pergunta se alguma fonte, requisito ou restrição mudou desde o último plano, então uma mudança é percebida ali no mais tardar.',
      },
      {
        id: 'agents',
        q: 'Quais agentes de programação?',
        a: 'Qualquer agente de programação que suporte Agent Skills e possa ler e editar os arquivos do projeto e executar comandos. Seus engenheiros continuam com o que já usam. O skill gerado é uma pasta de instruções que o agente deles carrega, e não contém nenhuma credencial. O guia de configuração lista os agentes suportados e os passos de instalação de cada um.',
        more: { label: 'Escolher um agente de programação no guia de configuração.', href: '/docs/setup/#choose-a-coding-agent' },
      },
      {
        id: 'license',
        q: 'Qual licença?',
        a: 'Apache 2.0, para os skills, os scripts e os modelos. O repositório traz a política de segurança, o histórico de alterações e as respostas às perguntas de segurança comuns das empresas, cada uma marcada como suportada, suportada com pré-requisitos ou planejada.',
        more: { label: 'Abrir o repositório no GitHub.', href: 'https://github.com/sct-will/carrydown' },
      },
    ],
    doesNotHeading: 'O que o carrydown não faz',
    doesNot: [
      'Ele não escreve código de aplicação.',
      'Toda escrita no GitHub é um ensaio até você passar --apply.',
      'Ele nunca apaga issues, rótulos, projetos nem repositórios.',
      'A comparação de atualização roda na sua máquina. Sem rede, sem token, sem chamada a modelo.',
      'Documentos confidenciais ficam na sua máquina, a menos que você diga que todos podem vê-los.',
      'Nomes, folgas e alocação ficam em um arquivo privado, nunca no plano.',
      'Se você parar, fica com Markdown simples e issues comuns do GitHub.',
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
      'Nada no site se move sozinho. Qualquer animação futura respeitará a configuração de movimento reduzido e oferecerá uma imagem estática.',
      'Títulos, regiões e textos de links são escritos para serem lidos em ordem e fora de contexto.',
      'O site é verificado com ferramentas automáticas antes de cada versão e revisado à mão com um leitor de tela.',
    ],
    notFinishedHeading: 'O que não está concluído',
    notFinished:
      'As traduções do site estão sendo revisadas por falantes nativos e entram no ar um idioma por vez. A seção de documentação é gerada a partir do repositório e pode ficar atrás do restante do site nesses pontos até que cada versão seja verificada.',
    contactHeading: 'Conte-nos sobre um problema',
    contactBefore:
      'Se algo neste site for difícil de usar com tecnologia assistiva, ou se você precisar do conteúdo em outra forma, escreva para ',
    contactAfter: '. Diga qual página e o que aconteceu. Você deve receber uma resposta em até dez dias úteis.',
    review:
      'Esta declaração descreve a intenção do site e seu estado atual. Ela é revisada quando o site muda. Última revisão em 16 de novembro de 2026.',
  },

  home: {
    title: 'Carried context, uma verdade de referência para cada agente de programação',
    description:
      'Carried-context development é uma abordagem de desenvolvimento com agentes que leva as decisões e o contexto do projeto até o agente de programação de cada engenheiro, para que o projeto fique alinhado e nada se afaste.',
    h1: [
      'Carried-context development vai além do desenvolvimento orientado por especificações.',
      'O contexto viaja com o trabalho.',
    ],
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
        title: 'Planejado como um todo conectado.',
        body: 'Um único plano e todas as especificações vêm da mesma verdade de referência. Dependências, interfaces e critérios de aceitação são revisados em conjunto para achar lacunas e conflitos, e uma verificação valida cada citação.',
      },
      {
        eyebrow: 'Passagem para a engenharia',
        title: 'Uma passagem que chega ao agente de programação.',
        body: 'Cada issue liga sua especificação e cita suas seções da verdade de referência. Um agent skill específico do projeto coloca a especificação aprovada, essas seções e as suas convenções diante do agente de programação antes que ele planeje o código.',
      },
      {
        eyebrow: 'Contexto do projeto sempre em dia',
        title: 'Mudanças levantadas pelo líder do projeto ou pelos engenheiros se propagam.',
        body: 'Um líder de projeto informa uma fonte alterada, ou um engenheiro aponta uma especificação errada. O agente encontra o trabalho afetado, mantém as correções que ainda servem e traz os conflitos para você. As atualizações aprovadas seguem pelas especificações, issues e pela passagem.',
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
        { title: 'Um plano', path: 'docs/spec/plan.yaml', body: 'Marcos, trilhas, responsáveis e datas ajustados às suas pessoas e ao seu tempo, com uma razão escrita para cada marco.' },
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
