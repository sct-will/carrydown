// One place for the settings that change between the preview address and the custom domain.
//
// Until the custom domain is on, the site is served by GitHub Pages at
// https://sct-will.github.io/carrydown/. Set customDomain to "carried-context.dev" to serve it at the
// root of that domain. astro.config.mjs reads this file, and so does the layout.

/** The custom domain, with no scheme and no slash. Empty until the domain is connected. */
export const customDomain = '';

/** The GoatCounter site code. Empty means no analytics script is loaded. */
export const goatcounterCode = '';

/** Indexing is off until launch. One flag drives the robots meta tag and robots.txt. */
export const INDEXING_ENABLED = false;

/** The origin the site is built for. */
export const site = customDomain ? `https://${customDomain}` : 'https://sct-will.github.io';

/** The base path. "/" on the custom domain, "/carrydown" on the Pages address. */
export const base = customDomain ? '/' : '/carrydown';

export const siteName = 'Carried context';
export const repoUrl = 'https://github.com/sct-will/carrydown';
export const sampleBoardUrl = 'https://github.com/users/sct-will/projects/2';
export const accessibilityEmail = 'accessibility@carried-context.dev';
