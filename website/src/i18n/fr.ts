// French strings. Same shape as en.ts, so the compiler flags a missing key. Brand names, the term
// "Carried-context development" and the quoted agent commands stay in English. A native speaker has
// not reviewed this translation yet, and every translated page says so.
import { en, type Strings } from './en';

export const fr: Strings = {
  lang: 'fr',
  dir: 'ltr',
  label: 'Français',

  site: {
    name: 'Carried-context development',
    skipLink: 'Aller au contenu principal',
    homeLabel: 'Carried-context development, accueil',
  },

  nav: {
    label: 'Principale',
    definition: 'Définition',
    github: 'GitHub',
    docs: 'Docs',
    faq: 'FAQ',
    accessibility: 'Déclaration d’accessibilité',
    menu: 'Menu',
    docsMenu: 'Menu des docs',
  },

  controls: {
    themeLabel: 'Thème',
    themeAuto: 'Auto',
    themeDark: 'Sombre',
    themeLight: 'Clair',
    languageLabel: 'Langue',
  },

  search: {
    button: 'Rechercher',
    title: 'Rechercher sur ce site',
    close: 'Fermer',
    unavailable: 'La recherche fonctionne sur le site publié. Elle n’est pas disponible dans l’aperçu de développement.',
  },

  copyPage: {
    button: 'Copier la page',
    copied: 'Copié',
    menu: 'Autres façons d’utiliser cette page',
    asMarkdown: 'Copier la page en Markdown',
    open: 'Ouvrir le Markdown',
    source: 'Voir la source sur GitHub',
    ok: 'Page copiée dans le presse-papiers en Markdown.',
    fail: 'Copie impossible. Ouvrez le Markdown et copiez-le depuis là.',
  },

  translation: {
    note: 'Cette traduction est en attente de relecture par un locuteur natif. La page en anglais fait foi.',
    link: 'Lire la page en anglais',
  },

  footer: {
    label: 'Pied de page',
    copyright: en.footer.copyright,
  },

  definition: {
    title: 'Carried-context development, définition',
    description:
      'Carried-context development fait descendre la vérité de référence convenue par une équipe jusque dans le plan, chaque spécification, chaque ticket et les instructions de chaque agent de codage, avec citation par section, et la fait descendre à nouveau quand elle change.',
    h1: 'Carried-context development',
    status: ['Statut : méthode ouverte', 'Version 1.0', 'Novembre 2026', 'Will Scott, PhD'],
    contents: 'Sommaire',
    sections: [
      'Définition',
      'Les règles',
      'En quoi elle diffère du développement piloté par les spécifications',
      'Implémentation de référence',
      'Comment citer',
      'Journal des modifications',
    ],
    definition:
      'Carried-context development fait descendre la vérité de référence convenue par une équipe jusque dans le plan, chaque spécification, chaque ticket et les instructions de chaque agent de codage, avec citation par section, et la fait descendre à nouveau quand elle change.',
    rules: [
      {
        title: 'Une seule vérité de référence.',
        body: 'Les documents que l’équipe a validés sont la seule entrée rédigée par des humains. Tout ce qui en découle en est dérivé, et rien en aval ne prime sur eux.',
      },
      {
        title: 'Ajusté aux personnes et aux dates réelles.',
        body: 'Le plan est bâti autour de qui est disponible, de combien de temps, et de l’échéance. Fixez l’un et l’autre se déduit.',
      },
      {
        title: 'Une spécification par élément de travail.',
        body: 'Un élément de travail est le plus petit morceau de travail qu’un ingénieur peut terminer et montrer. Chacun a sa propre spécification.',
      },
      {
        title: 'Cité par section.',
        body: 'Chaque spécification, ticket et instruction nomme les sections de la vérité de référence dont il provient. Un contrôle valide chaque citation, depuis un clone propre.',
      },
      {
        title: 'Approuvé, pas généré.',
        body: 'Une personne décide des responsables, des dates, du périmètre et de l’ordre, approuve ce qui peut être partagé et avec qui, et approuve ce qui est publié. Rien n’est publié sans un oui.',
      },
      {
        title: 'Porté jusqu’à l’agent.',
        body: 'L’agent de codage de l’ingénieur lit la spécification et les sections citées avant de planifier une ligne de code.',
      },
      {
        title: 'Porté à nouveau en cas de changement.',
        body: 'Quand la vérité de référence change, une seule revue trouve le travail concerné et conserve les corrections des ingénieurs. La mise à jour approuvée descend jusqu’à chaque élément de travail.',
      },
    ],
    differs:
      'Le développement piloté par les spécifications laisse chaque spécification à l’ingénieur qui l’écrit. La qualité dépend de son auteur. Deux spécifications ne se ressemblent pas et rien ne les relie. Elles dérivent au fil des changements du projet. Carried-context development dérive chaque spécification de la même vérité de référence, les revoit ensemble, cite les sources et porte chaque changement approuvé à chaque agent de codage. L’ingénierie de contexte, une voisine, décide de ce qu’un modèle voit en une étape ; le contexte porté décide de ce que le projet entier doit respecter.',
    compare: {
      aspect: 'Critère',
      specDriven: 'Développement piloté par les spécifications',
      carried: 'Carried-context development',
      rows: [
        ['Unité de planification', 'Une tâche ou une fonctionnalité', 'Le projet entier'],
        ['Ce qui circule', 'La spécification', 'La vérité de référence, citée par section'],
        [
          'Quand les sources changent',
          'Réécrire la spécification',
          'Une revue. Corrections des ingénieurs conservées',
        ],
        [
          'Qui écrit la spécification',
          'L’ingénieur',
          'Dérivée par l’agent d’IA de la vérité de référence, relue par le responsable du plan',
        ],
        [
          'Cohérence entre les spécifications',
          'Aucune imposée',
          'Revues ensemble, chaque citation vérifiée',
        ],
        ['Qui décide', 'Le développeur', 'Le responsable du plan, les ingénieurs, les parties prenantes'],
      ],
    },
    reference: {
      body: 'carrydown, deux Agent Skills et un troisième généré, Apache 2.0, premier commit le 24 octobre 2026.',
      link: 'github.com/sct-will/carrydown',
    },
    cite: {
      heading: 'Comment citer',
      text: en.definition.cite.text,
      bibtex: en.definition.cite.bibtex,
    },
    changelog: '1.0, novembre 2026. Première publication.',
  },

  faq: {
    title: 'Questions, carried-context development',
    description:
      'Des réponses sur carried-context development et carrydown : la différence avec le développement piloté par les spécifications, pourquoi ce n’est pas un modèle en cascade, comment le travail sur GitHub reste aligné sur la vérité de référence, et ce que carrydown ne fait pas.',
    h1: 'Questions',
    intro: 'Des réponses aux questions les plus fréquentes, avec des liens vers les docs quand il y a plus à lire. Chaque question a son propre lien.',
    methodHeading: 'À propos de carried-context development',
    toolHeading: 'À propos de carrydown',
    anchorLabel: 'Lien vers cette question',
    items: [
      {
        id: 'what-is-carried-context-development',
        group: 'method',
        q: 'Qu’est-ce que carried-context development ?',
        a: 'Carried-context development est une approche du développement agentique qui fait descendre les décisions et le contexte du projet jusqu’à l’agent de codage de chaque ingénieur, pour que le projet reste aligné et que rien ne dérive. Carried-context development fait descendre la vérité de référence convenue par une équipe jusque dans le plan, chaque spécification, chaque ticket et les instructions de chaque agent de codage, avec citation par section, et la fait descendre à nouveau quand elle change.',
        more: { label: 'Lire la définition et les règles sur la page de définition.', href: '/definition/' },
      },
      {
        id: 'spec-driven',
        group: 'method',
        q: 'En quoi carried-context development diffère-t-il du développement piloté par les spécifications classique ?',
        a: 'Dans le développement piloté par les spécifications, chaque ingénieur écrit la spécification de sa propre tâche. La qualité dépend de qui l’a écrite, aucune spécification ne ressemble à une autre, et rien ne les relie dès que le projet change. Carried-context development part d’un niveau plus haut. Votre agent d’IA dérive chaque spécification de la même vérité de référence convenue et cite les sections dont elle vient. Le responsable du plan relit les spécifications ensemble avant toute publication, et une vérification valide chaque citation depuis un clone propre. Quand la vérité de référence change, une seule revue porte le changement approuvé dans chaque spécification, chaque ticket et chaque agent de codage, au lieu que chaque ingénieur réécrive la sienne.',
        more: { label: 'Voir la comparaison côte à côte sur la page de définition.', href: '/definition/#differs' },
      },
      {
        id: 'rag',
        group: 'method',
        q: 'En quoi carried-context development diffère-t-il de la génération augmentée par récupération ?',
        a: 'La génération augmentée par récupération fournit à un modèle des éléments qu’il trouve au moment de la demande. Carried-context development consigne, pendant la planification et après une revue humaine, les sections sources approuvées qu’un travail doit suivre, et vous donne un chemin relu pour les modifier ensuite. La récupération peut faire partie d’une implémentation. Elle ne définit pas à elle seule ces décisions de projet ni leur revue.',
      },
      {
        id: 'prompts',
        group: 'method',
        q: 'N’est-ce que des prompts ?',
        a: 'Non. Le vérificateur est du code, et il fait échouer l’intégration continue quand une spécification enfreint les règles. Des scripts construisent le tableau via l’interface de programmation de GitHub. Le plan et les spécifications sont des fichiers dans Git que vous pouvez lire, comparer et relire. Les prompts en sont la plus petite partie.',
      },
      {
        id: 'waterfall',
        group: 'method',
        q: 'Carried-context development, n’est-ce pas simplement un modèle en cascade ?',
        a: 'Non. Le modèle en cascade fige tout le plan au départ et traite un changement comme un échec du plan. Ici, le plan, les spécifications et les tickets sont des fichiers dans Git. Les changer coûte peu et le changement est relu comme du code. Les unités de travail durent le temps que demande le travail, pas des cases de longueur fixe. Chaque jalon se termine par une démonstration que les parties prenantes valident ou refusent, et ce que l’équipe apprend retourne dans la vérité de référence puis redescend. Vous pouvez planifier, construire un peu, apprendre et mettre le plan à jour aussi souvent que le projet le demande.',
        more: { label: 'Lire dans la méthode comment un changement redescend.', href: '/docs/method/#when-the-project-changes' },
      },
      {
        id: 'what-is-carrydown',
        group: 'carrydown',
        q: 'Qu’est-ce que carrydown, et en quoi diffère-t-il de carried-context development ?',
        a: 'Carried-context development est une approche du développement agentique. Carried-context development fait descendre la vérité de référence convenue par une équipe jusque dans le plan, chaque spécification, chaque ticket et les instructions de chaque agent de codage, avec citation par section, et la fait descendre à nouveau quand elle change. carrydown en est l’implémentation de référence : deux Agent Skills que vous installez ensemble avec une seule commande, un troisième qu’elle génère pour vos ingénieurs, et les contrôles qui valident chaque citation. Elle est open source sous Apache 2.0 et fonctionne avec l’agent de codage que votre équipe utilise déjà.',
        more: { label: 'Lire dans les docs comment cela fonctionne.', href: '/docs/#how-it-works' },
      },
      {
        id: 'reconciled',
        group: 'carrydown',
        q: 'Comment carrydown garde-t-il le tableau de projet, les tickets, les spécifications et le skill des ingénieurs alignés sur la vérité de référence ?',
        a: 'Vous dites à votre agent ce qui a changé. Dites « This changed: … » et décrivez le changement ou remettez les documents révisés. L’agent compare le changement avec les sources que vous avez relues en dernier et avec le travail en cours, trouve les spécifications et les tickets que le changement touche, garde les corrections des ingénieurs qui tiennent encore, et vous montre une seule revue des mises à jour proposées et des conflits éventuels. Rien ne bouge avant votre approbation. La mise à jour approuvée passe ensuite par la même publication que le plan : elle met à jour le tableau et les tickets que vous choisissez, n’en supprime aucun et régénère le skill des ingénieurs, si bien que chaque agent de codage lit la nouvelle spécification la prochaine fois qu’un ingénieur nomme un élément de travail.',
        more: { label: 'Suivre les étapes du guide du responsable du plan.', href: '/docs/plan-owner-guide/#when-the-project-changes' },
      },
      {
        id: 'certify',
        group: 'carrydown',
        q: 'carrydown certifie-t-il que mes documents sont justes ?',
        a: 'Non. La vérité de référence est ce que votre équipe a convenu, et l’agent la prend telle quelle. Ce qu’il ajoute, c’est la relecture. Il rend chaque document, vous aide à le relire avec des questions, et une seconde passe confronte le plan terminé à ses sources, à ses contraintes et à ses choix d’affectation. Si un document est faux, le plan est faux de la même façon, et la correction va dans le document, pas dans le plan.',
      },
      {
        id: 'one-person',
        group: 'method',
        q: 'Carried-context development est-il fait pour un spike d’une seule personne ?',
        a: 'Pas vraiment. La méthode paie quand plusieurs ingénieurs partagent des semaines de travail sur une architecture convenue et que des spécifications qui divergent coûtent du vrai temps. Pour un spike d’une seule personne, le plan, les spécifications et le tableau sont plus de structure que le travail n’en demande. Elle convient particulièrement bien aux équipes d’entreprise, où les règles de gouvernance, les normes d’ingénierie et le contexte de l’entreprise font partie de la vérité de référence et où plusieurs équipes construisent sur une même architecture. Utilisez-la quand une équipe confie du travail à des agents de codage et a besoin que chacun parte des mêmes décisions.',
      },
      {
        id: 'midway',
        group: 'carrydown',
        q: 'Puis-je adopter carried-context development avec carrydown au milieu d’un projet en cours ?',
        a: 'Pas comme flux de travail pris en charge aujourd’hui. carrydown permet de créer de nouveaux plans de projet, y compris pour de nouvelles phases de bases de code existantes. Il ne fournit pas encore de processus de conversion pour reprendre un tableau GitHub existant et son travail en cours.',
      },
      {
        id: 'governance',
        group: 'carrydown',
        q: 'Comment carrydown soutient-il la gouvernance de l’IA ?',
        a: 'Les règles de gouvernance, les normes d’ingénierie et le contexte de l’entreprise entrent comme vérité de référence à côté des documents techniques, en Word, Markdown, texte brut ou extractions relues de fichiers PDF et d’images. Le plan enregistre la version et la préséance de chaque source, chaque élément de travail cite les sections qui s’appliquent à lui, et les vérifications valident ces citations pendant la rédaction puis à nouveau depuis un clone propre. Le skill généré des ingénieurs pointe chaque agent de codage vers le contexte approuvé, si bien que l’agent lit les règles applicables avant de planifier le code. Vous relisez les brouillons et approuvez exactement ce qui est partagé, avec qui et où, après un aperçu et une simulation, et le plan, les spécifications, les versions des sources et les décisions enregistrées restent dans votre dépôt. Les vérifications automatiques et la seconde passe consignent les preuves et les risques, et votre équipe reste juge de la conformité du travail aux exigences de votre organisation.',
        more: { label: 'Lire comment carrydown soutient la gouvernance de l’IA.', href: '/docs/#how-does-carrydown-support-ai-governance' },
      },
      {
        id: 'withhold',
        group: 'carrydown',
        q: 'Avec carrydown, puis-je garder certains éléments de contexte hors des spécifications, du skill des ingénieurs et des agents de codage ?',
        a: 'Oui. Les ingénieurs et leurs agents de codage ne voient jamais que le contexte approuvé de chaque élément de travail : le texte source exact que l’élément cite et les décisions qui le sous-tendent, que vous approuvez avant toute publication. Avant de rendre ou de copier quoi que ce soit, l’agent pose une question : tous ceux qui peuvent lire ce dépôt peuvent-ils voir tous ces documents et vos notes d’affectation ? Sur un non, il rédige dans un espace de travail privé sur votre machine, et le dépôt ne reçoit que les résultats que vous approuvez, jamais un original restreint ni son rendu complet. Chaque publication vous montre un aperçu de ce qui sera partagé, avec qui et où, et une simulation avant toute écriture. Les noms, les jours d’absence et l’allocation restent dans un fichier privé et n’atteignent jamais le plan, une spécification ou le skill. Deux limites demeurent. Tous ceux qui peuvent lire le dépôt peuvent lire chaque contexte approuvé, une section ne peut donc pas être montrée à un ingénieur et cachée à un autre, et le travail que certains lecteurs ne doivent pas voir reste hors de la publication comme élément restreint. Et un texte déjà livré ne peut pas être rappelé.',
        more: { label: 'Lire qui peut voir vos documents, dans le guide d’installation.', href: '/docs/setup/#before-you-add-documents-who-may-see-them' },
      },
      {
        id: 'watch',
        group: 'carrydown',
        q: 'carrydown surveille-t-il mes documents ?',
        a: 'Non. carrydown n’a aucun observateur de fichiers et ne lit jamais votre système documentaire de lui-même. Une mise à jour commence quand vous dites ce qui a changé et fournissez le matériel révisé, et elle se termine quand vous approuvez la revue. La revue de jalon du guide du responsable du plan demande aussi si une source, une exigence ou une contrainte a changé depuis le dernier plan, si bien qu’un changement est repéré là au plus tard.',
      },
      {
        id: 'agents',
        group: 'carrydown',
        q: 'Avec quels agents de codage carrydown fonctionne-t-il ?',
        a: 'Tout agent de codage qui prend en charge les Agent Skills et peut lire et modifier les fichiers du projet et exécuter des commandes. Vos ingénieurs gardent celui qu’ils utilisent déjà. Le skill généré est un dossier d’instructions que leur agent charge, et il ne contient aucun identifiant. Le guide d’installation liste les agents pris en charge et les étapes d’installation de chacun.',
        more: { label: 'Choisir un agent de codage dans le guide d’installation.', href: '/docs/setup/#choose-a-coding-agent' },
      },
      {
        id: 'tracker',
        group: 'carrydown',
        q: 'Puis-je utiliser Jira ou un autre outil de suivi ?',
        a: 'Aujourd’hui, l’outil de suivi est GitHub. Jira, Azure Boards, GitLab et Linear sont des invitations ouvertes à la communauté. Dans tous les cas, le plan, les spécifications et le skill des ingénieurs vivent dans votre dépôt sous forme de fichiers simples.',
        more: { label: 'Lire l’invitation ouverte sur GitHub.', href: 'https://github.com/sct-will/carrydown/issues/1' },
      },
      {
        id: 'cost',
        group: 'carrydown',
        q: 'Combien cela coûte-t-il en usage d’IA ?',
        a: 'Le coût désigne ici l’usage du modèle par votre agent, c’est-à-dire le texte que le modèle d’IA lit et écrit. Il est distinct du jeton GitHub. La planification lit les documents et écrit une spécification par élément de travail, donc son coût croît avec le nombre d’éléments. Une mise à jour lit le contenu modifié, un index compact de tous les éléments de travail et les spécifications complètes des candidats qu’elle trouve, et ne réécrit que ce qui demande un correctif. L’agent indique la taille de cet index avant d’évaluer. Les chiffres sont des estimations, et un changement de règle étendu peut encore demander une lecture étendue. Quand un ingénieur commence un élément de travail, le skill généré charge une spécification et les sections citées, pas tout le document. Les descriptions des deux skills restent courtes pour tenir dans la liste de chaque session.',
      },
      {
        id: 'does-not',
        group: 'carrydown',
        q: 'Où s’arrête carrydown ?',
        a: 'carrydown rédige le plan et les spécifications, les vérifie et publie ce que vous approuvez. Les décisions restent aux personnes, et le code applicatif aussi.',
        /** The literal text --apply is set in a monospace face wherever it appears. */
        list: [
          'Il n’écrit aucun code d’application.',
          'Chaque écriture sur GitHub est un essai à blanc tant que vous ne passez pas --apply.',
          'Il ne supprime jamais de tickets, d’étiquettes, de projets ni de dépôts.',
          'La comparaison de mise à jour s’exécute sur votre machine. Pas de réseau, pas de jeton, pas d’appel à un modèle.',
          'Une mise à jour vérifie le travail qu’elle peut observer et signale ce qu’elle n’a pas pu observer. Elle ne prétend pas trouver chaque élément concerné.',
          'Les documents confidentiels restent sur votre machine, sauf si vous dites que tout le monde peut les voir.',
          'Les noms, les jours d’absence et l’affectation restent dans un fichier privé, jamais dans le plan.',
          'Si vous arrêtez, vous gardez du Markdown brut et de simples tickets GitHub.',
        ],
      },
      {
        id: 'license',
        group: 'carrydown',
        q: 'Sous quelle licence carrydown est-il publié ?',
        a: 'Apache 2.0, pour les skills, les scripts et les modèles. Le dépôt porte la politique de sécurité, le journal des modifications et les réponses aux questions de sécurité courantes des entreprises, chacune étiquetée prise en charge, prise en charge avec prérequis ou prévue.',
        more: { label: 'Ouvrir le dépôt sur GitHub.', href: 'https://github.com/sct-will/carrydown' },
      },
    ],
  },

  accessibility: {
    title: 'Déclaration d’accessibilité',
    description:
      'Ce site est conçu pour être utilisable par tous. Il vise la conformité aux Web Content Accessibility Guidelines (WCAG) 2.2 au niveau AA.',
    h1: 'Déclaration d’accessibilité',
    intro:
      'Ce site est conçu pour être utilisable par tous, y compris par les personnes qui utilisent un lecteur d’écran, le clavier seul, l’agrandissement ou la réduction des animations. Il vise la conformité aux Web Content Accessibility Guidelines (WCAG) 2.2 au niveau AA.',
    doneHeading: 'Ce qui a été fait',
    done: [
      'Les couleurs du texte et de l’interface sont vérifiées pour le contraste dans les thèmes clair et sombre, et vous pouvez choisir l’un ou l’autre ou suivre votre système.',
      'Chaque page fonctionne au clavier seul, avec un indicateur de focus visible et un lien d’évitement vers le contenu principal.',
      'Le schéma est dessiné avec du texte et des formes vectorielles. Il s’adapte à la taille, respecte votre thème et porte une description écrite pour les lecteurs d’écran.',
      'Rien sur le site ne bouge de lui-même. Toute animation future respectera le réglage de réduction des animations et proposera une image fixe.',
      'Les titres, les repères et les textes de liens sont écrits pour être lus dans l’ordre et hors contexte.',
      'Le site est vérifié avec des outils automatiques avant chaque version et relu à la main avec un lecteur d’écran.',
    ],
    notFinishedHeading: 'Ce qui n’est pas terminé',
    notFinished:
      'Les traductions du site sont relues par des locuteurs natifs et sont mises en ligne une langue à la fois. La section de documentation est générée à partir du dépôt et peut avoir du retard sur le reste du site sur ces points, jusqu’à la vérification de chaque version.',
    contactHeading: 'Signalez-nous un problème',
    contactBefore:
      'Si quelque chose sur ce site est difficile à utiliser avec une technologie d’assistance, ou si vous avez besoin du contenu sous une autre forme, écrivez à ',
    contactAfter: '. Indiquez la page et ce qui s’est passé. Vous devriez recevoir une réponse sous dix jours ouvrés.',
    review:
      'Cette déclaration décrit l’intention du site et son état actuel. Elle est revue quand le site change. Dernière revue le 16 novembre 2026.',
  },

  home: {
    title: 'Carried context, une vérité de référence pour chaque agent de codage',
    description:
      'Carried-context development est une approche du développement agentique qui fait descendre les décisions et le contexte du projet jusqu’à l’agent de codage de chaque ingénieur, pour que le projet reste aligné et que rien ne dérive.',
    h1: [
      'Carried-context development va plus loin que le développement piloté par les spécifications.',
      'Le contexte voyage avec le travail.',
    ],
    /** The part of the second title line set in the amber, a styling choice a native reviewer may move or empty. */
    h1Emphasis: 'voyage avec le travail.',
    definition:
      'Gardez le projet aligné en donnant à l’agent de codage de chaque ingénieur les mêmes décisions et le même contexte de projet.',
    paragraph:
      'Votre équipe fournit les documents du projet, les exigences et les décisions sur les personnes et les échéances. Votre agent d’IA s’appuie sur cette vérité de référence pour créer un plan connecté, une spécification pour chaque élément de travail et des tickets GitHub qui lient chaque spécification et citent les sections de documents sur lesquelles elle repose. Votre agent d’IA génère aussi un agent skill propre au projet, qui porte la spécification, les décisions qui la fondent et les sections citées jusqu’à l’agent de codage de chaque ingénieur. Quand un document change, vous relisez une seule mise à jour.',
    buttons: {
      try: 'Commencer ici',
      sample: 'Voir les productions de l’agent d’IA d’un projet exemple',
    },
    /** A small line under the buttons. */
    license: 'Open source sous licence Apache 2.0.',
    howHeading: 'Comment ça marche',
    /** The last sentence under How it works; the middle word is the link to the README section. */
    learnMore: { before: 'En savoir plus ', link: 'ici', after: '.' },
    sideParagraphs: [
      'Quand les ingénieurs écrivent leurs spécifications chacun de leur côté, la qualité varie et les spécifications dérivent à mesure que le projet change.',
      'Carried-context development rattache chaque spécification à la même vérité de référence, cite les sources et fait descendre chaque changement approuvé jusqu’à chaque agent de codage.',
    ],
    values: [
      {
        eyebrow: 'Plan connecté',
        title: 'Les décisions du projet restent liées d’une spécification à l’autre.',
        body: 'Votre agent construit le plan et les spécifications à partir des mêmes documents et décisions convenus. Les dépendances, les interfaces partagées et les critères d’acceptation sont revus ensemble pour repérer lacunes et conflits. Des contrôles valident les citations des sources.',
      },
      {
        eyebrow: 'Passation à l’ingénierie',
        title: 'Les décisions et les sources atteignent chaque agent de codage.',
        body: 'Un skill généré pour votre projet indique à l’agent de codage de chaque ingénieur de lire la spécification approuvée, les extraits de sources cités et les conventions du projet avant de planifier le code. Chaque ticket renvoie à sa spécification, pour que les ingénieurs puissent eux aussi examiner le contexte.',
      },
      {
        eyebrow: 'Contexte du projet tenu à jour',
        title: 'Gardez la passation alignée à mesure que le projet évolue.',
        body: 'Prévenez l’agent avec lequel vous planifiez quand une source change ou qu’une spécification semble erronée. Il repère le travail susceptible d’être concerné et garde les corrections des ingénieurs qui tiennent encore. Vous décidez de la résolution des conflits et approuvez les mises à jour des spécifications, des tickets et du contexte des agents de codage.',
      },
    ],
    carrydown: {
      heading: 'Essayez-le',
      intro:
        'Carried-context development est une approche du développement agentique, et il y a plus d’une façon de la mettre en œuvre. carrydown en est l’implémentation de référence : deux Agent Skills que vous installez, un troisième qu’elle génère pour vos ingénieurs, et les contrôles qui valident chaque citation. Elle est open source sous Apache 2.0 et fonctionne avec l’agent de codage que votre équipe utilise déjà.',
      tiles: [
        {
          step: 'Étape 1',
          title: 'Regarder un exemple de plan terminé.',
          body: 'Le tableau exemple et ses tickets, sur GitHub.',
          command: '',
          button: 'Ouvrir l’exemple',
        },
        {
          step: 'Étape 2',
          title: 'Lancer carrydown sur votre projet.',
          body: 'Installez les deux skills carrydown, puis dites',
          command: en.home.carrydown.tiles[1].command,
          button: 'Guide d’installation',
        },
      ],
      stepsHeading: 'Votre agent d’IA vous guide pour utiliser carrydown sur votre projet',
      steps: [
        {
          who: 'Responsable du plan',
          what: 'Installe les deux skills carrydown et lance le plan.',
          say: en.home.carrydown.steps[0].say,
        },
        {
          who: 'Responsable du plan',
          what: 'Relit le plan et les spécifications, puis publie.',
          say: en.home.carrydown.steps[1].say,
        },
        {
          who: 'Chaque ingénieur',
          what: 'Installe une fois l’agent skill généré et nomme un élément de travail.',
          say: en.home.carrydown.steps[2].say,
        },
        {
          who: 'Parties prenantes',
          what: 'Signalent une source modifiée ou une spécification qui semble erronée. Une revue, puis la mise à jour approuvée descend.',
          say: en.home.carrydown.steps[3].say,
        },
      ],
      reviewNote: 'Les parties prenantes, les responsables de projet et les responsables d’ingénierie assistent à chaque jalon et décident de la réussite ou de l’échec. La revue humaine fait explicitement partie de la méthode.',
    },
    /** The What you get section: the outputs, summarized from the README's list. */
    whatYouGet: {
      heading: 'Ce que vous obtenez',
      intro:
        'Votre agent d’IA produit ces éléments avec les skills carrydown. Chaque élément de travail peut citer des sections d’une ou plusieurs sources, et les dates et la capacité sont vérifiées par rapport à l’équipe nommée.',
      /** The word between a title and the path that follows it, where there is one. */
      inWord: 'dans',
      items: [
        { title: 'Un plan que vous relisez comme une page dans votre navigateur web', path: '', body: 'Jalons, pistes, responsables et dates ajustés à vos personnes et à votre temps, avec un tableau de charge et un chemin critique, et une raison écrite pour chaque jalon. Le plan validé dans le dépôt, docs/spec/plan.yaml, ne contient que les identifiants et les pistes.' },
        { title: 'Une spécification par élément de travail', path: '', body: 'La plus petite unité de travail qu’un ingénieur peut terminer et montrer, citant ses sections et vérifiée par rapport au plan à chaque pull request.' },
        { title: 'Un contexte approuvé par élément de travail', path: 'docs/context/', body: 'Le texte exact des sections citées et les décisions qui le fondent, approuvés par vous. La seule partie de vos documents qui atteint les agents des ingénieurs.' },
        { title: 'Un reçu de publication', path: 'docs/release/', body: 'Un petit fichier public qui nomme la publication approuvée, son état et son expiration.' },
        { title: 'Un rapport de seconde revue', path: '', body: 'Couverture, preuves, raisonnement et risque, avec vos décisions et les contrôles des corrections acceptées.' },
        { title: 'Des tickets GitHub', path: '', body: 'Un par élément de travail sous une sous-épopée par jalon, chacun disant à l’agent de l’ingénieur quoi lire.' },
        { title: 'Un tableau GitHub Projects', path: '', body: 'Unités de travail, pistes, dates et points de contrôle remplis.' },
        { title: 'Le skill d’agent d’IA de l’ingénieur', path: '', body: 'Généré à partir de vos spécifications et commité dans votre dépôt. Un ingénieur démarre un élément de travail en le nommant, par exemple « Work on [work item ID] », et l’agent de codage lit d’abord la spécification et le contexte approuvé de cet élément.' },
      ],
    },
  },

  diagram: {
    ariaLabel:
      'Le contexte de projet que vous fournissez, documents, décisions et plus tard un changement, alimente l’agent d’IA. Celui-ci génère pour votre équipe un plan de projet à relire et à approuver, une spécification pour chaque élément de travail, un tableau GitHub avec tickets et jalons où chaque ticket lie sa spécification et cite ses sources, et un agent skill propre au projet, installé une fois par chaque ingénieur qui utilise un agent de codage.',
    provideHeading: 'Contexte que vous fournissez',
    generatesHeading: 'L’agent d’IA génère pour l’équipe',
    documents: 'Documents',
    documentsNote: 'architecture, exigences, règles',
    decisions: 'Décisions',
    decisionsNote: 'personnes, affectation, échéances',
    later: 'Plus tard',
    changed: 'Quelque chose a changé',
    changedNote: 'document modifié, spécification fausse',
    agent: 'Agent d’IA',
    agentVerbs: ['lit, planifie, cite,', 'transmet, réconcilie'],
    plans: 'Planifie',
    plansTitle: 'Plan de projet à relire et approuver',
    plansNote: 'jalons, pistes, dates ajustées à vos équipes',
    writes: 'Écrit',
    writesTitle: 'Une spécification par élément',
    writesNote: 'toutes issues de la même vérité',
    opens: 'Ouvre',
    opensTitle: 'Tableau GitHub, tickets et jalons',
    opensNote: 'chaque ticket lie sa spécification et ses sources',
    generates: 'Génère',
    generatesTitle: 'Agent skill propre au projet',
    generatesNote: 'installé une fois par chaque ingénieur',
    engineers: ['Ingénieurs avec', 'agents de codage'],
  },
};
