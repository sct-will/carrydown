import { en, type Strings } from './en';
import { de } from './de';
import { fr } from './fr';
import { ja } from './ja';
import { es } from './es';
import { ptBR } from './pt-BR';
import { zhCN } from './zh-CN';
import { localeCodes, localeList, defaultLocale, translatedLocales } from './locales';

export { localeList, defaultLocale, translatedLocales };
export type { Strings };

/** Every locale the site serves. The default locale is first. Add a module in this folder, import it
 * here and add the locale to locales.mjs. */
export const locales = localeCodes;

const dictionaries: Record<string, Strings> = {
  en,
  de,
  fr,
  ja,
  es,
  'pt-br': ptBR,
  'zh-cn': zhCN,
};

/** The strings of a locale, falling back to English for an unknown one. */
export function getStrings(locale: string = defaultLocale): Strings {
  return dictionaries[locale] ?? en;
}
