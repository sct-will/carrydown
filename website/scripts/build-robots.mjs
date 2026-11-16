// Writes dist/robots.txt after `astro build`. One flag, INDEXING_ENABLED in site.config.mjs, drives this
// file and the robots meta tag. While it is false the file disallows everything. When it is true the
// file allows everything and names the sitemap.
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { INDEXING_ENABLED, site, base } from '../site.config.mjs';

const dist = join(resolve(dirname(fileURLToPath(import.meta.url)), '..'), 'dist');
const prefix = base === '/' ? '' : base.replace(/\/+$/, '');

const lines = INDEXING_ENABLED
  ? ['User-agent: *', 'Allow: /', '', `Sitemap: ${site}${prefix}/sitemap-index.xml`]
  : ['User-agent: *', 'Disallow: /'];

mkdirSync(dist, { recursive: true });
writeFileSync(join(dist, 'robots.txt'), `${lines.join('\n')}\n`);
console.log(`build-robots: wrote dist/robots.txt (indexing ${INDEXING_ENABLED ? 'on' : 'off'})`);
