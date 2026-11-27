// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import { readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { customDomain, site, base, siteName, iconVersion } from './site.config.mjs';
import { sidebar } from './src/sidebar.mjs';
import { localeList, defaultLocale } from './src/i18n/locales.mjs';

// Writes the files GitHub Pages needs next to the built pages: .nojekyll always, and CNAME once a
// custom domain is set.
/** @type {import('astro').AstroIntegration} */
const pagesFiles = {
  name: 'carried-context-pages-files',
  hooks: {
    'astro:build:done': ({ dir }) => {
      writeFileSync(fileURLToPath(new URL('.nojekyll', dir)), '');
      if (customDomain) writeFileSync(fileURLToPath(new URL('CNAME', dir)), `${customDomain}\n`);
    },
  },
};

// Starlight's locale table, built from the one locale list. The default locale is the root: its docs
// have no URL prefix. Every other locale is served under /<code>/docs/, and a docs page without a
// translation shows the English page with a note.
const starlightLocales = Object.fromEntries(
  localeList.map((l) => [
    l.code === defaultLocale ? 'root' : l.code,
    { label: l.label, lang: l.lang, dir: l.dir },
  ]),
);

// The site has one theme, light. Starlight writes its dark theme into the <html> data-theme of every docs
// page as its no-script fallback; this writes the site's theme there instead, so a docs page is light
// before any script runs. ThemeScript holds the same value at runtime.
/** @type {import('astro').AstroIntegration} */
const lightTheme = {
  name: 'carried-context-light-theme',
  hooks: {
    'astro:build:done': ({ dir }) => {
      /** @param {string} folder */
      const walk = (folder) => {
        for (const entry of readdirSync(folder, { withFileTypes: true })) {
          const path = join(folder, entry.name);
          if (entry.isDirectory()) walk(path);
          else if (entry.name.endsWith('.html')) {
            const html = readFileSync(path, 'utf8');
            const next = html.replace(/(<html\b[^>]*?)\sdata-theme="[a-z]+"/, '$1 data-theme="light"');
            if (next !== html) writeFileSync(path, next);
          }
        }
      };
      walk(fileURLToPath(dir));
    },
  },
};

// The docs FAQ page became the troubleshooting page. The old address in each locale redirects to the
// new one. Astro adds the base path to both sides.
const redirects = Object.fromEntries(
  localeList.map((l) => {
    const prefix = l.code === defaultLocale ? '' : `/${l.code}`;
    return [`${prefix}/docs/faq/`, `${prefix}/docs/troubleshooting/`];
  }),
);

export default defineConfig({
  site,
  base,
  trailingSlash: 'always',
  redirects,
  integrations: [
    starlight({
      favicon: `/favicon.svg?v=${iconVersion}`,
      title: siteName,
      description:
        'Carried-context development carries project decisions and context all the way down to each engineer’s coding agent.',
      // The docs and the pages share one palette and one header and footer.
      customCss: ['./src/styles/tokens.css', './src/styles/chrome.css', './src/styles/locales.css', './src/styles/docs.css'],
      defaultLocale: 'root',
      locales: starlightLocales,
      components: {
        Header: './src/components/starlight/Header.astro',
        Footer: './src/components/starlight/Footer.astro',
        // Adds the robots tag, the image tags, the JSON-LD and the analytics tag to the docs pages.
        Head: './src/components/starlight/Head.astro',
        // The page title with the Copy page control beside it.
        PageTitle: './src/components/starlight/PageTitle.astro',
        ThemeProvider: './src/components/starlight/ThemeProvider.astro',
        MobileMenuFooter: './src/components/starlight/MobileMenuFooter.astro',
      },
      // Code blocks as plain bordered boxes, without the window frame, in the one light theme.
      expressiveCode: {
        themes: ['starlight-light'],
        useStarlightDarkModeSwitch: false,
        defaultProps: { frame: 'none' },
        styleOverrides: { borderColor: 'var(--hairline)', borderRadius: '4px' },
      },
      // Pagefind indexes the whole build after `astro build`: the docs, and every site page whose main
      // element carries data-pagefind-body. The header's search dialog reads that index.
      pagefind: true,
      sidebar,
    }),
    pagesFiles,
    lightTheme,
  ],
});
