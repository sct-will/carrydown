// Bounded page sets for the slow tests. The docs generator makes hundreds of pages, so reflow and a11y
// scan a chosen set instead of every page. routes.mjs still requests every page.
import { localeCodes, defaultLocale } from '../src/i18n/locales.mjs';
import { basePath, listRoutes } from './lib.mjs';

/** The five site pages, as routes without the locale prefix. */
const sitePages = ['/', '/definition/', '/sample/', '/faq/', '/accessibility/'];

/** A route in a locale, with the base path. Locale codes are the lowercase URL prefixes. */
export const routeFor = (locale, path) => `${basePath}${locale === defaultLocale ? '' : `/${locale}`}${path}`;

/** The five site pages in a locale. */
export const siteRoutes = (locale) => sitePages.map((p) => routeFor(locale, p));

export const otherLocales = localeCodes.filter((c) => c !== defaultLocale);

/** Fails loudly when a chosen page was not built, so a renamed route cannot shrink the set unnoticed. */
export function requireBuilt(routes) {
  const built = new Set(listRoutes());
  const missing = routes.filter((r) => !built.has(r));
  if (missing.length) throw new Error(`pages missing from dist/: ${missing.join(', ')}`);
  return routes;
}

/** Every built English docs page: the routes under /docs/. */
export const englishDocsRoutes = () => listRoutes().filter((r) => r.startsWith(`${basePath}/docs/`));

/** The fallback docs page checked in each locale: the English setup page shown with a note. */
export const fallbackDocsRoute = (locale) => routeFor(locale, '/docs/setup/');
