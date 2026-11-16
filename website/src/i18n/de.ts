// German strings. Same shape as en.ts, so the compiler flags a missing key. Brand names, the term
// "Carried-context development" and the quoted agent commands stay in English. A native speaker has
// not reviewed this translation yet, and every translated page says so.
import { en, type Strings } from './en';

export const de: Strings = {
  lang: 'de',
  dir: 'ltr',
  label: 'Deutsch',

  site: {
    name: 'Carried-context development',
    skipLink: 'Zum Hauptinhalt springen',
    homeLabel: 'Carried-context development, Startseite',
  },

  nav: {
    label: 'Hauptnavigation',
    definition: 'Definition',
    github: 'GitHub',
    docs: 'Doku',
    faq: 'FAQ',
    accessibility: 'Erklärung zur Barrierefreiheit',
    menu: 'Menü',
    docsMenu: 'Doku-Menü',
  },

  controls: {
    themeLabel: 'Darstellung',
    themeAuto: 'Auto',
    themeDark: 'Dunkel',
    themeLight: 'Hell',
    languageLabel: 'Sprache',
  },

  search: {
    button: 'Suchen',
    title: 'Diese Website durchsuchen',
    close: 'Schließen',
    unavailable: 'Die Suche funktioniert auf der veröffentlichten Website. In der Entwicklungsvorschau ist sie nicht verfügbar.',
  },

  translation: {
    note: 'Diese Übersetzung wird noch von Muttersprachlern geprüft. Die englische Seite ist maßgeblich.',
    link: 'Englische Seite lesen',
  },

  footer: {
    label: 'Fußbereich',
    copyright: en.footer.copyright,
  },

  definition: {
    title: 'Carried-context development, Definition',
    description:
      'Carried-context development trägt die vereinbarte Faktengrundlage eines Teams hinunter in den Plan, in jede Spezifikation, jedes Issue und die Anweisungen jedes Coding-Agenten, mit Abschnittsangabe, und trägt sie erneut hinunter, wenn sich die Faktengrundlage ändert.',
    h1: 'Carried-context development',
    status: ['Status: offene Methode', 'Version 1.0', 'November 2026', 'Will Scott, PhD'],
    contents: 'Inhalt',
    sections: [
      'Definition',
      'Die Regeln',
      'Der Unterschied zu spezifikationsgetriebener Entwicklung',
      'Referenzimplementierung',
      'So wird zitiert',
      'Änderungsprotokoll',
    ],
    definition:
      'Carried-context development trägt die vereinbarte Faktengrundlage eines Teams hinunter in den Plan, in jede Spezifikation, jedes Issue und die Anweisungen jedes Coding-Agenten, mit Abschnittsangabe, und trägt sie erneut hinunter, wenn sich die Faktengrundlage ändert.',
    rules: [
      {
        title: 'Eine Faktengrundlage.',
        body: 'Die vom Team vereinbarten Dokumente sind die einzige von Menschen verfasste Eingabe. Alles Nachgelagerte wird aus ihnen abgeleitet, und nichts Nachgelagertes steht über ihnen.',
      },
      {
        title: 'Auf echte Menschen und Termine abgestimmt.',
        body: 'Der Plan richtet sich danach, wer verfügbar ist, mit wie viel Zeit und bis wann geliefert werden muss. Wer eines vorgibt, bekommt das andere abgeleitet.',
      },
      {
        title: 'Eine Spezifikation pro Arbeitspaket.',
        body: 'Ein Arbeitspaket ist die kleinste Einheit, die ein Entwickler fertigstellen und vorführen kann. Jedes hat eine eigene Spezifikation.',
      },
      {
        title: 'Mit Abschnittsangabe belegt.',
        body: 'Jede Spezifikation, jedes Issue und jede Anweisung nennt die Abschnitte der Faktengrundlage, aus denen sie stammt. Eine Prüfung validiert jeden Beleg, aus einem frischen Klon.',
      },
      {
        title: 'Freigegeben, nicht generiert.',
        body: 'Ein Mensch entscheidet über Verantwortliche, Termine, Umfang und Reihenfolge, gibt frei, was mit wem geteilt werden darf, und gibt frei, was veröffentlicht wird. Nichts wird ohne ein Ja gepostet.',
      },
      {
        title: 'Zum Agenten getragen.',
        body: 'Der Coding-Agent des Entwicklers liest die Spezifikation und die belegten Abschnitte, bevor er eine Zeile Code plant.',
      },
      {
        title: 'Bei Änderungen erneut getragen.',
        body: 'Ändert sich die Faktengrundlage, findet eine Prüfung die betroffene Arbeit und behält die Korrekturen der Entwickler. Die freigegebene Aktualisierung wird bis in jedes Arbeitspaket getragen.',
      },
    ],
    differs:
      'Spezifikationsgetriebene Entwicklung überlässt jede Spezifikation dem Entwickler, der sie schreibt. Die Qualität hängt davon ab, wer sie verfasst hat. Keine zwei Spezifikationen gleichen sich, und nichts verbindet sie. Sie driften auseinander, wenn sich das Projekt ändert. Carried-context development leitet jede Spezifikation aus derselben Faktengrundlage ab, prüft die Spezifikationen gemeinsam, belegt die Quellen und trägt jede freigegebene Änderung zu jedem Coding-Agenten. Context Engineering, ein Nachbar, bestimmt, was ein Modell in einem Schritt sieht; Carried Context bestimmt, was das ganze Projekt befolgen muss.',
    compare: {
      aspect: 'Merkmal',
      specDriven: 'Spezifikationsgetriebene Entwicklung',
      carried: 'Carried-context development',
      rows: [
        ['Planungseinheit', 'Eine Aufgabe oder ein Feature', 'Das gesamte Projekt'],
        ['Was weitergegeben wird', 'Die Spezifikation', 'Die Faktengrundlage, mit Abschnittsangabe'],
        [
          'Wenn sich die Quellen ändern',
          'Die Spezifikation neu schreiben',
          'Eine Prüfung. Korrekturen der Entwickler bleiben erhalten',
        ],
        [
          'Wer die Spezifikation schreibt',
          'Der Entwickler',
          'Vom KI-Agenten aus der Faktengrundlage abgeleitet, vom Plan-Verantwortlichen geprüft',
        ],
        [
          'Konsistenz zwischen Spezifikationen',
          'Nicht erzwungen',
          'Gemeinsam geprüft, jeder Beleg kontrolliert',
        ],
        ['Wer entscheidet', 'Der Entwickler', 'Der Plan-Verantwortliche, die Entwickler, die Stakeholder'],
      ],
    },
    reference: {
      body: 'carrydown, zwei Agent Skills und ein generierter dritter, Apache 2.0, erster Commit am 24. Oktober 2026.',
      link: 'github.com/sct-will/carrydown',
    },
    cite: {
      heading: 'So wird zitiert',
      text: en.definition.cite.text,
      bibtex: en.definition.cite.bibtex,
    },
    changelog: '1.0, November 2026. Erste Veröffentlichung.',
  },

  faq: {
    title: 'Fragen, carried-context development',
    description:
      'Kurze Antworten zu carried-context development und carrydown und dazu, was carrydown nicht tut.',
    h1: 'Fragen',
    intro: 'Kurze Antworten, mit Links in die Doku, wo es mehr gibt.',
    items: [
      {
        q: 'Bescheinigt es, dass meine Dokumente richtig sind?',
        a: 'Nein. Es geht von dem aus, was Sie mitbringen, und hilft Ihnen, es zu prüfen.',
      },
      {
        q: 'Ist es für einen Ein-Personen-Spike gedacht?',
        a: 'Eher nicht. Es lohnt sich, wenn mehrere Entwickler über Wochen an einer vereinbarten Architektur arbeiten.',
      },
      { q: 'Beobachtet es meine Dokumente?', a: 'Nein. Eine Aktualisierung beginnt, wenn Sie sagen, was sich geändert hat.' },
      {
        q: 'Welche Coding-Agenten?',
        a: 'Jeder Coding-Agent, der Agent Skills unterstützt. Ihre Entwickler behalten den, den sie nutzen.',
      },
      {
        q: 'Welche Lizenz?',
        a: 'Apache 2.0. Die Sicherheitsrichtlinie, das Änderungsprotokoll und die Antworten auf häufige Sicherheitsfragen von Unternehmen liegen im Repository.',
      },
    ],
    doesNotHeading: 'Was carrydown nicht tut',
    doesNot: [
      'Es schreibt keinen Anwendungscode.',
      'Jeder Schreibzugriff auf GitHub ist ein Probelauf, bis Sie --apply angeben.',
      'Es löscht nie Issues, Labels, Projekte oder Repositories.',
      'Der Aktualisierungsvergleich läuft auf Ihrem Rechner. Kein Netzwerk, kein Token, kein Modellaufruf.',
      'Vertrauliche Dokumente bleiben auf Ihrem Rechner, es sei denn, Sie sagen, dass alle sie sehen dürfen.',
      'Namen, freie Tage und Zuteilung bleiben in einer privaten Datei, nie im Plan.',
      'Wenn Sie aufhören, behalten Sie reines Markdown und gewöhnliche GitHub-Issues.',
    ],
  },

  accessibility: {
    title: 'Erklärung zur Barrierefreiheit',
    description:
      'Diese Website soll für alle nutzbar sein. Sie strebt die Web Content Accessibility Guidelines (WCAG) 2.2 auf Stufe AA an.',
    h1: 'Erklärung zur Barrierefreiheit',
    intro:
      'Diese Website soll für alle nutzbar sein, auch für Menschen, die einen Screenreader, nur die Tastatur, Vergrößerung oder reduzierte Bewegung nutzen. Sie strebt die Web Content Accessibility Guidelines (WCAG) 2.2 auf Stufe AA an.',
    doneHeading: 'Was getan wurde',
    done: [
      'Text- und Oberflächenfarben werden im hellen und im dunklen Thema auf Kontrast geprüft, und Sie können ein Thema wählen oder Ihrem System folgen.',
      'Jede Seite funktioniert allein mit der Tastatur, mit sichtbarem Fokusindikator und einem Link zum Überspringen zum Hauptinhalt.',
      'Das Diagramm ist aus Text und Vektorformen gezeichnet. Es skaliert, folgt Ihrem Thema und trägt eine schriftliche Beschreibung für Screenreader.',
      'Nichts auf der Website bewegt sich von selbst. Jede künftige Animation beachtet die Einstellung für reduzierte Bewegung und bietet ein Standbild an.',
      'Überschriften, Landmarken und Linktexte sind so geschrieben, dass man sie der Reihe nach und aus dem Zusammenhang gelöst lesen kann.',
      'Die Website wird vor jeder Veröffentlichung mit automatisierten Werkzeugen geprüft und von Hand mit einem Screenreader begutachtet.',
    ],
    notFinishedHeading: 'Was noch nicht fertig ist',
    notFinished:
      'Die Übersetzungen der Website werden von Muttersprachlern geprüft und gehen Sprache für Sprache online. Der Dokumentationsbereich wird aus dem Repository erzeugt und kann in diesen Punkten hinter dem Rest der Website zurückliegen, bis jede Version geprüft ist.',
    contactHeading: 'Melden Sie uns ein Problem',
    contactBefore:
      'Wenn etwas auf dieser Website mit assistiven Technologien schwer zu bedienen ist oder Sie die Inhalte in einer anderen Form brauchen, schreiben Sie an ',
    contactAfter: '. Nennen Sie die Seite und was passiert ist. Sie sollten innerhalb von zehn Arbeitstagen eine Antwort erhalten.',
    review:
      'Diese Erklärung beschreibt die Absicht der Website und ihren aktuellen Stand. Sie wird überprüft, wenn sich die Website ändert. Zuletzt geprüft am 16. November 2026.',
  },

  home: {
    title: 'Carried-context development, Startseite',
    description:
      'Carried-context development ist ein Ansatz für agentische Entwicklung, der Projektentscheidungen und Kontext bis zum Coding-Agenten jedes Entwicklers trägt, damit das Projekt ausgerichtet bleibt und nichts auseinanderdriftet.',
    h1: [
      'Carried-context development geht über spezifikationsgetriebene Entwicklung hinaus.',
      'Der Kontext reist mit der Arbeit.',
    ],
    definition:
      'Halten Sie das Projekt ausgerichtet, indem Sie dem Coding-Agenten jedes Entwicklers dieselben Projektentscheidungen und denselben Kontext geben.',
    paragraph:
      'Ihr Team liefert die Projektdokumente, die Anforderungen und die Entscheidungen zu Personen und Terminen. Ihr KI-Agent nutzt diese Faktengrundlage, um einen verbundenen Plan, eine Spezifikation für jedes Arbeitspaket und GitHub-Issues zu erstellen, die jede Spezifikation verlinken und die dahinterstehenden Dokumentabschnitte belegen. Ihr KI-Agent generiert außerdem einen projektspezifischen Agent Skill, der die Spezifikation, die Entscheidungen dahinter und die belegten Abschnitte zum Coding-Agenten jedes Entwicklers trägt. Wenn sich ein Dokument ändert, prüfen Sie eine einzige Aktualisierung.',
    buttons: {
      try: 'Auf GitHub ausprobieren',
      sample: 'KI-Agent-Ergebnisse eines Beispielprojekts ansehen',
    },
    howHeading: 'So funktioniert es',
    sideParagraphs: [
      'Wenn Entwickler Spezifikationen unabhängig voneinander schreiben, schwankt die Qualität, und die Spezifikationen driften auseinander, während sich das Projekt ändert.',
      'Carried-context development bindet jede Spezifikation an dieselbe Faktengrundlage, belegt die Quellen und trägt jede freigegebene Änderung zu jedem Coding-Agenten.',
    ],
    values: [
      {
        eyebrow: 'Verbundener Plan',
        title: 'Als verbundenes Ganzes geplant.',
        body: 'Ein Plan und jede Spezifikation stammen aus derselben Faktengrundlage. Abhängigkeiten, Schnittstellen und Abnahmekriterien werden gemeinsam auf Lücken und Widersprüche geprüft, und eine Prüfung validiert jeden Beleg.',
      },
      {
        eyebrow: 'Übergabe an die Entwicklung',
        title: 'Eine Übergabe, die den Coding-Agenten erreicht.',
        body: 'Jedes Issue verlinkt seine Spezifikation und belegt seine Abschnitte der Faktengrundlage. Ein projektspezifischer Agent Skill legt dem Coding-Agenten die freigegebene Spezifikation, diese Abschnitte und Ihre Konventionen vor, bevor er Code plant.',
      },
      {
        eyebrow: 'Projektkontext synchron gehalten',
        title: 'Änderungen von Projektleitung oder Entwicklern werden durchgereicht.',
        body: 'Die Projektleitung meldet eine geänderte Quelle, oder ein Entwickler markiert eine falsche Spezifikation. Der Agent findet die betroffene Arbeit, behält Korrekturen, die noch passen, und legt Ihnen Konflikte vor. Freigegebene Aktualisierungen fließen durch Spezifikationen, Issues und Übergabe.',
      },
    ],
    carrydown: {
      heading: 'Probieren Sie es aus',
      intro:
        'Carried-context development ist ein Ansatz für agentische Entwicklung, und es gibt mehr als einen Weg, ihn umzusetzen. carrydown ist die Referenzimplementierung: zwei Agent Skills, die Sie installieren, ein dritter, den sie für Ihre Entwickler generiert, und die Prüfungen, die jeden Beleg validieren. Sie ist Open Source unter Apache 2.0 und arbeitet mit dem Coding-Agenten, den Ihr Team bereits nutzt.',
      tryButton: 'Auf GitHub ausprobieren',
      installCommand: en.home.carrydown.installCommand,
      copy: 'Kopieren',
      copied: 'Kopiert',
      copyLabel: 'Installationsbefehl kopieren',
      copiedStatus: 'Installationsbefehl in die Zwischenablage kopiert.',
      copyFailedStatus: 'Kopieren nicht möglich. Markieren Sie den Befehl und kopieren Sie ihn.',
      tiles: [
        {
          step: 'Schritt 1',
          title: 'Einen fertigen Beispielplan ansehen.',
          body: 'Das Beispielboard und seine Issues auf GitHub.',
          command: '',
          button: 'Beispiel öffnen',
        },
        {
          step: 'Schritt 2',
          title: 'carrydown in Ihrem Projekt ausführen.',
          body: 'Installieren Sie die zwei carrydown-Skills und sagen Sie dann',
          command: en.home.carrydown.tiles[1].command,
          button: 'Einrichtung',
        },
      ],
      stepsHeading: 'Ihr KI-Agent führt Sie durch den Einsatz von carrydown in Ihrem Projekt',
      steps: [
        {
          who: 'Plan-Verantwortlicher',
          what: 'Installiert die zwei carrydown-Skills und startet den Plan.',
          say: en.home.carrydown.steps[0].say,
        },
        {
          who: 'Plan-Verantwortlicher',
          what: 'Prüft Plan und Spezifikationen und veröffentlicht dann.',
          say: en.home.carrydown.steps[1].say,
        },
        {
          who: 'Jeder Entwickler',
          what: 'Installiert den generierten Agent Skill einmal und nennt ein Arbeitspaket.',
          say: en.home.carrydown.steps[2].say,
        },
        {
          who: 'Stakeholder',
          what: 'Melden eine geänderte Quelle oder eine Spezifikation, die falsch scheint. Eine Prüfung, dann wird die freigegebene Aktualisierung hinuntergetragen.',
          say: en.home.carrydown.steps[3].say,
        },
      ],
      reviewNote: 'Stakeholder, Projektverantwortliche und Engineering-Manager sehen sich jeden Meilenstein an und entscheiden über bestanden oder nicht bestanden. Die Prüfung durch Menschen ist ausdrücklich Teil der Methode.',
    },
  },

  diagram: {
    ariaLabel:
      'Der Projektkontext, den Sie liefern, nämlich Dokumente, Entscheidungen und später eine Änderung, speist den KI-Agenten. Dieser generiert für Ihr Team einen Projektplan zur Prüfung und Freigabe, eine Spezifikation für jedes Arbeitspaket, ein GitHub-Board mit Issues und Meilensteinen, wobei jedes Issue seine Spezifikation verlinkt und seine Quellen belegt, und einen projektspezifischen Agent Skill, den jeder Entwickler einmal installiert und mit einem Coding-Agenten nutzt.',
    provideHeading: 'Projektkontext von Ihnen',
    generatesHeading: 'KI-Agent generiert für Ihr Team',
    documents: 'Dokumente',
    documentsNote: 'Architektur, Anforderungen, Regeln',
    decisions: 'Entscheidungen',
    decisionsNote: 'Personen, Zuteilung, Termine',
    later: 'Später',
    changed: 'Etwas hat sich geändert',
    changedNote: 'Dokument geändert, Spezifikation falsch',
    agent: 'KI-Agent',
    agentVerbs: ['liest, plant, belegt,', 'übergibt, gleicht ab'],
    plans: 'Plant',
    plansTitle: 'Projektplan zur Prüfung und Freigabe',
    plansNote: 'Meilensteine, Spuren, Termine für Ihr Team',
    writes: 'Schreibt',
    writesTitle: 'Eine Spezifikation je Arbeitspaket',
    writesNote: 'alle aus derselben Faktengrundlage',
    opens: 'Eröffnet',
    opensTitle: 'GitHub-Board, Issues, Meilensteine',
    opensNote: 'jedes Issue verlinkt Spezifikation und Quellen',
    generates: 'Generiert',
    generatesTitle: 'Projektspezifischer Agent Skill',
    generatesNote: 'einmal von jedem Entwickler installiert',
    engineers: ['Entwickler mit', 'Coding-Agenten'],
  },
};
