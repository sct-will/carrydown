// Spanish strings. Same shape as en.ts, so the compiler flags a missing key. Brand names, the term
// "Carried-context development" and the quoted agent commands stay in English. A native speaker has
// not reviewed this translation yet, and every translated page says so.
import { en, type Strings } from './en';

export const es: Strings = {
  lang: 'es',
  dir: 'ltr',
  label: 'Español',

  site: {
    name: 'Carried-context development',
    skipLink: 'Saltar al contenido principal',
    homeLabel: 'Carried-context development, inicio',
  },

  nav: {
    label: 'Principal',
    definition: 'Definición',
    github: 'GitHub',
    docs: 'Docs',
    faq: 'FAQ',
    accessibility: 'Declaración de accesibilidad',
    menu: 'Menú',
    docsMenu: 'Menú de docs',
  },

  controls: {
    themeLabel: 'Tema',
    themeAuto: 'Auto',
    themeDark: 'Oscuro',
    themeLight: 'Claro',
    languageLabel: 'Idioma',
  },

  search: {
    button: 'Buscar',
    title: 'Buscar en este sitio',
    close: 'Cerrar',
    unavailable: 'La búsqueda funciona en el sitio publicado. No está disponible en la vista previa de desarrollo.',
  },

  translation: {
    note: 'Esta traducción está pendiente de revisión por un hablante nativo. La página en inglés es la referencia.',
    link: 'Leer la página en inglés',
  },

  footer: {
    label: 'Pie de página',
    copyright: en.footer.copyright,
  },

  definition: {
    title: 'Carried-context development, definición',
    description:
      'Carried-context development lleva la verdad de referencia acordada por un equipo hasta el plan, cada especificación, cada incidencia y las instrucciones de cada agente de programación, citada por sección, y la lleva de nuevo cuando cambia.',
    h1: 'Carried-context development',
    status: ['Estado: método abierto', 'Versión 1.0', 'Noviembre de 2026', 'Will Scott, PhD'],
    contents: 'Contenido',
    sections: [
      'Definición',
      'Las reglas',
      'En qué se diferencia del desarrollo guiado por especificaciones',
      'Implementación de referencia',
      'Cómo citar',
      'Registro de cambios',
    ],
    definition:
      'Carried-context development lleva la verdad de referencia acordada por un equipo hasta el plan, cada especificación, cada incidencia y las instrucciones de cada agente de programación, citada por sección, y la lleva de nuevo cuando cambia.',
    rules: [
      {
        title: 'Una sola verdad de referencia.',
        body: 'Los documentos que el equipo acordó son la única entrada escrita por personas. Todo lo posterior se deriva de ellos, y nada posterior está por encima de ellos.',
      },
      {
        title: 'Ajustado a personas y fechas reales.',
        body: 'El plan se construye en torno a quién está disponible, cuánto de su tiempo y cuándo vence. Si se da una cosa, la otra se deriva.',
      },
      {
        title: 'Una especificación por elemento de trabajo.',
        body: 'Un elemento de trabajo es la pieza de trabajo más pequeña que un ingeniero puede terminar y mostrar. Cada uno tiene su propia especificación.',
      },
      {
        title: 'Citado por sección.',
        body: 'Cada especificación, incidencia e instrucción nombra las secciones de la verdad de referencia de las que procede. Una comprobación valida cada cita, desde un clon limpio.',
      },
      {
        title: 'Aprobado, no generado.',
        body: 'Una persona decide responsables, fechas, alcance y orden, aprueba qué se puede compartir y con quién, y aprueba lo que se publica. Nada se publica sin un sí.',
      },
      {
        title: 'Llevado hasta el agente.',
        body: 'El agente de programación del ingeniero lee la especificación y las secciones citadas antes de planificar una línea de código.',
      },
      {
        title: 'Llevado de nuevo ante un cambio.',
        body: 'Cuando cambia la verdad de referencia, una sola revisión encuentra el trabajo afectado y conserva las correcciones de los ingenieros. La actualización aprobada llega hasta cada elemento de trabajo.',
      },
    ],
    differs:
      'El desarrollo guiado por especificaciones deja cada especificación al ingeniero que la escribe. La calidad depende de quién la escribió. No hay dos especificaciones iguales y nada las une. Se desvían a medida que el proyecto cambia. Carried-context development deriva cada especificación de la misma verdad de referencia, revisa las especificaciones en conjunto, cita las fuentes y lleva cada cambio aprobado a cada agente de programación. La ingeniería de contexto, una vecina, decide lo que ve un modelo en un paso; el contexto llevado decide lo que debe cumplir todo el proyecto.',
    compare: {
      aspect: 'Aspecto',
      specDriven: 'Desarrollo guiado por especificaciones',
      carried: 'Carried-context development',
      rows: [
        ['Unidad de planificación', 'Una tarea o función', 'El proyecto completo'],
        ['Qué viaja', 'La especificación', 'La verdad de referencia, citada por sección'],
        [
          'Cuando cambian las fuentes',
          'Reescribir la especificación',
          'Una revisión. Se conservan las correcciones de los ingenieros',
        ],
        [
          'Quién escribe la especificación',
          'El ingeniero',
          'Derivada por el agente de IA de la verdad de referencia, revisada por el responsable del plan',
        ],
        [
          'Coherencia entre especificaciones',
          'Ninguna impuesta',
          'Revisadas en conjunto, cada cita comprobada',
        ],
        ['Quién decide', 'El desarrollador', 'El responsable del plan, los ingenieros, las partes interesadas'],
      ],
    },
    reference: {
      body: 'carrydown, dos Agent Skills y un tercero generado, Apache 2.0, primer commit el 24 de octubre de 2026.',
      link: 'github.com/sct-will/carrydown',
    },
    cite: {
      heading: 'Cómo citar',
      text: en.definition.cite.text,
      bibtex: en.definition.cite.bibtex,
    },
    changelog: '1.0, noviembre de 2026. Primera publicación.',
  },

  faq: {
    title: 'Preguntas, carried-context development',
    description:
      'Respuestas breves sobre carried-context development y carrydown, y sobre lo que carrydown no hace.',
    h1: 'Preguntas',
    intro: 'Respuestas breves, con enlaces a la documentación donde hay más.',
    items: [
      {
        q: '¿Certifica que mis documentos son correctos?',
        a: 'No. Parte de lo que usted aporta y le ayuda a revisarlo.',
      },
      {
        q: '¿Sirve para una prueba de una sola persona?',
        a: 'No realmente. Compensa cuando varios ingenieros comparten semanas de trabajo con una arquitectura acordada.',
      },
      { q: '¿Vigila mis documentos?', a: 'No. Una actualización empieza cuando usted dice qué cambió.' },
      {
        q: '¿Qué agentes de programación?',
        a: 'Cualquier agente de programación que admita Agent Skills. Sus ingenieros conservan el que usan.',
      },
      {
        q: '¿Qué licencia?',
        a: 'Apache 2.0. La política de seguridad, el registro de cambios y las respuestas a las preguntas de seguridad habituales de las empresas están en el repositorio.',
      },
    ],
    doesNotHeading: 'Lo que carrydown no hace',
    doesNot: [
      'No escribe código de aplicación.',
      'Cada escritura en GitHub es un ensayo hasta que usted pasa --apply.',
      'Nunca borra incidencias, etiquetas, proyectos ni repositorios.',
      'La comparación de actualización se ejecuta en su equipo. Sin red, sin token, sin llamada a un modelo.',
      'Los documentos confidenciales permanecen en su equipo salvo que usted diga que todos pueden verlos.',
      'Los nombres, los días libres y la asignación quedan en un archivo privado, nunca en el plan.',
      'Si lo deja, conserva Markdown simple e incidencias normales de GitHub.',
    ],
  },

  accessibility: {
    title: 'Declaración de accesibilidad',
    description:
      'Este sitio está pensado para que lo pueda usar todo el mundo. Aspira a cumplir las Web Content Accessibility Guidelines (WCAG) 2.2 en el nivel AA.',
    h1: 'Declaración de accesibilidad',
    intro:
      'Este sitio está pensado para que lo pueda usar todo el mundo, incluidas las personas que usan un lector de pantalla, solo el teclado, ampliación o movimiento reducido. Aspira a cumplir las Web Content Accessibility Guidelines (WCAG) 2.2 en el nivel AA.',
    doneHeading: 'Lo que se ha hecho',
    done: [
      'Los colores del texto y de la interfaz se comprueban en cuanto a contraste en los temas claro y oscuro, y puede elegir cualquiera de los dos o seguir su sistema.',
      'Cada página funciona solo con el teclado, con un indicador de foco visible y un enlace para saltar al contenido principal.',
      'El diagrama está dibujado con texto y formas vectoriales, así que se escala, respeta su tema y lleva una descripción escrita para lectores de pantalla.',
      'Nada en el sitio se mueve por sí solo. Cualquier animación futura respetará el ajuste de movimiento reducido y ofrecerá una imagen fija.',
      'Los encabezados, los puntos de referencia y los textos de los enlaces están escritos para leerse en orden y fuera de contexto.',
      'El sitio se comprueba con herramientas automáticas antes de cada versión y se revisa a mano con un lector de pantalla.',
    ],
    notFinishedHeading: 'Lo que no está terminado',
    notFinished:
      'Las traducciones del sitio las están revisando hablantes nativos y se publican un idioma cada vez. La sección de documentación se genera a partir del repositorio y puede ir por detrás del resto del sitio en estos puntos hasta que se compruebe cada versión.',
    contactHeading: 'Cuéntenos un problema',
    contactBefore:
      'Si algo en este sitio es difícil de usar con tecnología de apoyo, o necesita el contenido en otra forma, escriba a ',
    contactAfter: '. Indique qué página y qué ocurrió. Debería recibir respuesta en diez días laborables.',
    review:
      'Esta declaración describe la intención del sitio y su estado actual. Se revisa cuando el sitio cambia. Última revisión el 16 de noviembre de 2026.',
  },

  home: {
    title: 'Carried-context development, inicio',
    description:
      'Carried-context development es un enfoque de desarrollo con agentes que lleva las decisiones y el contexto del proyecto hasta el agente de programación de cada ingeniero, para que el proyecto siga alineado y nada se desvíe.',
    h1: [
      'Carried-context development va más allá del desarrollo guiado por especificaciones.',
      'El contexto viaja con el trabajo.',
    ],
    definition:
      'Mantenga el proyecto alineado dando al agente de programación de cada ingeniero las mismas decisiones y el mismo contexto del proyecto.',
    paragraph:
      'Su equipo aporta los documentos del proyecto, los requisitos y las decisiones sobre personas y plazos. Su agente de IA usa esta verdad de referencia para crear un plan conectado, una especificación por cada elemento de trabajo e incidencias de GitHub que enlazan cada especificación y citan las secciones de los documentos en que se basa. Su agente de IA también genera un agent skill específico del proyecto que lleva la especificación, las decisiones que la sustentan y las secciones citadas hasta el agente de programación de cada ingeniero. Cuando cambia un documento, usted revisa una sola actualización.',
    buttons: {
      try: 'Probarlo en GitHub',
      sample: 'Ver los resultados del agente de IA de un proyecto de ejemplo',
    },
    howHeading: 'Cómo funciona',
    sideParagraphs: [
      'Cuando los ingenieros escriben las especificaciones por separado, la calidad varía y las especificaciones se desvían a medida que el proyecto cambia.',
      'Carried-context development vincula cada especificación a la misma verdad de referencia, cita las fuentes y entrega cada cambio aprobado a cada agente de programación.',
    ],
    values: [
      {
        eyebrow: 'Plan conectado',
        title: 'Planificado como un todo conectado.',
        body: 'Un solo plan y todas las especificaciones salen de la misma verdad de referencia. Las dependencias, las interfaces y los criterios de aceptación se revisan en conjunto para detectar huecos y conflictos, y una comprobación valida cada cita.',
      },
      {
        eyebrow: 'Traspaso a ingeniería',
        title: 'Un traspaso que llega al agente de programación.',
        body: 'Cada incidencia enlaza su especificación y cita sus secciones de la verdad de referencia. Un agent skill específico del proyecto pone la especificación aprobada, esas secciones y sus convenciones ante el agente de programación antes de que planifique código.',
      },
      {
        eyebrow: 'Contexto del proyecto sincronizado',
        title: 'Los cambios que plantea el líder del proyecto o los ingenieros se propagan.',
        body: 'Un líder de proyecto informa de una fuente modificada, o un ingeniero señala una especificación errónea. El agente encuentra el trabajo afectado, conserva las correcciones que siguen valiendo y le presenta los conflictos. Las actualizaciones aprobadas fluyen por las especificaciones, las incidencias y el traspaso.',
      },
    ],
    carrydown: {
      heading: 'Pruébelo',
      intro:
        'Carried-context development es un enfoque de desarrollo con agentes, y hay más de una forma de implementarlo. carrydown es la implementación de referencia: dos Agent Skills que usted instala, un tercero que genera para sus ingenieros y las comprobaciones que validan cada cita. Es de código abierto bajo Apache 2.0 y funciona con el agente de programación que su equipo ya usa.',
      tryButton: 'Probarlo en GitHub',
      installCommand: en.home.carrydown.installCommand,
      copy: 'Copiar',
      copied: 'Copiado',
      copyLabel: 'Copiar el comando de instalación',
      copiedStatus: 'Comando de instalación copiado al portapapeles.',
      copyFailedStatus: 'No se pudo copiar. Seleccione el comando y cópielo.',
      tiles: [
        {
          step: 'Paso 1',
          title: 'Mire un ejemplo de plan terminado.',
          body: 'El tablero de ejemplo y sus incidencias, en GitHub.',
          command: '',
          button: 'Abrir el ejemplo',
        },
        {
          step: 'Paso 2',
          title: 'Ejecute carrydown en su proyecto.',
          body: 'Instale los dos skills de carrydown y luego diga',
          command: en.home.carrydown.tiles[1].command,
          button: 'Guía de instalación',
        },
      ],
      stepsHeading: 'Su agente de IA le guía para usar carrydown en su proyecto',
      steps: [
        {
          who: 'Responsable del plan',
          what: 'Instala los dos skills de carrydown y empieza el plan.',
          say: en.home.carrydown.steps[0].say,
        },
        {
          who: 'Responsable del plan',
          what: 'Revisa el plan y las especificaciones, y luego publica.',
          say: en.home.carrydown.steps[1].say,
        },
        {
          who: 'Cada ingeniero',
          what: 'Instala una vez el agent skill generado y nombra un elemento de trabajo.',
          say: en.home.carrydown.steps[2].say,
        },
        {
          who: 'Partes interesadas',
          what: 'Informan de una fuente modificada o de una especificación que parece errónea. Una revisión, y la actualización aprobada se propaga.',
          say: en.home.carrydown.steps[3].say,
        },
      ],
      reviewNote: 'Las partes interesadas, los responsables del proyecto y los responsables de ingeniería ven cada hito y deciden si se supera o no. La revisión humana es explícitamente parte del método.',
    },
  },

  diagram: {
    ariaLabel:
      'El contexto de proyecto que usted aporta, documentos, decisiones y más tarde un cambio, alimenta al agente de IA. Este genera para su equipo un plan de proyecto para revisar y aprobar, una especificación por cada elemento de trabajo, un tablero de GitHub con incidencias e hitos donde cada incidencia enlaza su especificación y cita sus fuentes, y un agent skill específico del proyecto que cada ingeniero instala una vez y usa con un agente de programación.',
    provideHeading: 'Contexto que usted aporta',
    generatesHeading: 'El agente de IA genera para su equipo',
    documents: 'Documentos',
    documentsNote: 'arquitectura, requisitos, reglas',
    decisions: 'Decisiones',
    decisionsNote: 'personas, asignación, plazos',
    later: 'Después',
    changed: 'Algo cambió',
    changedNote: 'documento cambiado o spec errónea',
    agent: 'Agente de IA',
    agentVerbs: ['lee, planifica, cita,', 'traspasa, reconcilia'],
    plans: 'Planifica',
    plansTitle: 'Plan para revisar y aprobar',
    plansNote: 'hitos, líneas, fechas ajustadas a su gente',
    writes: 'Escribe',
    writesTitle: 'Una especificación por elemento',
    writesNote: 'todas de la misma verdad de referencia',
    opens: 'Abre',
    opensTitle: 'Tablero de GitHub con incidencias e hitos',
    opensNote: 'cada incidencia enlaza especificación y fuentes',
    generates: 'Genera',
    generatesTitle: 'Agent skill del proyecto',
    generatesNote: 'instalado una vez por cada ingeniero',
    engineers: ['Ingenieros con', 'agentes de código'],
  },
};
