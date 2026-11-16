import { defineCollection } from 'astro:content';
import type { Loader } from 'astro/loaders';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema, i18nSchema } from '@astrojs/starlight/schema';
import { localeList, getStrings } from './i18n';

// Starlight's own interface strings, per language. The site keeps all translated text in .ts modules,
// so this loader builds the entries from them instead of reading JSON files. Today it renames
// Starlight's mobile sidebar button to "Docs menu", so it does not repeat the site's Menu button.
const uiStrings: Loader = {
  name: 'site-ui-strings',
  async load({ store, parseData }) {
    store.clear();
    for (const l of localeList) {
      const data = await parseData({
        id: l.lang,
        data: { 'menuButton.accessibleLabel': getStrings(l.code).nav.docsMenu },
      });
      store.set({ id: l.lang, data });
    }
  },
};

export const collections = {
  docs: defineCollection({ loader: docsLoader(), schema: docsSchema() }),
  i18n: defineCollection({ loader: uiStrings, schema: i18nSchema() }),
};
