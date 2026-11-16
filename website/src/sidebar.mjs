// The docs sidebar, built from the manifest that scripts/build-docs.mjs writes from the repository's
// Markdown files: Start here (README, setup, plan owner guide), Reference (the rest, alphabetical by
// title) and Sample. Page labels come from each page's own title, so a translated page shows its
// translated title. The manifest is generated and not committed; until the generator has run, the sidebar
// is empty.
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const manifestPath = fileURLToPath(new URL('./generated/docs-manifest.json', import.meta.url));

// Group labels in each locale. Hardcoded here so they do not depend on the English page titles.
const labels = {
  start: {
    label: 'Start here',
    translations: { de: 'Hier beginnen', fr: 'Pour commencer', ja: 'はじめに', es: 'Empezar aquí', 'pt-BR': 'Comece aqui', 'zh-CN': '从这里开始' },
  },
  reference: {
    label: 'Reference',
    translations: { de: 'Referenz', fr: 'Référence', ja: 'リファレンス', es: 'Referencia', 'pt-BR': 'Referência', 'zh-CN': '参考' },
  },
  sample: {
    label: 'Sample',
    translations: { de: 'Beispiel', fr: 'Exemple', ja: 'サンプル', es: 'Ejemplo', 'pt-BR': 'Exemplo', 'zh-CN': '示例' },
  },
};

function build() {
  if (!existsSync(manifestPath)) return [];
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  return manifest.groups.map((g) => ({
    label: labels[g.id].label,
    translations: labels[g.id].translations,
    items: g.slugs.map((slug) => ({ slug })),
  }));
}

export const sidebar = build();
