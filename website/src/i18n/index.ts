import { en, type Strings } from './en';

/** Every locale the site serves. The default locale is first. Add a locale module and list it here. */
export const locales = ['en'] as const;
export type Locale = (typeof locales)[number];

const dictionaries: Record<string, Strings> = { en };

/** The strings of a locale, falling back to English for an unknown one. */
export function getStrings(locale: string = 'en'): Strings {
  return dictionaries[locale] ?? en;
}
