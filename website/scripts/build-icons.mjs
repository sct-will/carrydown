// Writes the favicon files into public/ and the mark at several sizes into src/assets/logo/png/ from
// the mark in src/assets/logo/. Run it by hand when the mark changes: `node scripts/build-icons.mjs`.
// The output is committed. The build does not run this script. The share image has its own script,
// build-og-image.mjs, which draws the mark with the title.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const logo = (name) => readFileSync(join(root, 'src/assets/logo', name), 'utf8');
const out = (name) => join(root, 'public', name);

// favicon.svg: the square mark in the site's teal for a light tab, the lighter teal for a dark one. A
// favicon cannot inherit the page color, so the file sets its own and follows the browser's setting.
const favicon = logo('mark-square.svg')
  .replace('fill="#4aa4aa"', 'fill="var(--teal)"')
  .replace('>', '><title>Carried-context development</title><style>:root{--teal:#2a6f6f}@media (prefers-color-scheme:dark){:root{--teal:#5fb8b8}}</style>');
writeFileSync(out('favicon.svg'), favicon);

// The PNG icons sit on a rounded cream square, so they read in a tab of either color.
async function onCream(svgText, size, pad) {
  const inner = Math.round(size - pad * 2);
  const mark = await sharp(Buffer.from(svgText)).resize(inner, inner).png().toBuffer();
  const bg = Buffer.from(
    `<svg xmlns='http://www.w3.org/2000/svg' width='${size}' height='${size}'><rect width='${size}' height='${size}' rx='${Math.round(size * 0.18)}' fill='#F6F3EC'/></svg>`,
  );
  return sharp(bg).composite([{ input: mark, left: pad, top: pad }]).png().toBuffer();
}
const light = logo('mark-square-light.svg');
writeFileSync(out('favicon-32.png'), await onCream(light, 32, 2));
writeFileSync(out('apple-touch-icon.png'), await onCream(light, 180, 16));

// The mark alone, transparent ground, in the logo's teal, at the sizes a profile or a slide wants.
const pngDir = join(root, 'src/assets/logo/png');
mkdirSync(pngDir, { recursive: true });
const sizes = [64, 128, 256, 512, 1024];
for (const size of sizes) {
  writeFileSync(join(pngDir, `mark-${size}.png`), await sharp(Buffer.from(logo('mark-square.svg'))).resize(size, size).png().toBuffer());
}
console.log(`build-icons: wrote favicon.svg, favicon-32.png, apple-touch-icon.png and mark-{${sizes.join(',')}}.png`);
