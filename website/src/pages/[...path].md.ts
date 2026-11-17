// The Markdown of each docs page, served next to the page: /docs/setup/ has /docs/setup.md. The Copy
// page control reads it, and a reader or an agent can open it directly. The text is the generated page
// with its links made absolute, so it reads the same wherever it is pasted.
import type { APIRoute, GetStaticPaths } from 'astro';
import { getCollection } from 'astro:content';
import { site, base, repoUrl, sourceBranch } from '../../site.config.mjs';

const prefix = base === '/' ? '' : base.replace(/\/+$/, '');
// Images copied into the site are read from the repository at the branch the docs are built from.
const RAW = `${repoUrl.replace('https://github.com/', 'https://raw.githubusercontent.com/')}/${sourceBranch}/`;

export const getStaticPaths: GetStaticPaths = async () => {
  const entries = await getCollection('docs');
  return entries
    .filter((entry) => entry.id !== '404' && typeof entry.body === 'string')
    .map((entry) => ({ params: { path: entry.id }, props: { entry } }));
};

/** An absolute address for a link in the page. Images copied into the site are read from the repository. */
function absolute(href: string, pageUrl: string): string {
  const copied = href.match(/assets\/docs\/(.+)$/);
  if (copied) return RAW + copied[1];
  return new URL(href, pageUrl).href;
}

const relative = (href: string) => !/^([a-z][a-z0-9+.-]*:|\/\/|#)/i.test(href);

/** The page as Markdown: the title, the source note as plain text, the body with absolute links. */
export function pageMarkdown(title: string, body: string, pageUrl: string): string {
  const text = body
    // The source note and the translation note are HTML paragraphs in the generated page.
    .replace(/<p class="synced[^"]*"[^>]*>([\s\S]*?)<\/p>/g, (_m, inner: string) => inner.replace(/<[^>]+>/g, '').trim())
    .replace(/\]\(([^)\s]+)\)/g, (m, href: string) => (relative(href) ? `](${absolute(href, pageUrl)})` : m))
    .replace(/\b(src|href)="([^"]+)"/g, (m, attr: string, href: string) => (relative(href) ? `${attr}="${absolute(href, pageUrl)}"` : m));
  return `# ${title}\n\n${text.trim()}\n`;
}

export const GET: APIRoute = ({ props }) => {
  const { entry } = props;
  const pageUrl = `${site}${prefix}/${entry.id}/`;
  return new Response(pageMarkdown(entry.data.title, entry.body ?? '', pageUrl), {
    headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
  });
};
