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
    intro: 'Antworten auf die häufigsten Fragen, mit Links in die Doku, wo es mehr gibt.',
    methodHeading: 'Zu carried-context development',
    toolHeading: 'Zu carrydown',
    anchorLabel: 'Link zu dieser Frage',
    items: [
      {
        id: 'what-is-carried-context-development',
        group: 'method',
        q: 'Was ist carried-context development?',
        a: 'Carried-context development ist ein Ansatz für agentische Entwicklung, der Projektentscheidungen und Kontext bis zum Coding-Agenten jedes Entwicklers trägt und so hilft, Spezifikationen und Coding-Agenten aufeinander abgestimmt zu halten, während sich das Projekt ändert. Carried-context development trägt die vereinbarte Faktengrundlage eines Teams hinunter in den Plan, in jede Spezifikation, jedes Issue und die Anweisungen jedes Coding-Agenten, mit Abschnittsangabe, und trägt sie erneut hinunter, wenn sich die Faktengrundlage ändert.',
        more: { label: 'Die Definition und die Regeln auf der Definitionsseite lesen.', href: '/definition/' },
      },
      {
        id: 'spec-driven',
        group: 'method',
        q: 'Was unterscheidet carried-context development von klassischer spezifikationsgetriebener Entwicklung?',
        a: 'Bei spezifikationsgetriebener Entwicklung schreibt jeder Entwickler die Spezifikation für seine eigene Aufgabe. Die Qualität hängt davon ab, wer sie geschrieben hat, keine zwei Spezifikationen gleichen sich, und nichts hält sie zusammen, sobald sich das Projekt ändert. Carried-context development setzt eine Ebene höher an. Ihr KI-Agent leitet jede Spezifikation aus derselben vereinbarten Faktengrundlage ab und zitiert die Abschnitte, aus denen sie stammt. Der Plan-Verantwortliche prüft die Spezifikationen gemeinsam, bevor etwas veröffentlicht wird, und eine Prüfung validiert jedes Zitat aus einem frischen Klon. Ändert sich die Faktengrundlage, trägt eine einzige Durchsicht die freigegebene Änderung in jede Spezifikation, jedes Issue und jeden Coding-Agenten, statt dass jeder Entwickler seine eigene umschreibt.',
        more: { label: 'Den direkten Vergleich auf der Definitionsseite ansehen.', href: '/definition/#differs' },
      },
      {
        id: 'rag',
        group: 'method',
        q: 'Was unterscheidet carried-context development von Retrieval-Augmented Generation?',
        a: 'Retrieval-Augmented Generation versorgt ein Modell mit Material, das es im Moment der Anfrage findet. Carried-context development hält während der Planung und nach einer Prüfung durch Menschen fest, welchen freigegebenen Quellabschnitten eine Arbeit folgen muss, und gibt Ihnen einen geprüften Weg, das später zu ändern. Retrieval kann Teil einer Implementierung sein. Es legt diese Projektentscheidungen und ihre Prüfung aber nicht von sich aus fest.',
      },
      {
        id: 'prompts',
        group: 'method',
        q: 'Sind das nicht einfach Prompts?',
        a: 'Nein. Die Prüfung ist Code, und sie lässt die Continuous Integration fehlschlagen, wenn eine Spezifikation gegen die Regeln verstößt. Skripte bauen das Board über die Programmierschnittstelle von GitHub auf. Der Plan und die Spezifikationen sind Dateien in Git, die Sie lesen, vergleichen und prüfen können. Die Prompts sind der kleinste Teil.',
      },
      {
        id: 'waterfall',
        group: 'method',
        q: 'Ist carried-context development nicht einfach Wasserfall?',
        a: 'Nein. Das Wasserfallmodell legt den ganzen Plan im Voraus fest und behandelt eine Änderung als Versagen des Plans. Hier sind Plan, Spezifikationen und Issues Dateien in Git, also ist eine Änderung billig und wird wie Code geprüft. Arbeitseinheiten dauern so lange, wie die Arbeit braucht, statt in Kästen fester Länge zu passen. Jeder Meilenstein endet mit einer Vorführung, über die die Stakeholder mit bestanden oder nicht bestanden entscheiden, und was das Team lernt, fließt in die Faktengrundlage zurück und wird erneut hinuntergetragen. Sie können planen, ein wenig bauen, lernen und den Plan so oft anpassen, wie das Projekt es braucht.',
        more: { label: 'In der Methode lesen, wie eine Änderung hinuntergetragen wird.', href: '/docs/method/#when-the-project-changes' },
      },
      {
        id: 'what-is-carrydown',
        group: 'carrydown',
        q: 'Was ist carrydown, und was unterscheidet es von carried-context development?',
        a: 'Carried-context development ist ein Ansatz für agentische Entwicklung. Carried-context development trägt die vereinbarte Faktengrundlage eines Teams hinunter in den Plan, in jede Spezifikation, jedes Issue und die Anweisungen jedes Coding-Agenten, mit Abschnittsangabe, und trägt sie erneut hinunter, wenn sich die Faktengrundlage ändert. carrydown ist die Referenzimplementierung: zwei Agent Skills, die Sie zusammen mit einem Befehl installieren, ein dritter, den sie für Ihre Entwickler generiert, und die Prüfungen, die jeden Beleg validieren. Sie ist Open Source unter Apache 2.0 und arbeitet mit dem Coding-Agenten, den Ihr Team bereits nutzt.',
        more: { label: 'In der Doku lesen, wie es funktioniert.', href: '/docs/#how-it-works' },
      },
      {
        id: 'reconciled',
        group: 'carrydown',
        q: 'Wie hält carrydown Projektboard, Issues, Spezifikationen und den Skill der Entwickler mit der Faktengrundlage abgeglichen?',
        a: 'Sie sagen Ihrem Agenten, was sich geändert hat. Sagen Sie „This changed: …“ und beschreiben Sie die Änderung oder übergeben Sie die überarbeiteten Dokumente. Der Agent vergleicht die Änderung mit den Quellen, die Sie zuletzt geprüft haben, und mit der laufenden Arbeit, findet die betroffenen Spezifikationen und Issues, behält die Korrekturen der Entwickler, die noch passen, und zeigt Ihnen eine einzige Durchsicht der vorgeschlagenen Aktualisierungen und aller Konflikte. Nichts bewegt sich, bevor Sie freigeben. Die freigegebene Aktualisierung durchläuft dann dieselbe Veröffentlichung wie der Plan: Sie aktualisiert das Board und die Issues, die Sie auswählen, löscht keines davon und generiert den Skill der Entwickler neu. Sobald ein Entwickler seine Projektdateien aktualisiert hat, meldet die nächste Prüfung dieses Arbeitspakets jede Änderung an den freigegebenen Eingaben und weist den Coding-Agenten an, seinen Plan neu zu bewerten. Eine laufende Coding-Unterhaltung wird nicht automatisch aktualisiert.',
        more: { label: 'Den Schritten im Leitfaden für Plan-Verantwortliche folgen.', href: '/docs/plan-owner-guide/#when-the-project-changes' },
      },
      {
        id: 'certify',
        group: 'carrydown',
        q: 'Bescheinigt carrydown, dass meine Dokumente richtig sind?',
        a: 'Nein. Die Faktengrundlage ist das, worauf sich Ihr Team geeinigt hat, und der Agent nimmt sie als gegeben. Was er hinzufügt, ist Prüfung. Er rendert jedes Dokument, hilft Ihnen mit Fragen bei der Durchsicht, und eine zweite Prüfung stellt den fertigen Plan seinen Quellen, seinen Randbedingungen und seinen Besetzungsentscheidungen gegenüber. Ist ein Dokument falsch, ist der Plan auf dieselbe Weise falsch, und die Korrektur gehört in das Dokument und nicht in den Plan.',
      },
      {
        id: 'one-person',
        group: 'method',
        q: 'Ist carried-context development für einen Ein-Personen-Spike gedacht?',
        a: 'Eher nicht. Die Methode lohnt sich, wenn mehrere Entwickler über Wochen an einer vereinbarten Architektur arbeiten und auseinanderdriftende Spezifikationen echte Zeit kosten. Für einen Ein-Personen-Spike sind Plan, Spezifikationen und Board mehr Struktur, als die Arbeit braucht. Besonders gut passt sie zu Unternehmensteams, bei denen Governance-Regeln, Entwicklungsstandards und Unternehmenskontext Teil der Faktengrundlage sind und mehrere Teams auf einer Architektur aufbauen. Nutzen Sie sie, wenn ein Team Arbeit an Coding-Agenten übergibt und jeder davon von denselben Entscheidungen ausgehen muss.',
      },
      {
        id: 'midway',
        group: 'carrydown',
        q: 'Kann ich carried-context development mit carrydown mitten in einem laufenden Projekt einführen?',
        a: 'Heute nicht als unterstützter Arbeitsablauf. carrydown unterstützt das Erstellen neuer Projektpläne, auch für neue Phasen bestehender Codebasen. Einen Umstellungsprozess, der ein bestehendes GitHub-Board und seine laufende Arbeit übernimmt, gibt es derzeit nicht.',
      },
      {
        id: 'governance',
        group: 'carrydown',
        q: 'Wie unterstützt carrydown die KI-Governance?',
        a: 'Governance-Regeln, Entwicklungsstandards und Unternehmenskontext gehen neben den technischen Dokumenten als Faktengrundlage ein, als Word, Markdown, Klartext oder geprüfte Auszüge aus PDF- und Bilddateien. Der Plan hält Version und Rang jeder Quelle fest, jedes Arbeitspaket zitiert die Abschnitte, die für es gelten, und die Prüfungen validieren diese Zitate beim Entwurf und noch einmal in einem frischen Klon. Der generierte Skill der Entwickler verweist jeden Coding-Agenten auf den freigegebenen Kontext, sodass der Agent die geltenden Regeln liest, bevor er Code plant. Sie prüfen die Entwürfe und geben nach Vorschau und Probelauf genau frei, was mit wem und wo geteilt wird, und Plan, Spezifikationen, Quellversionen und festgehaltene Entscheidungen bleiben in Ihrem Repository. Die automatischen Prüfungen und die zweite Prüfung halten Belege und Risiken fest, und ob die Arbeit die Anforderungen Ihrer Organisation erfüllt, beurteilt weiterhin Ihr Team.',
        more: { label: 'Lesen, wie carrydown die KI-Governance unterstützt.', href: '/docs/#how-does-carrydown-support-ai-governance' },
      },
      {
        id: 'withhold',
        group: 'carrydown',
        q: 'Kann ich mit carrydown bestimmten Kontext aus den Spezifikationen, dem Skill der Entwickler und den Coding-Agenten heraushalten?',
        a: 'Ja. Die Entwickler und ihre Coding-Agenten sehen immer nur den freigegebenen Kontext jedes Arbeitspakets: den genauen Quelltext, den das Paket zitiert, und die Entscheidungen dahinter, die Sie freigeben, bevor etwas veröffentlicht wird. Bevor der Agent etwas rendert oder kopiert, stellt er eine Frage: Dürfen alle, die dieses Repository lesen können, alle diese Dokumente und Ihre Besetzungsnotizen sehen? Bei Nein entwirft er in einem privaten Arbeitsbereich auf Ihrem Rechner, und das Repository erhält nur die Ergebnisse, die Sie freigeben, nie ein eingeschränktes Original oder dessen vollständige Wiedergabe. Jede Veröffentlichung zeigt Ihnen eine Vorschau dessen, was mit wem und wo geteilt wird, und einen Probelauf, bevor etwas geschrieben wird. Namen, freie Tage und Auslastung bleiben in einer privaten Datei und gelangen nie in den Plan, eine Spezifikation oder den Skill. Zwei Grenzen bleiben. Wer das Repository lesen kann, kann jeden freigegebenen Kontext lesen, ein Abschnitt lässt sich also nicht einem Entwickler zeigen und vor einem anderen verbergen, und Arbeit, die manche Leser nicht sehen dürfen, bleibt als eingeschränktes Paket aus der Veröffentlichung heraus. Und bereits ausgelieferter Text lässt sich nicht zurückrufen.',
        more: { label: 'In der Einrichtungsanleitung lesen, wer Ihre Dokumente sehen darf.', href: '/docs/setup/#before-you-add-documents-who-may-see-them' },
      },
      {
        id: 'watch',
        group: 'carrydown',
        q: 'Beobachtet carrydown meine Dokumente?',
        a: 'Nein. carrydown hat keine Dateiüberwachung und liest Ihr Dokumentensystem nie von sich aus. Eine Aktualisierung beginnt, wenn Sie sagen, was sich geändert hat, und das überarbeitete Material bereitstellen, und sie endet, wenn Sie die Durchsicht freigeben. Die Meilensteinprüfungen fordern die Plan-Verantwortlichen außerdem auf, Änderungen an Quellen, Anforderungen oder Randbedingungen zu melden.',
      },
      {
        id: 'agents',
        group: 'carrydown',
        q: 'Mit welchen Coding-Agenten arbeitet carrydown?',
        a: 'Jeder Coding-Agent, der Agent Skills unterstützt und Projektdateien lesen und bearbeiten sowie Befehle ausführen kann. Ihre Entwickler behalten den, den sie bereits nutzen. Der generierte Skill ist ein Ordner mit Anweisungen, den ihr Agent lädt, und er enthält keine Zugangsdaten. Die Einrichtungsanleitung listet die unterstützten Agenten und die Installationsschritte für jeden.',
        more: { label: 'Einen Coding-Agenten in der Einrichtungsanleitung wählen.', href: '/docs/setup/#choose-a-coding-agent' },
      },
      {
        id: 'tracker',
        group: 'carrydown',
        q: 'Kann ich Jira oder einen anderen Tracker verwenden?',
        a: 'Heute ist GitHub der Tracker. Jira, Azure Boards, GitLab und Linear sind offene Einladungen an die Community. In jedem Fall liegen der Plan, die Spezifikationen und der Skill der Entwickler als einfache Dateien in Ihrem Repository.',
        more: { label: 'Die offene Einladung auf GitHub lesen.', href: 'https://github.com/sct-will/carrydown/issues/1' },
      },
      {
        id: 'cost',
        group: 'carrydown',
        q: 'Was kostet es an KI-Nutzung?',
        a: 'Kosten meint hier die Modellnutzung Ihres Agenten, also den Text, den das KI-Modell liest und schreibt. Sie sind vom GitHub-Token getrennt. Die Planung liest die Dokumente und schreibt eine Spezifikation pro Arbeitspaket, daher wachsen ihre Kosten mit der Zahl der Arbeitspakete. Eine Aktualisierung liest das geänderte Material, einen kompakten Index aller Arbeitspakete und die vollständigen Spezifikationen der Kandidaten, die sie findet, und schreibt nur neu, was eine Korrektur braucht. Der Agent nennt die Größe dieses Index, bevor er bewertet. Die Zahlen sind Schätzungen, und eine weitreichende Regeländerung kann trotzdem weitreichendes Lesen erfordern. Wenn ein Entwickler ein Arbeitspaket beginnt, lädt der generierte Skill eine Spezifikation und die zitierten Abschnitte, nicht das ganze Dokument. Die Beschreibungen der beiden Skills bleiben kurz, damit sie in die Liste jeder Sitzung passen.',
      },
      {
        id: 'does-not',
        group: 'carrydown',
        q: 'Wo hört carrydown auf?',
        a: 'carrydown entwirft den Plan und die Spezifikationen, prüft sie und veröffentlicht, was Sie freigeben. Die Entscheidungen bleiben bei Menschen, und der Anwendungscode auch.',
        /** The literal text --apply is set in a monospace face wherever it appears. */
        list: [
          'Es schreibt keinen Anwendungscode.',
          'Jeder Schreibzugriff auf GitHub ist ein Probelauf, bis Sie --apply angeben.',
          'Es löscht nie Issues, Labels, Projekte oder Repositories.',
          'Der Aktualisierungsvergleich läuft auf Ihrem Rechner. Kein Netzwerk, kein Token, kein Modellaufruf.',
          'Eine Aktualisierung prüft die Arbeit, die sie beobachten kann, und meldet, was sie nicht beobachten konnte. Sie behauptet nicht, jedes betroffene Element zu finden.',
          'Vertrauliche Dokumente bleiben auf Ihrem Rechner, es sei denn, Sie sagen, dass alle sie sehen dürfen.',
          'Namen, freie Tage und Zuteilung bleiben in einer privaten Datei, nie im Plan.',
          'Wenn Sie aufhören, behalten Sie reines Markdown und gewöhnliche GitHub-Issues.',
        ],
      },
      {
        id: 'license',
        group: 'carrydown',
        q: 'Welche Lizenz hat carrydown?',
        a: 'Apache 2.0, für die Skills, die Skripte und die Vorlagen. Das Repository enthält die Sicherheitsrichtlinie, das Änderungsprotokoll und die Antworten auf häufige Sicherheitsfragen von Unternehmen, jede mit dem Vermerk unterstützt, unterstützt mit Voraussetzungen oder geplant.',
        more: { label: 'Das Repository auf GitHub öffnen.', href: 'https://github.com/sct-will/carrydown' },
      },
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
      'Text- und Oberflächenfarben werden auf Kontrast geprüft.',
      'Jede Seite funktioniert allein mit der Tastatur, mit sichtbarem Fokusindikator und einem Link zum Überspringen zum Hauptinhalt.',
      'Das Diagramm ist aus Text und Vektorformen gezeichnet. Es skaliert und trägt eine schriftliche Beschreibung für Screenreader.',
      'Animationen und Seitenübergänge schalten sich ab, wenn Ihr System auf reduzierte Bewegung eingestellt ist. Kurze Farb- und Unterstreichungswechsel an Links und Schaltflächen bleiben, ebenso die Drehung eines Pfeils in der Seitenleiste der Dokumentation.',
      'Überschriften, Landmarken und Linktexte sind so geschrieben, dass man sie der Reihe nach und aus dem Zusammenhang gelöst lesen kann.',
      'Die Website wird vor jeder Veröffentlichung mit automatisierten Werkzeugen geprüft und von Hand mit einem Screenreader begutachtet.',
    ],
    notFinishedHeading: 'Was noch nicht fertig ist',
    notFinished:
      'Die Übersetzungen der Website werden von Muttersprachlern geprüft und gehen Sprache für Sprache online. Die Dokumentationsseiten sind noch nicht übersetzt. Jede Sprache zeigt die englische Seite mit einem Hinweis. Diese Seiten werden aus dem Markdown des Repositorys erzeugt, daher sind ihre Diagramme und Screenshots Rasterbilder mit schriftlicher Beschreibung.',
    contactHeading: 'Melden Sie uns ein Problem',
    contactBefore:
      'Wenn etwas auf dieser Website mit assistiven Technologien schwer zu bedienen ist oder Sie die Inhalte in einer anderen Form brauchen, schreiben Sie an ',
    contactAfter: '. Nennen Sie die Seite und was passiert ist. Sie sollten innerhalb von zehn Arbeitstagen eine Antwort erhalten.',
    review:
      'Diese Erklärung beschreibt die Absicht der Website und ihren aktuellen Stand. Sie wird überprüft, wenn sich die Website ändert. Zuletzt geprüft am 27. November 2026.',
  },

  home: {
    title: 'Carried context, eine Faktengrundlage für jeden Coding-Agenten',
    description:
      'Carried-context development ist ein Ansatz für agentische Entwicklung, der Projektentscheidungen und Kontext bis zum Coding-Agenten jedes Entwicklers trägt und so hilft, Spezifikationen und Coding-Agenten aufeinander abgestimmt zu halten, während sich das Projekt ändert.',
    h1: 'Carried-context development gibt jedem Coding-Agenten die Entscheidungen und Quellen hinter der Arbeit.',
    /** The part of the title set in amber, a styling choice a native reviewer may move or empty. */
    h1Emphasis: 'Entscheidungen und Quellen',
    definition:
      'Ihr KI-Agent erstellt aus Ihren vereinbarten Projektdokumenten einen verbundenen Plan und die Spezifikationen. Ein projektspezifischer Skill weist jeden Coding-Agenten an, seine freigegebene Spezifikation und die zitierten Quellenabschnitte zu lesen, bevor er Code plant.',
    paragraph:
      'Carried-context development ist ein Ansatz für agentische Entwicklung. Ihr Team liefert die Projektdokumente, die Anforderungen und die Entscheidungen zu Personen und Terminen. Ihr KI-Agent nutzt diese Faktengrundlage, um einen verbundenen Plan, eine Spezifikation für jedes Arbeitspaket und GitHub-Issues zu erstellen, die jede Spezifikation verlinken und die dahinterstehenden Dokumentabschnitte belegen. Ihr KI-Agent generiert außerdem einen projektspezifischen Agent Skill, der die Spezifikation, die Entscheidungen dahinter und die belegten Abschnitte zum Coding-Agenten jedes Entwicklers trägt. Wenn sich ein Dokument ändert, prüfen Sie eine einzige Aktualisierung.',
    buttons: {
      try: 'Hier starten',
    },
    sampleLink: 'Sehen Sie, was ein Agent für ein Beispielprojekt erstellt hat',
    /** A small line under the buttons. */
    license: 'Open Source unter Apache 2.0.',
    howHeading: 'So funktioniert es',
    /** The last sentence under How it works; the middle word is the link to the README section. */
    learnMore: { before: 'Mehr dazu ', link: 'hier', after: '.' },
    sideParagraphs: [
      'Wenn sich das Projekt ändert, legt Ihr Agent Aktualisierungen der betroffenen Arbeit zur Freigabe vor.',
    ],
    values: [
      {
        eyebrow: 'Verbundener Plan',
        title: 'Projektentscheidungen bleiben über alle Spezifikationen hinweg verbunden.',
        body: 'Ihr Agent erstellt den Plan und die Spezifikationen aus denselben vereinbarten Dokumenten und Entscheidungen. Abhängigkeiten, gemeinsame Schnittstellen und Abnahmekriterien werden zusammen auf Lücken und Widersprüche geprüft. Prüfungen validieren die Quellenbelege.',
      },
      {
        eyebrow: 'Übergabe an die Entwicklung',
        title: 'Entscheidungen und Quellen erreichen jeden Coding-Agenten.',
        body: 'Ein für Ihr Projekt generierter Skill weist den Coding-Agenten jedes Entwicklers an, die freigegebene Spezifikation, die zitierten Quellenauszüge und die Projektkonventionen zu lesen, bevor er Code plant. Jedes Issue verlinkt seine Spezifikation, sodass auch die Entwickler den Kontext prüfen können.',
      },
      {
        eyebrow: 'Projektkontext synchron gehalten',
        title: 'Halten Sie die Übergabe abgestimmt, wenn sich das Projekt ändert.',
        body: 'Sagen Sie dem Agenten, mit dem Sie planen, Bescheid, wenn sich eine Quelle ändert oder eine Spezifikation falsch erscheint. Er ermittelt die Arbeit, die betroffen sein kann, und behält Korrekturen der Entwickler, die noch passen. Sie entscheiden, wie Konflikte gelöst werden, und geben Aktualisierungen der Spezifikationen, der Issues und des Kontexts der Coding-Agenten frei.',
      },
    ],
    carrydown: {
      heading: 'Probieren Sie es aus',
      intro:
        'Es gibt mehr als einen Weg, carried-context development umzusetzen. carrydown ist die Referenzimplementierung: zwei Agent Skills, die Sie installieren, ein dritter, den sie für Ihre Entwickler generiert, und die Prüfungen, die jeden Beleg validieren. Sie ist Open Source unter Apache 2.0 und arbeitet mit dem Coding-Agenten, den Ihr Team bereits nutzt.',
      tiles: [
        {
          step: 'Schritt 1',
          title: 'Einen fertigen Beispielplan ansehen.',
          body: 'Ein Rundgang durch das, was der Agent generiert hat, mit einem Link zu jedem Artefakt auf GitHub.',
          command: '',
          button: 'Sehen Sie, was ein Agent für ein Beispielprojekt erstellt hat',
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
        { title: 'Ein Plan, den Sie als Seite in Ihrem Webbrowser prüfen', path: '', body: 'Meilensteine, Tracks, Verantwortliche und Termine, an Ihre Leute und Ihre Zeit angepasst, mit einer Lasttabelle und einem kritischen Pfad und einer Begründung für jeden Meilenstein. Der eingecheckte Plan, docs/spec/plan.yaml, enthält nur Ids und Tracks.' },
        { title: 'Der KI-Agent-Skill des Entwicklers', path: '', body: 'Aus Ihren Spezifikationen generiert und in Ihrem Repository committet. Ein Entwickler startet ein Arbeitspaket, indem er es nennt, zum Beispiel „Work on [work item ID]“, und der Coding-Agent liest zuerst die Spezifikation und den freigegebenen Kontext dieses Pakets.' },
        { title: 'Eine Spezifikation pro Arbeitspaket', path: '', body: 'Das kleinste Stück Arbeit, das ein Entwickler abschließen und vorführen kann, mit Belegen auf seine Abschnitte und bei jedem Pull Request gegen den Plan geprüft.' },
        { title: 'Ein freigegebener Kontext pro Arbeitspaket', path: 'docs/context/', body: 'Der genaue Quelltext der belegten Abschnitte und die Entscheidungen dahinter, von Ihnen freigegeben. Der einzige Teil Ihrer Dokumente, der die Agenten der Entwickler erreicht.' },
        { title: 'Eine Release-Quittung', path: 'docs/release/', body: 'Eine kleine öffentliche Datei, die das freigegebene Release, seinen Zustand und sein Ablaufdatum nennt.' },
        { title: 'Ein Bericht der zweiten Prüfung', path: '', body: 'Abdeckung, Belege, Begründung und Risiko, mit Ihren Entscheidungen und den Prüfungen der angenommenen Korrekturen.' },
        { title: 'GitHub-Issues', path: '', body: 'Eines pro Arbeitspaket unter einem Sub-Epic pro Meilenstein, und jedes sagt dem Agenten des Entwicklers, was er lesen soll.' },
        { title: 'Ein GitHub-Projektboard', path: '', body: 'Arbeitseinheiten, Tracks, Termine und Checkpoints ausgefüllt.' },
      ],
    },
  },

  /** The sample page, /sample/. Same shape as en.ts. The excerpts, commands, paths and identifiers
   * are in src/lib/sample-excerpts.mjs and stay in English. */
  sample: {
    title: 'Ein Beispielprojekt, carried-context development',
    description: 'Ein fiktives Projekt für Spesenfreigaben: Firma, Personen und Termine sind erfunden, und nichts ist implementiert. Der Plan-Verantwortliche lieferte ein Architekturdokument und zwei Besetzungsdateien, prüfte den Plan und gab ihn frei.',
    eyebrow: 'Das Beispiel',
    h1: 'Sehen Sie, wie Kontext aus der Faktengrundlage durch ein ganzes Beispielprojekt getragen wird.',
    lede: 'Ein fiktives Projekt für Spesenfreigaben: Firma, Personen und Termine sind erfunden, und nichts ist implementiert. Der Plan-Verantwortliche lieferte ein Architekturdokument und zwei Besetzungsdateien, prüfte den Plan und gab ihn frei.',
    primary: 'Das Beispiel auf Ihrem Rechner ausführen',
    ready: 'Bereit zum Start?',
    readyLink: 'carrydown in Ihrem Projekt ausführen',
    callout: 'Alle sechs unten aufgeführten Artefakte hat eine KI im carrydown-Ablauf generiert.',
    previewsNote: 'Jede Vorschau ist ein echter Auszug, eine gekennzeichnete Zusammenfassung oder Kürzung oder das veröffentlichte Bild des Boards.',
    notice: 'Worauf achten',
    labels: {
      milestones: 'Auszug aus den Meilensteinen, Begründung gekürzt',
      excerpt: 'Auszug',
      abridged: 'Auszug, gekürzt',
      board: 'Das veröffentlichte Bild des Boards',
    },
    boardAlt: 'Die Tabellenansicht des Beispielprojekts auf GitHub, nach Arbeitseinheit gruppiert. Jede Gruppe listet ihre Arbeitspakete mit den Spalten Track, Complete by und Checkpoint.',
    tiles: [
      {
        key: 'plan',
        title: 'Den freigegebenen Plan ansehen',
        value: 'Damit prüfen Sie einen Zeitplan, der zu Ihren Leuten und Ihrer Zeit passt: Meilensteine, Tracks, Verantwortliche und Termine, mit einer schriftlichen Begründung für jeden Meilenstein.',
        what: 'Sie prüfen ihn als Seite im Browser und bitten im Gespräch um Änderungen. Das Repository enthält nur Ids und Tracks.',
        note: 'In einem echten Projekt bleiben die Besetzungsangaben auf dem Rechner des Verantwortlichen. Dieses Beispiel veröffentlicht erfundene.',
        notice: [
          'Jeder Meilenstein sagt in einem Satz, was das Team gemeinsam vorführen muss. Daran lässt es sich messen.',
          'Eine schriftliche Begründung für die Reihenfolge. Routing und Posteingang sind zwei Hälften einer Fähigkeit und teilen sich deshalb einen Meilenstein.',
          'Nur Ids und Tracks. Namen und freie Tage gelangen nie ins Repository.',
        ],
      },
      {
        key: 'specification',
        title: 'Eine Spezifikation mit ihren Quellen ansehen',
        value: 'Damit geben Sie jedem Entwickler das kleinste Stück Arbeit, das er abschließen und vorführen kann, mit Belegen auf die Abschnitte, aus denen es stammt.',
        what: 'Eine pro Arbeitspaket: warum es existiert, der Vertrag, Abnahmekriterien und ein Platz für Entscheidungen. Ein Skript prüft sie gegen den Plan, und in der Continuous Integration läuft es erneut auf einem frischen Klon.',
        note: '',
        notice: [
          'Die Referenzen nennen die Quellenabschnitte, denen dieses Paket folgt.',
          'Der Vertrag zitiert die Erinnerungsregel, und das Abnahmekriterium macht daraus einen benannten Test. Dieselbe Regel an beiden Stellen.',
          'Hängt von WI-01 ab und gibt drei Pakete frei. So hängt verwandte Arbeit zusammen.',
        ],
      },
      {
        key: 'context',
        title: 'Den freigegebenen Kontext ansehen, den ein Agent zuerst liest',
        value: 'Damit entscheiden Sie genau, welcher Text aus Ihren Dokumenten die Agenten der Entwickler erreicht: die Abschnitte, die jedes Arbeitspaket belegt, und sonst nichts.',
        what: 'Dazu die Entscheidungen, die Widersprüche zwischen Quellen klären, und wofür der Text verwendet werden darf. Eine Prüfung verifiziert ihn, bevor der Agent plant.',
        note: '',
        notice: [
          'Hier stehen nur die vier Abschnitte, die WI-03 belegt. Sonst nichts aus dem Dokument.',
          'Ein Widerspruch und seine Klärung. Die Finanzabteilung wollte 2 Tage, das Dokument sagt 3, und der Agent liest „use 3“, statt zu raten.',
          'Wofür der Text verwendet werden darf: Code und Tests, kein Issue-Text.',
        ],
      },
      {
        key: 'skill',
        title: 'Den generierten Agent Skill ansehen',
        value: 'Damit starten Ihre Entwickler ein Arbeitspaket mit einem Satz: ein Skill, aus Ihren Spezifikationen generiert und in Ihrem Repository committet.',
        what: 'Einmal installiert. „Work on WI-03“ lässt den Coding-Agenten den freigegebenen Kontext und die Spezifikation dieses Pakets prüfen und lesen, bevor er Code anfasst.',
        note: '',
        notice: [
          'Die Prüfung ist der erste Befehl für jedes Arbeitspaket. Erst wenn sie besteht, liest der Agent den freigegebenen Kontext.',
          'Der Agent öffnet das Quelldokument nie. Der freigegebene Kontext ist für das Paket vollständig.',
          'Haben sich die freigegebenen Eingaben seit der letzten Prüfung geändert, liest der Agent sie neu und überdenkt seinen Plan.',
        ],
      },
      {
        key: 'issues',
        title: 'Die Issues ansehen, die der Agent erstellt hat',
        value: 'Damit verfolgen Sie jedes Arbeitspaket dort, wo Ihr Team schon arbeitet, und jedes Issue sagt dem Agenten des Entwicklers, was er lesen soll.',
        what: 'Ein Epic, fünf Sub-Epics und neun Arbeitspakete, jedes mit Zieltermin, Checkpoint und den Gründen, warum es existiert.',
        note: '',
        notice: [
          'Der Abschnitt „AI engineering notes“ verlinkt die Spezifikation und den Skill und sagt, was Sie Ihrem Agenten sagen.',
          'Die Zeile „Ground truth“ nennt dieselben Abschnitte wie die Spezifikation.',
          '„Depends on WI-01“ verlinkt das Issue, auf das dieses wartet.',
        ],
      },
      {
        key: 'project',
        title: 'Das GitHub-Projekt ansehen',
        value: 'Damit steuern Sie den Plan in dem Werkzeug, das Ihr Team schon nutzt, mit ausgefüllten Arbeitseinheiten, Tracks, Terminen und Checkpoints.',
        what: 'Nach Arbeitseinheit gruppiert. Jedes Arbeitspaket verlinkt seine Spezifikation, den Skill der Entwickler und die Abschnitte, die es belegt.',
        note: '',
        notice: [
          'Nach Arbeitseinheit gruppiert, mit ihren Terminen. Die Meilensteinzeile steht bei ihren Arbeitspaketen.',
          'Track, Complete by und Checkpoint stammen aus dem Plan. Niemand hat sie eingetippt.',
        ],
      },
    ],
    changeHeading: 'Vom Agenten generierte Artefakte werden aktualisiert, wenn sich etwas ändert.',
    change: {
      title: 'Einer Änderung durch das Projekt folgen',
      value: 'Damit ändern Sie das Dokument und geben die Aktualisierung frei, bevor etwas veröffentlicht wird. Die betroffene Arbeit bewertet der Agent für Sie.',
      what: 'Das Dokument bekam eine neue Regel. Der Agent schlug Aktualisierungen für die Routing-Engine und den davon abhängigen Posteingang vor, zwei Entwürfe von Spezifikationen, und der Verantwortliche nahm beide in einer Durchsicht an.',
      notice: [
        'Der Posteingang belegte den geänderten Abschnitt nie und wurde trotzdem aktualisiert. Er hängt von der Routing-Engine ab, und der Agent folgte der Abhängigkeit.',
        'Drei weitere Pakete belegen den Abschnitt. Der Agent las sie, fand keinen Widerspruch und ließ sie, wie sie waren.',
        'Der Verantwortliche nahm beide Entwürfe in einer Durchsicht an. Bis dahin wird nichts veröffentlicht.',
      ],
      addedRule: 'hinzugefügte Regel',
      items: [
        'Vertragsregel und Abnahmekriterium hinzugefügt (abgedruckt)',
        'Abnahmekriterium hinzugefügt (Zusammenfassung, Wortlaut nicht abgedruckt)',
      ],
      status: 'Aufgezeichnete lokale Übung · Angenommene Entwürfe warten auf das Release',
    },
    trial: {
      heading: 'Das Beispiel auf Ihrem Rechner ausführen',
      intro: 'Git, Python 3.9 oder neuer, ein Coding-Agent, der Dateien liest und Befehle ausführt, und Netzwerkzugang für die erste Prüfung. Für diesen Test mit dem öffentlichen Beispiel brauchen Sie weder ein GitHub-Konto noch ein Token zum Veröffentlichen.',
      lead: 'Ihr eigener Coding-Agent. Kein GitHub-Konto und kein Token zum Veröffentlichen für diesen Test mit dem öffentlichen Beispiel. Die letzte Zeile weist den Agenten an, vor jeder Implementierung anzuhalten.',
      steps: [
        { label: 'Das Beispiel holen', copyLabel: 'Den Klonbefehl kopieren' },
        { label: 'In diesem Ordner arbeiten', copyLabel: 'Den Ordnerbefehl kopieren' },
        { label: 'Den Skill der Entwickler laden, auf eine von zwei Arten', copyLabel: 'Den Installationsbefehl kopieren' },
        { label: 'Dies zum Agenten sagen', copyLabel: 'Den Satz kopieren, den Sie sagen' },
      ],
      folderNote: 'Öffnen Sie denselben Ordner in Ihrem Coding-Agenten als Arbeitsordner.',
      installNote: 'Das Installationsprogramm braucht Node.js 22.20 oder neuer. Starten Sie danach eine neue Agentensitzung.',
      readInstead: { before: 'Oder bitten Sie den Agenten ohne Installation,', after: 'zu lesen und zu befolgen.' },
      copy: 'Kopieren',
      copied: 'Kopiert',
      copyOk: 'In die Zwischenablage kopiert.',
      copyFail: 'Kopieren nicht möglich. Markieren Sie den Text und kopieren Sie ihn.',
      expected: 'Erwartete Ausgabe, wenn die Prüfung besteht',
      installHelp: 'Probleme bei der Installation',
      checkHelp: 'Wenn die Prüfung nicht besteht',
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
