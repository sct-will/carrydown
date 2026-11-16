// Writes the favicon files and a placeholder Open Graph image into public/ from the "Pinned pages"
// mark in src/assets/logo/. Run it by hand when the mark changes: `node scripts/build-icons.mjs`.
// The output is committed. The build does not run this script.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const logo = (name) => readFileSync(join(root, 'src/assets/logo', name), 'utf8');
const out = (name) => join(root, 'public', name);

// favicon.svg: the one-color mark from currentColor. A favicon cannot inherit the page color, so the
// file sets its own and follows the browser's light or dark setting.
const mono = logo('I-pages-mono.svg')
  .replace(" width='64' height='64' role='img'", '')
  .replace('>', '><title>Carried context</title><style>:root{color:#1F2A44}@media (prefers-color-scheme:dark){:root{color:#EEF1F6}}</style>');
writeFileSync(out('favicon.svg'), mono.replace('<svg ', '<svg color="#1F2A44" '));

// The PNGs sit on a rounded cream square, so they read in a tab of either color.
async function onCream(svgText, size, pad) {
  const inner = Math.round(size - pad * 2);
  const mark = await sharp(Buffer.from(svgText)).resize(inner, inner).png().toBuffer();
  const bg = Buffer.from(
    `<svg xmlns='http://www.w3.org/2000/svg' width='${size}' height='${size}'><rect width='${size}' height='${size}' rx='${Math.round(size * 0.18)}' fill='#F6F3EC'/></svg>`,
  );
  return sharp(bg).composite([{ input: mark, left: pad, top: pad }]).png().toBuffer();
}
const light = logo('I-pages-light.svg');
writeFileSync(out('favicon-32.png'), await onCream(light, 32, 3));
writeFileSync(out('apple-touch-icon.png'), await onCream(light, 180, 22));

// Placeholder Open Graph image, 1200 by 630: navy ground, the mark at 160 px, the title. The metadata
// work replaces this with a build step.
const markDark = await sharp(Buffer.from(logo('I-pages-dark.svg'))).resize(160, 160).png().toBuffer();
const base = Buffer.from(
  `<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='630'><rect width='1200' height='630' fill='#0F1420'/>` +
    `<text x='96' y='400' font-family='Helvetica, Arial, sans-serif' font-size='72' font-weight='700' fill='#EEF1F6'>Context that travels</text>` +
    `<text x='96' y='490' font-family='Helvetica, Arial, sans-serif' font-size='72' font-weight='700' fill='#EEF1F6'>with the work.</text></svg>`,
);
writeFileSync(out('og-image.png'), await sharp(base).composite([{ input: markDark, left: 96, top: 96 }]).png().toBuffer());
console.log('build-icons: wrote favicon.svg, favicon-32.png, apple-touch-icon.png, og-image.png');
