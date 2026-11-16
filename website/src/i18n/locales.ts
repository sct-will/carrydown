// Typed view of locales.mjs, the one list of locales for the pages, the language control, the
// Starlight configuration and the docs generator.
import { localeList, defaultLocale, localeCodes, translatedLocales } from './locales.mjs';

export { localeList, defaultLocale, localeCodes, translatedLocales };
export type Locale = 'en' | 'de' | 'fr' | 'ja' | 'es' | 'pt-br' | 'zh-cn';
