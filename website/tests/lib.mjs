// Shared helpers for the site tests: start `astro preview`, list the built routes.
import { spawn } from 'node:child_process';
import { readdirSync, statSync, existsSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { base } from '../site.config.mjs';

export const websiteDir = join(dirname(fileURLToPath(import.meta.url)), '..');
export const dist = join(websiteDir, 'dist');
export const basePath = base === '/' ? '' : base.replace(/\/+$/, '');

/** Every built page as a route path with the base, for example /carrydown/faq/. */
export function listRoutes() {
  if (!existsSync(dist)) throw new Error('dist/ is missing. Run `npm run build` first.');
  const routes = [];
  const walk = (dir) => {
    for (const name of readdirSync(dir)) {
      const p = join(dir, name);
      if (statSync(p).isDirectory()) walk(p);
      else if (name === 'index.html') {
        const rel = relative(dist, dirname(p)).split('\\').join('/');
        routes.push(`${basePath}/${rel}${rel ? '/' : ''}`);
      }
    }
  };
  walk(dist);
  return routes.sort();
}

/** Starts `astro preview` and resolves with { origin, stop } once it answers. */
export async function startPreview(port = 4399) {
  const child = spawn(process.execPath, [join(websiteDir, 'node_modules/astro/bin/astro.mjs'), 'preview', '--ignore-lock', '--host', '127.0.0.1', '--port', String(port)], {
    cwd: websiteDir,
    env: { ...process.env, ASTRO_TELEMETRY_DISABLED: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let log = '';
  child.stdout.on('data', (d) => (log += d));
  child.stderr.on('data', (d) => (log += d));
  const origin = `http://127.0.0.1:${port}`;
  const stop = () => new Promise((resolve) => {
    if (child.exitCode !== null) return resolve();
    child.once('exit', () => resolve());
    child.kill('SIGTERM');
    setTimeout(() => child.kill('SIGKILL'), 3000).unref();
  });
  for (let i = 0; i < 100; i++) {
    if (child.exitCode !== null) throw new Error(`astro preview exited early:\n${log}`);
    try {
      const r = await fetch(`${origin}${basePath}/`);
      if (r.ok) return { origin, stop };
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 200));
  }
  await stop();
  throw new Error(`astro preview did not start:\n${log}`);
}
