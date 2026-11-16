// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { customDomain, site, base, siteName } from './site.config.mjs';
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

export default defineConfig({
  site,
  base,
  trailingSlash: 'always',
  integrations: [
    starlight({
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
        ThemeProvider: './src/components/starlight/ThemeProvider.astro',
        MobileMenuFooter: './src/components/starlight/MobileMenuFooter.astro',
      },
      // Code blocks as plain bordered boxes, as in the docs design, without the window frame.
      expressiveCode: {
        defaultProps: { frame: 'none' },
        styleOverrides: { borderColor: 'var(--border-strong)', borderRadius: '6px' },
      },
      // Pagefind indexes the whole build after `astro build`: the docs, and every site page whose main
      // element carries data-pagefind-body. The header's search dialog reads that index.
      pagefind: true,
      sidebar,
    }),
    pagesFiles,
  ],
});
