// Writes the mark's variants and the icons from the master drawing, src/assets/logo/mark.svg (K1: the
// letters C, C and D as ink outlines, the thread in amber-stroke cut through them by a mask and drawn
// over). Run it by hand when the mark changes: `node scripts/build-icons.mjs`. The output is committed.
// The build does not run this script. The share image has its own script, build-og-image.mjs.
//
// It writes:
// - src/assets/logo/mark-mono.svg: letters and thread in currentColor, for one-color use.
// - src/assets/logo/mark-square.svg and mark-square-light.svg: the mark on a square canvas, ink letters
//   and the amber-stroke thread, for a light ground; mark-square-dark.svg: paper letters and the ochre
//   thread, for a dark ground.
// - public/favicon.svg and public/favicon-32.png: the mark on a rounded paper square. A favicon is
//   drawn at 16 to 32 px, so it uses the K3 weights (outline 58, thread 72, cut 136) instead of K1's
//   (44, 66, 130); every size under 64 px does.
// - public/apple-touch-icon.png: the mark on a rounded paper square, 180 px.
// - src/assets/logo/png/mark-{64,128,256,512,1024}.png: the mark alone on a transparent ground.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const logoDir = join(root, 'src/assets/logo');
const out = (name) => join(root, 'public', name);

const INK = '#1D1A15';
const AMBER_STROKE = '#A8740C';
const PAPER = '#F5F1E8';
const OCHRE = '#D9A441';
const NAME = 'Carried-context development';

const master = readFileSync(join(logoDir, 'mark.svg'), 'utf8');
if (!master.includes(`stroke="${INK}"`) || !master.includes(`stroke="${AMBER_STROKE}"`)) {
  throw new Error('mark.svg: expected ink letters and an amber-stroke thread');
}
// The inside of the master <svg>: the mask, the letters and the thread.
const inner = master.replace(/^<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '');

/** The drawing with its colors and, for small sizes, the K3 weights. */
function draw({ letters = INK, thread = AMBER_STROKE, heavy = false, id = 'cut' } = {}) {
  let s = inner
    .replaceAll(`stroke="${INK}"`, `stroke="${letters}"`)
    .replaceAll(`stroke="${AMBER_STROKE}"`, `stroke="${thread}"`)
    .replaceAll('id="cut"', `id="${id}"`)
    .replaceAll('url(#cut)', `url(#${id})`);
  if (heavy) {
    s = s.replace('stroke-width="130"', 'stroke-width="136"').replace('stroke-width="44"', 'stroke-width="58"').replace('stroke-width="66"', 'stroke-width="72"');
  }
  return s;
}

// The mark is 931 by 777 units, centered on (626.5, 628.5). A square canvas of side `side` around it.
const square = (side) => `${626.5 - side / 2} ${628.5 - side / 2} ${side} ${side}`;
const svg = (viewBox, body, extra = '') => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}"${extra}>${body}</svg>`;

// The variants beside the master.
writeFileSync(join(logoDir, 'mark-mono.svg'), svg('161 240 931 777', draw({ letters: 'currentColor', thread: 'currentColor' }), ' role="img" aria-label="carrydown mark"'));
writeFileSync(join(logoDir, 'mark-square.svg'), svg(square(975), draw()));
writeFileSync(join(logoDir, 'mark-square-light.svg'), svg(square(975), draw()));
writeFileSync(join(logoDir, 'mark-square-dark.svg'), svg(square(975), draw({ letters: PAPER, thread: OCHRE })));

// An icon: the mark on a rounded paper square with a margin round it.
const ICON_SIDE = 1160;
const icon = (heavy) => {
  const [x, y] = square(ICON_SIDE).split(' ');
  const ground = `<rect x="${x}" y="${y}" width="${ICON_SIDE}" height="${ICON_SIDE}" rx="${Math.round(ICON_SIDE * 0.18)}" fill="${PAPER}"/>`;
  return svg(square(ICON_SIDE), `<title>${NAME}</title>${ground}${draw({ heavy })}`);
};
const png = (text, size) => sharp(Buffer.from(text), { density: 600 }).resize(size, size).png().toBuffer();

const favicon = icon(true);
writeFileSync(out('favicon.svg'), favicon);
writeFileSync(out('favicon-32.png'), await png(favicon, 32));
writeFileSync(out('apple-touch-icon.png'), await png(icon(false), 180));

// The mark alone, transparent ground, at the sizes a profile or a slide wants. All are 64 px or more,
// so all use the K1 weights.
const pngDir = join(logoDir, 'png');
mkdirSync(pngDir, { recursive: true });
const sizes = [64, 128, 256, 512, 1024];
const plain = svg(square(975), draw());
for (const size of sizes) writeFileSync(join(pngDir, `mark-${size}.png`), await png(plain, size));
console.log(`build-icons: wrote mark-mono.svg, mark-square{,-light,-dark}.svg, favicon.svg, favicon-32.png, apple-touch-icon.png and mark-{${sizes.join(',')}}.png`);
