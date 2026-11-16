import { defineCollection } from 'astro:content';
import type { Loader } from 'astro/loaders';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema, i18nSchema } from '@astrojs/starlight/schema';
import { localeList, getStrings, defaultLocale } from './i18n';
import { notFoundText } from './i18n/en';

// Starlight's own interface strings, per language. The site keeps all translated text in .ts modules,
// so this loader builds the entries from them instead of reading JSON files. Today it renames
// Starlight's mobile sidebar button to "Docs menu", so it does not repeat the site's Menu button, and
// replaces the not-found text, which points to a search the site does not have.
const uiStrings: Loader = {
  name: 'site-ui-strings',
  async load({ store, parseData }) {
    store.clear();
    for (const l of localeList) {
      const data = await parseData({
        id: l.lang,
        data: {
          'menuButton.accessibleLabel': getStrings(l.code).nav.docsMenu,
          ...(l.code === defaultLocale ? { '404.text': notFoundText } : {}),
        },
      });
      store.set({ id: l.lang, data });
    }
  },
};

export const collections = {
  docs: defineCollection({ loader: docsLoader(), schema: docsSchema() }),
  i18n: defineCollection({ loader: uiStrings, schema: i18nSchema() }),
};
