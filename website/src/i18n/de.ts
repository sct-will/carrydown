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

  copyPage: {
    button: 'Seite kopieren',
    copied: 'Kopiert',
    menu: 'Weitere Möglichkeiten für diese Seite',
    asMarkdown: 'Seite als Markdown kopieren',
    open: 'Markdown öffnen',
    source: 'Quelle auf GitHub ansehen',
    ok: 'Seite als Markdown in die Zwischenablage kopiert.',
    fail: 'Kopieren nicht möglich. Öffnen Sie das Markdown und kopieren Sie es von dort.',
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
      'Antworten zu carried-context development und carrydown: der Unterschied zu spezifikationsgetriebener Entwicklung, warum es kein Wasserfall ist, wie die Arbeit auf GitHub mit der Faktengrundlage abgeglichen bleibt und was carrydown nicht tut.',
    h1: 'Fragen',
    intro: 'Antworten auf die häufigsten Fragen, mit Links in die Doku, wo es mehr gibt. Jede Frage hat einen eigenen Link.',
    items: [
      {
        id: 'spec-driven',
        q: 'Was unterscheidet das von klassischer spezifikationsgetriebener Entwicklung?',
        a: 'Bei spezifikationsgetriebener Entwicklung schreibt jeder Entwickler die Spezifikation für seine eigene Aufgabe. Die Qualität hängt davon ab, wer sie geschrieben hat, keine zwei Spezifikationen gleichen sich, und nichts hält sie zusammen, sobald sich das Projekt ändert. Carried-context development setzt eine Ebene höher an. Ihr KI-Agent leitet jede Spezifikation aus derselben vereinbarten Faktengrundlage ab und zitiert die Abschnitte, aus denen sie stammt. Der Plan-Verantwortliche prüft die Spezifikationen gemeinsam, bevor etwas veröffentlicht wird, und eine Prüfung validiert jedes Zitat aus einem frischen Klon. Ändert sich die Faktengrundlage, trägt eine einzige Durchsicht die freigegebene Änderung in jede Spezifikation, jedes Issue und jeden Coding-Agenten, statt dass jeder Entwickler seine eigene umschreibt.',
        more: { label: 'Den direkten Vergleich auf der Definitionsseite ansehen.', href: '/definition/#differs' },
      },
      {
        id: 'waterfall',
        q: 'Ist das nicht einfach Wasserfall?',
        a: 'Nein. Das Wasserfallmodell legt den ganzen Plan im Voraus fest und behandelt eine Änderung als Versagen des Plans. Hier sind Plan, Spezifikationen und Issues Dateien in Git, also ist eine Änderung billig und wird wie Code geprüft. Arbeitseinheiten dauern so lange, wie die Arbeit braucht, statt in Kästen fester Länge zu passen. Jeder Meilenstein endet mit einer Vorführung, über die die Stakeholder mit bestanden oder nicht bestanden entscheiden, und was das Team lernt, fließt in die Faktengrundlage zurück und wird erneut hinuntergetragen. Sie können planen, ein wenig bauen, lernen und den Plan so oft anpassen, wie das Projekt es braucht.',
        more: { label: 'In der Methode lesen, wie eine Änderung hinuntergetragen wird.', href: '/docs/method/#when-the-project-changes' },
      },
      {
        id: 'reconciled',
        q: 'Wie bleiben Projektboard, Issues, Spezifikationen und der Skill der Entwickler mit der Faktengrundlage abgeglichen?',
        a: 'Sie sagen Ihrem Agenten, was sich geändert hat. Sagen Sie „This changed: …“ und beschreiben Sie die Änderung oder übergeben Sie die überarbeiteten Dokumente. Der Agent vergleicht die Änderung mit den Quellen, die Sie zuletzt geprüft haben, und mit der laufenden Arbeit, findet die betroffenen Spezifikationen und Issues, behält die Korrekturen der Entwickler, die noch passen, und zeigt Ihnen eine einzige Durchsicht der vorgeschlagenen Aktualisierungen und aller Konflikte. Nichts bewegt sich, bevor Sie freigeben. Die freigegebene Aktualisierung durchläuft dann dieselbe Veröffentlichung wie der Plan: Sie aktualisiert das Board und die Issues, die Sie auswählen, löscht keines davon und generiert den Skill der Entwickler neu, sodass jeder Coding-Agent die neue Spezifikation liest, wenn ein Entwickler das nächste Mal ein Arbeitspaket nennt.',
        more: { label: 'Den Schritten im Leitfaden für Plan-Verantwortliche folgen.', href: '/docs/plan-owner-guide/#when-the-project-changes' },
      },
      {
        id: 'certify',
        q: 'Bescheinigt es, dass meine Dokumente richtig sind?',
        a: 'Nein. Die Faktengrundlage ist das, worauf sich Ihr Team geeinigt hat, und der Agent nimmt sie als gegeben. Was er hinzufügt, ist Prüfung. Er rendert jedes Dokument, hilft Ihnen mit Fragen bei der Durchsicht, und eine zweite Prüfung stellt den fertigen Plan seinen Quellen, seinen Randbedingungen und seinen Besetzungsentscheidungen gegenüber. Ist ein Dokument falsch, ist der Plan auf dieselbe Weise falsch, und die Korrektur gehört in das Dokument und nicht in den Plan.',
      },
      {
        id: 'one-person',
        q: 'Ist es für einen Ein-Personen-Spike gedacht?',
        a: 'Eher nicht. Die Methode lohnt sich, wenn mehrere Entwickler über Wochen an einer vereinbarten Architektur arbeiten und auseinanderdriftende Spezifikationen echte Zeit kosten. Für einen Ein-Personen-Spike sind Plan, Spezifikationen und Board mehr Struktur, als die Arbeit braucht. Besonders gut passt sie zu Unternehmensteams, bei denen Governance-Regeln, Entwicklungsstandards und Unternehmenskontext Teil der Faktengrundlage sind und mehrere Teams auf einer Architektur aufbauen. Nutzen Sie sie, wenn ein Team Arbeit an Coding-Agenten übergibt und jeder davon von denselben Entscheidungen ausgehen muss.',
      },
      {
        id: 'governance',
        q: 'Wie unterstützt das die KI-Governance?',
        a: 'Governance-Regeln, Entwicklungsstandards und Unternehmenskontext gehen neben den technischen Dokumenten als Faktengrundlage ein, als Word, Markdown, Klartext oder geprüfte Auszüge aus PDF- und Bilddateien. Der Plan hält Version und Rang jeder Quelle fest, jedes Arbeitspaket zitiert die Abschnitte, die für es gelten, und die Prüfungen validieren diese Zitate beim Entwurf und noch einmal in einem frischen Klon. Der generierte Skill der Entwickler verweist jeden Coding-Agenten auf den freigegebenen Kontext, sodass der Agent die geltenden Regeln liest, bevor er Code plant. Sie prüfen die Entwürfe und geben nach Vorschau und Probelauf genau frei, was mit wem und wo geteilt wird, und Plan, Spezifikationen, Quellversionen und festgehaltene Entscheidungen bleiben in Ihrem Repository. Die automatischen Prüfungen und die zweite Prüfung halten Belege und Risiken fest, und ob die Arbeit die Anforderungen Ihrer Organisation erfüllt, beurteilt weiterhin Ihr Team.',
        more: { label: 'Lesen, wie carrydown die KI-Governance unterstützt.', href: '/docs/#how-does-carrydown-support-ai-governance' },
      },
      {
        id: 'watch',
        q: 'Beobachtet es meine Dokumente?',
        a: 'Nein. carrydown hat keine Dateiüberwachung und liest Ihr Dokumentensystem nie von sich aus. Eine Aktualisierung beginnt, wenn Sie sagen, was sich geändert hat, und das überarbeitete Material bereitstellen, und sie endet, wenn Sie die Durchsicht freigeben. Die Meilensteinprüfung im Leitfaden für Plan-Verantwortliche fragt außerdem, ob sich seit dem letzten Plan eine Quelle, eine Anforderung oder eine Randbedingung geändert hat, sodass eine Änderung spätestens dort auffällt.',
      },
      {
        id: 'agents',
        q: 'Welche Coding-Agenten?',
        a: 'Jeder Coding-Agent, der Agent Skills unterstützt und Projektdateien lesen und bearbeiten sowie Befehle ausführen kann. Ihre Entwickler behalten den, den sie bereits nutzen. Der generierte Skill ist ein Ordner mit Anweisungen, den ihr Agent lädt, und er enthält keine Zugangsdaten. Die Einrichtungsanleitung listet die unterstützten Agenten und die Installationsschritte für jeden.',
        more: { label: 'Einen Coding-Agenten in der Einrichtungsanleitung wählen.', href: '/docs/setup/#choose-a-coding-agent' },
      },
      {
        id: 'license',
        q: 'Welche Lizenz?',
        a: 'Apache 2.0, für die Skills, die Skripte und die Vorlagen. Das Repository enthält die Sicherheitsrichtlinie, das Änderungsprotokoll und die Antworten auf häufige Sicherheitsfragen von Unternehmen, jede mit dem Vermerk unterstützt, unterstützt mit Voraussetzungen oder geplant.',
        more: { label: 'Das Repository auf GitHub öffnen.', href: 'https://github.com/sct-will/carrydown' },
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
    title: 'Carried context, eine Faktengrundlage für jeden Coding-Agenten',
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
      try: 'Hier starten',
      sample: 'KI-Agent-Ergebnisse eines Beispielprojekts ansehen',
    },
    /** A small line under the buttons. */
    license: 'Open Source unter Apache 2.0.',
    howHeading: 'So funktioniert es',
    /** The last sentence under How it works; the middle word is the link to the README section. */
    learnMore: { before: 'Mehr dazu ', link: 'hier', after: '.' },
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
    /** The What you get section: the outputs, summarized from the README's list. */
    whatYouGet: {
      heading: 'Was Sie bekommen',
      intro:
        'Ihr KI-Agent erzeugt diese Ergebnisse mit den carrydown-Skills. Jedes Arbeitspaket kann Abschnitte aus einer oder mehreren Quellen belegen, und Termine und Kapazität werden gegen das benannte Team geprüft.',
      /** The word between a title and the path that follows it, where there is one. */
      inWord: 'in',
      items: [
        { title: 'Ein Plan', path: 'docs/spec/plan.yaml', body: 'Meilensteine, Tracks, Verantwortliche und Termine, an Ihre Leute und Ihre Zeit angepasst, mit einer Begründung für jeden Meilenstein.' },
        { title: 'Eine Spezifikation pro Arbeitspaket', path: '', body: 'Das kleinste Stück Arbeit, das ein Entwickler abschließen und vorführen kann, mit Belegen auf seine Abschnitte und bei jedem Pull Request gegen den Plan geprüft.' },
        { title: 'Ein freigegebener Kontext pro Arbeitspaket', path: 'docs/context/', body: 'Der genaue Quelltext der belegten Abschnitte und die Entscheidungen dahinter, von Ihnen freigegeben. Der einzige Teil Ihrer Dokumente, der die Agenten der Entwickler erreicht.' },
        { title: 'Eine Release-Quittung', path: 'docs/release/', body: 'Eine kleine öffentliche Datei, die das freigegebene Release, seinen Zustand und sein Ablaufdatum nennt.' },
        { title: 'Ein Bericht der zweiten Prüfung', path: '', body: 'Abdeckung, Belege, Begründung und Risiko, mit Ihren Entscheidungen und den Prüfungen der angenommenen Korrekturen.' },
        { title: 'GitHub-Issues', path: '', body: 'Eines pro Arbeitspaket unter einem Sub-Epic pro Meilenstein, und jedes sagt dem Agenten des Entwicklers, was er lesen soll.' },
        { title: 'Ein GitHub-Projektboard', path: '', body: 'Arbeitseinheiten, Tracks, Termine und Checkpoints ausgefüllt.' },
        { title: 'Der KI-Agent-Skill des Entwicklers', path: '', body: 'Aus Ihren Spezifikationen generiert und in Ihrem Repository committet. Ein Entwickler startet ein Arbeitspaket, indem er es nennt, zum Beispiel „Work on [work item ID]“, und der Coding-Agent liest zuerst die Spezifikation und den freigegebenen Kontext dieses Pakets.' },
      ],
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
