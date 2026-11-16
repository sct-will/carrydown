// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { customDomain, site, base, siteName } from './site.config.mjs';
import { sidebar } from './src/sidebar.mjs';

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
      customCss: ['./src/styles/tokens.css', './src/styles/chrome.css'],
      components: {
        Header: './src/components/starlight/Header.astro',
        Footer: './src/components/starlight/Footer.astro',
        ThemeProvider: './src/components/starlight/ThemeProvider.astro',
      },
      pagefind: false,
      sidebar,
    }),
    pagesFiles,
  ],
});
