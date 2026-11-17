// Route to title and description, keyed by locale. The metadata component reads this so that no page
// needs to pass anything beyond what the layout already receives. Strings come from the locale
// modules in src/i18n/ where they exist. English text fills the gaps, and a locale without its own
// strings falls back to English through getStrings.
import { getStrings } from '../i18n';

export type PageKey = 'home' | 'definition' | 'faq' | 'accessibility';

/** The route of each page, without the base path and without the locale prefix. */
export const routes: Record<string, PageKey> = {
  '/': 'home',
  '/definition/': 'definition',
  '/faq/': 'faq',
  '/accessibility/': 'accessibility',
};

export interface PageMeta {
  title: string;
  description: string;
}

/** English text for pages whose strings are not in a locale module. */
const englishDefaults: Record<PageKey, PageMeta> = {
  home: {
    title: 'Carried-context development, home',
    description:
      'Carried-context development is an approach to agentic development that carries project decisions and context all the way down to each engineer’s coding agent, so the project stays aligned and nothing drifts.',
  },
  definition: {
    title: 'Carried-context development, definition',
    description:
      'Carried-context development carries a team’s agreed ground truth down into the plan, every specification, every issue and every coding agent’s instructions, cited by section, and carries it down again when the ground truth changes.',
  },
  faq: {
    title: 'Questions, carried-context development',
    description: 'Short answers about carried-context development and carrydown, with links into the docs where there is more.',
  },
  accessibility: {
    title: 'Accessibility statement',
    description: 'The accessibility statement for carriedcontext.dev: what the site supports, how it was checked and how to report a problem.',
  },
};

type Loose = Record<string, unknown>;
const str = (v: unknown): string | undefined => (typeof v === 'string' && v.trim() ? v.trim() : undefined);

/** Title and description of a page in a locale. */
export function pageMeta(locale: string, key: PageKey): PageMeta {
  const t = getStrings(locale) as unknown as Loose;
  const section = (t[key] ?? {}) as Loose;
  const fallback = englishDefaults[key];
  return {
    title: str(section.title) ?? str(section.metaTitle) ?? fallback.title,
    description: str(section.description) ?? str(section.metaDescription) ?? fallback.description,
  };
}

/** The one-sentence definition, from the definition page strings, else the English text. */
export function definitionSentence(locale: string): string {
  const t = getStrings(locale) as unknown as Loose;
  const d = (t.definition ?? {}) as Loose;
  const sentence = str(d.sentence) ?? str(d.definition) ?? str(d.def) ?? str(d.statement);
  return sentence ?? englishDefaults.definition.description;
}

export interface FaqItem {
  question: string;
  answer: string;
}

const stripTags = (s: string) => s.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
const asText = (v: unknown): string | undefined => {
  if (typeof v === 'string') return stripTags(v) || undefined;
  if (Array.isArray(v)) return stripTags(v.filter((x) => typeof x === 'string').join(' ')) || undefined;
  return undefined;
};

/** The FAQ questions and answers from the locale module: an array of {q, a} or {question, answer} items. */
export function faqItems(locale: string): FaqItem[] {
  const t = getStrings(locale) as unknown as Loose;
  const faq = (t.faq ?? {}) as Loose;
  for (const value of Object.values(faq)) {
    if (!Array.isArray(value) || value.length === 0) continue;
    const items: FaqItem[] = [];
    for (const raw of value) {
      if (!raw || typeof raw !== 'object') continue;
      const o = raw as Loose;
      const question = asText(o.q ?? o.question ?? o.title);
      const list = Array.isArray(o.list) ? (o.list as unknown[]).filter((x): x is string => typeof x === 'string') : [];
      const answer = asText([o.a ?? o.answer ?? o.body, ...list].filter((x) => typeof x === 'string').join(' '));
      if (question && answer) items.push({ question, answer });
    }
    if (items.length) return items;
  }
  return [];
}
