// Every internal link and asset goes through these helpers so the site works at /carrydown/ on the
// Pages address and at / on the custom domain.

const root = import.meta.env.BASE_URL.replace(/\/+$/, '');

/** The default locale has no prefix. Every other locale lives under /<locale>/. */
export const defaultLocale = 'en';

/** A site route with the base path and the locale prefix, for example localePath('de', '/faq/'). */
export function localePath(locale: string, path: string): string {
  const prefix = locale === defaultLocale ? '' : `/${locale}`;
  return `${root}${prefix}${path}`;
}

/** A static asset or a route with only the base path, for example withBase('/favicon.svg'). */
export function withBase(path: string): string {
  return `${root}${path}`;
}

/** The route of a page without the base path and without the locale prefix, for matching nav items. */
export function stripBase(pathname: string, locales: string[]): string {
  let p = pathname;
  if (root && p.startsWith(root)) p = p.slice(root.length) || '/';
  for (const l of locales) {
    if (l !== defaultLocale && (p === `/${l}` || p.startsWith(`/${l}/`))) {
      p = p.slice(l.length + 1) || '/';
      break;
    }
  }
  return p;
}
