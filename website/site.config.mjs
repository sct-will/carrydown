// One place for the settings that change between the preview address and the custom domain.
//
// Until the custom domain is on, the site is served by GitHub Pages at
// https://sct-will.github.io/carrydown/. Set customDomain to "carriedcontext.dev" to serve it at the
// root of that domain. astro.config.mjs reads this file, and so does the layout.

/** The custom domain, with no scheme and no slash. Empty until the domain is connected. */
export const customDomain = 'carriedcontext.dev';

/** The GoatCounter site code. Empty means no analytics script is loaded. */
export const goatcounterCode = '';

/** Indexing is off until launch. One flag drives the robots meta tag and robots.txt. */
export const INDEXING_ENABLED = false;

/** The origin the site is built for. */
export const site = customDomain ? `https://${customDomain}` : 'https://sct-will.github.io';

/** The base path. "/" on the custom domain, "/carrydown" on the Pages address. */
export const base = customDomain ? '/' : '/carrydown';

export const siteName = 'Carried-context development';
export const repoUrl = 'https://github.com/sct-will/carrydown';
/** The author's site. The footer links the name in the copyright line to it. */
export const authorName = 'Will Scott, PhD';
export const authorUrl = 'https://www.willscottphd.com';

/** The branch the docs are built from. The Copy page control links a page's source and the images in
 * its Markdown to this branch. */
export const sourceBranch = 'main';

export const sampleBoardUrl = 'https://github.com/users/sct-will/projects/2';
export const accessibilityEmail = 'accessibility@carriedcontext.dev';
