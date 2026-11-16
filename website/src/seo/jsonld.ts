// Builds the JSON-LD graph for a page. Pure functions, no Astro imports, so the output is easy to test.
import { repoUrl } from '../../site.config.mjs';
import type { FaqItem } from './pages';

export const authorName = 'Will Scott, PhD';
const authorUrl = 'https://github.com/sct-will';

export interface GraphInput {
  kind: string;
  siteName: string;
  /** Absolute URL of the site root, with the base path and a trailing slash. */
  siteUrl: string;
  /** Absolute canonical URL of the page. */
  pageUrl: string;
  title: string;
  description: string;
  /** BCP 47 tag of the page language. */
  language: string;
  definition?: string;
  faq?: FaqItem[];
}

const personId = (siteUrl: string) => `${siteUrl}#author`;
const websiteId = (siteUrl: string) => `${siteUrl}#website`;

export function buildGraph(i: GraphInput): Record<string, unknown> {
  const author = { '@id': personId(i.siteUrl) };
  const graph: Record<string, unknown>[] = [
    {
      '@type': 'WebSite',
      '@id': websiteId(i.siteUrl),
      name: i.siteName,
      url: i.siteUrl,
      inLanguage: i.language,
      author,
    },
    {
      '@type': 'Person',
      '@id': personId(i.siteUrl),
      name: authorName,
      url: authorUrl,
      sameAs: [authorUrl],
    },
  ];

  if (i.kind === 'definition' && i.definition) {
    graph.push({
      '@type': 'DefinedTerm',
      '@id': `${i.pageUrl}#term`,
      name: 'Carried-context development',
      description: i.definition,
      termCode: '1.0',
      url: i.pageUrl,
      inLanguage: i.language,
      author,
      isPartOf: { '@id': websiteId(i.siteUrl) },
    });
  }

  if (i.kind === 'home') {
    graph.push({
      '@type': 'SoftwareSourceCode',
      '@id': `${i.siteUrl}#carrydown`,
      name: 'carrydown',
      description:
        'The open reference implementation of carried-context development: two Agent Skills you install, a third it generates for your engineers, and the checks that validate every citation.',
      codeRepository: repoUrl,
      url: repoUrl,
      license: 'https://spdx.org/licenses/Apache-2.0.html',
      programmingLanguage: 'Python',
      author,
    });
  }

  if (i.kind === 'faq' && i.faq && i.faq.length) {
    graph.push({
      '@type': 'FAQPage',
      '@id': `${i.pageUrl}#faq`,
      url: i.pageUrl,
      name: i.title,
      inLanguage: i.language,
      mainEntity: i.faq.map((f) => ({
        '@type': 'Question',
        name: f.question,
        acceptedAnswer: { '@type': 'Answer', text: f.answer },
      })),
    });
  }

  if (i.kind === 'docs') {
    graph.push({
      '@type': 'TechArticle',
      '@id': `${i.pageUrl}#article`,
      headline: i.title,
      description: i.description,
      url: i.pageUrl,
      mainEntityOfPage: i.pageUrl,
      inLanguage: i.language,
      author,
      isPartOf: { '@id': websiteId(i.siteUrl) },
    });
  }

  return { '@context': 'https://schema.org', '@graph': graph };
}

/** JSON for a script tag. The less-than sign is escaped so the text can never close the tag. */
export function toScriptJson(graph: unknown): string {
  return JSON.stringify(graph).replace(/</g, '\\u003c');
}
