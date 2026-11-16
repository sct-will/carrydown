// The locale list. Plain JavaScript so that Node build scripts (the docs generator) and the Astro code
// read the same list. src/i18n/locales.ts re-exports it with types. The default locale is first and
// has no URL prefix; every other locale lives under /<code>/.

/**
 * @typedef {Object} LocaleInfo
 * @property {string} code The URL prefix and the key of the strings. Lowercase, because Starlight lowercases
 *   the folder names of its content, so the docs of pt-BR live at /pt-br/docs/. The pages use the same
 *   prefix so that the language control moves between a page and its docs with one rule.
 * @property {string} lang The BCP 47 tag for the lang attribute.
 * @property {string} hreflang The tag for hreflang alternates.
 * @property {string} label The name of the language in that language.
 * @property {'ltr' | 'rtl'} dir
 */

/** @type {LocaleInfo[]} */
export const localeList = [
  { code: 'en', lang: 'en', hreflang: 'en', label: 'English', dir: 'ltr' },
  { code: 'de', lang: 'de', hreflang: 'de', label: 'Deutsch', dir: 'ltr' },
  { code: 'fr', lang: 'fr', hreflang: 'fr', label: 'Français', dir: 'ltr' },
  { code: 'ja', lang: 'ja', hreflang: 'ja', label: '日本語', dir: 'ltr' },
  { code: 'es', lang: 'es', hreflang: 'es', label: 'Español', dir: 'ltr' },
  { code: 'pt-br', lang: 'pt-BR', hreflang: 'pt-BR', label: 'Português (Brasil)', dir: 'ltr' },
  { code: 'zh-cn', lang: 'zh-CN', hreflang: 'zh-CN', label: '简体中文', dir: 'ltr' },
];

export const defaultLocale = 'en';

/** The codes, default first: en, de, fr, ja, es, pt-br, zh-cn. */
export const localeCodes = localeList.map((l) => l.code);

/** Every locale except the default one: the ones that carry a translation notice. */
export const translatedLocales = localeCodes.filter((c) => c !== defaultLocale);
