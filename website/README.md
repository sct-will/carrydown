# carriedcontext.dev website

The website for carried-context development: the home page, the definition, the FAQ, the accessibility statement and the carrydown documentation. It is an Astro 7 site with Starlight for the docs. The docs are generated from the Markdown in this repository at build time.

## Run it

You need Node.js 22 or later.

```bash
cd website
npm ci
npx playwright install chromium   # once, for the tests and the social image
npm run dev                       # http://localhost:4321/carrydown/
```

## Build

```bash
npm run build
```

The build runs these steps in order:

1. `scripts/build-docs.mjs` generates the docs pages from the pages listed in its `PUBLIC_PAGES`: `README.md`, the approved `docs/*.md` files and `sample/expense-approvals/README.md`. An unlisted file in `docs/` is not published.
2. `astro build` writes the site to `dist/`.
3. `scripts/build-og-image.mjs` renders the 1200 by 630 social image to `dist/og-image.png`.
4. `scripts/build-llms.mjs` writes `dist/llms.txt` and `dist/llms-full.txt` from the built pages. See "The llms.txt files" below.
5. `scripts/build-robots.mjs` writes `dist/robots.txt`.

To refresh the committed `public/og-image.png` after changing the image script, run `node scripts/build-og-image.mjs --public`.

## Test

Build first, then:

```bash
npm test
```

This runs, in order:

- `scripts/check-docs-sync.mjs` regenerates the docs into a temporary folder and fails with a diff if the generated pages differ from the repository's Markdown.
- `tests/docs-publication.mjs` runs the generator on a small temporary repository and proves that only listed pages are published: an unlisted file in `docs/` appears in no generated file or locale, and a listed page missing on disk stops the build. It needs no built site.
- `tests/routes.mjs` starts `astro preview` and expects 200 for every page, in every locale, and for every internal link and asset.
- `tests/llms.mjs` checks `llms.txt` and `llms-full.txt`: the format, that every English page is listed once and no redirect is, the reading order, the "What to tell your agent, and when" phrases against the README, that a second run writes the same bytes, and that every listed address answers 200.
- `tests/reflow.mjs` takes screenshots of a bounded set of pages (the four site pages at six widths, plus Japanese, docs and fallback samples) into `tests/screenshots/` and fails on horizontal overflow, text under 12 px and tap targets under 44 px.
- `tests/a11y.mjs` runs axe-core on a bounded set (the four site pages in every locale, every English docs page and one fallback docs page per locale) and fails on any violation.

Type checks: `npx astro check`.

## Design

The design is the Hartwell direction of the round 3 and round 4 mockups, carried into the site in November 2026. The reference renders and their notes are in `specs/carried-context-site/mockups-v3/` (tokens, contrast, type, the figure) and `specs/carried-context-site/mockups-v4/` (the decisions, the mark, the title). The grammar: type-led, one accent for action and one for emphasis, a rule above each section heading, mono labels, the figure on a bone panel, the Try it out section as a pine band, hairline rows instead of cards. Nothing at rest carries a shadow. In place of a section number, each home page section head carries a small clay chevron, the figure's prompt chevron without its underscore.

- Tokens, in `src/styles/tokens.css`. Each text pair meets WCAG 2.2 AA.

  | Token | Value | Use | Contrast |
  | --- | --- | --- | --- |
  | `--paper` | #F5F1E8 | the page | |
  | `--bone` | #EAE3D3 | the figure panel, raised grounds | |
  | `--pine` | #17332C | hover ground on pine | |
  | `--pine-deep` | #0E241E | the Try it out band, the footer | |
  | `--ink` | #1D1A15 | text, headings, figure strokes | 15.4 on paper |
  | `--ink-soft` | #5E574A | secondary text | 6.3 on paper, 5.6 on bone |
  | `--clay` | #BC5A2E | the primary button, the figure's connectors | white on clay 4.5 |
  | `--clay-ink` | #9A4620 | section numbers, eyebrows, links, the focus ring | 5.7 on paper |
  | `--clay-tint` | #E8C9B5 | a pale clay ground | |
  | `--amber-ink` | #8F5A08 | the title's emphasis | 5.1 on paper |
  | `--amber-stroke` | #A8740C | the mark's thread on paper | |
  | `--ochre` | #D9A441 | numbers, links and the focus ring on pine; the mark's thread on pine | 7.2 on pine-deep |
  | `--cream-soft` | #B9C2B4 | body text on pine | 8.9 on pine-deep |
  | `--hairline` | #D6CDBA | rules on paper | |
  | `--hairline-dark` | #2E4A41 | rules on pine | |

- Light only. `color-scheme` is light, there is no theme control, and the docs are light too. `src/components/ThemeScript.astro` holds `data-theme="light"` on `<html>` for Starlight's styles and marks the page as script-enabled; the `lightTheme` step in `astro.config.mjs` writes the same value into every built docs page in place of Starlight's own no-script default. Code blocks use the one `starlight-light` theme.
- Theme color: `<meta name="theme-color" content="#0E241E">`, pine-deep, on every page, from `src/components/Seo.astro`. A browser that tints its toolbar (Safari, Android Chrome) frames the paper page in the green of the footer.
- Type: Atkinson Hyperlegible Next for everything, the titles included; Geist Mono for labels, numbers, quoted commands and paths. Both are self-hosted from their Fontsource packages, imported in `src/styles/tokens.css`. The home page title is weight 700. Chinese and Japanese pages put a native sans after the text face (`src/styles/locales.css`).
- The home page title is one sentence in the locale file (`home.h1`); the `h1Emphasis` key beside it names the part set in amber-ink, upright, in the same face and weight. A translation may move that part or leave it empty.
- The mark, `src/assets/logo/mark.svg` (K1 in the mockups): the letters C, C and D as three ink outlines, the thread cut through them by a mask and drawn over. `src/components/Mark.astro` draws the same geometry with the letters in `currentColor` and the thread in the `--thread` custom property: amber-stroke on paper (the header, at 22 px), ochre on pine (the footer). `scripts/build-icons.mjs` writes the variants, the favicon and the PNGs from the master file, on a paper ground for the icons; the favicon and every size under 64 px use the heavier K3 weights (outline 58, thread 72). `scripts/build-og-image.mjs` draws the share image on pine-deep: the mark with paper letters and the ochre thread, the title in Atkinson with the emphasis in ochre, the site name in cream-soft.
- The How it works figure, `src/components/HowItWorks.astro`, is styled as V1 of the round 3 mockups: boxes on paper with 3 unit corners and an ink-soft outline, clay connectors, mono eyebrows, the agent as a prompt chevron in an ink ring, and each engineer's coding agent as the same glyph, small, in clay. Its geometry is unchanged: every connector is the same `line.ln` with the same coordinates and dash pattern, and the agent's ring is the same `circle.tk`, so the drawing script reads it as before. The stacked variant under 1100 px has the same structure. At 1440 px the figure's smallest text renders at about 12.1 px.
- Motion follows one rule, written at the top of `src/styles/chrome.css`: it answers something, happens once, takes 150 to 600 ms for interface feedback, uses one easing family and only transform, opacity, clip and stroke, and is off under reduced motion. The home page diagram draws itself as the reader scrolls it into view (a scroll-driven animation in `src/styles/site.css`, with a timed fallback), the rule above each section heading draws out as the heading enters, and page changes are cross-document view transitions (with a guard in `ThemeScript.astro` that skips a transition still unfinished after 600 ms, since an embedded or automated browser can hold one for seconds).

## Settings

All settings are in `site.config.mjs`.

| Setting | What it does |
| --- | --- |
| `customDomain` | Set to `"carriedcontext.dev"`. The site is built for the root of that domain, and the build writes a `CNAME` file. Empty would build for `https://sct-will.github.io/carrydown/`. See `docs-setup.md` for the DNS and Pages configuration and how to check it. |
| `goatcounterCode` | Empty means no analytics. Set it to your GoatCounter site code, for example `"carried-context"`, and every page loads the GoatCounter script with `data-goatcounter` set to `https://<code>.goatcounter.com/count`. GoatCounter is cookie free. Nothing else is tracked. |
| `INDEXING_ENABLED` | False until launch. While false, every page has `<meta name="robots" content="noindex, nofollow">` and `robots.txt` says `Disallow: /`. See `TODO.md`. |

## How the docs are generated

`scripts/build-docs.mjs` reads the pages listed in `PUBLIC_PAGES` in the script from the repository root: `README.md`, the approved `docs/*.md` files and `sample/expense-approvals/README.md`. An unlisted file in `docs/` is not published, and a listed page missing on disk stops the build. It writes them into Starlight's content collection with front matter, rewrites links between those files to site routes and links to other repository files to their GitHub addresses, copies the images they use, and builds the sidebar from the page titles. A page's title is its first heading, except the README's: on GitHub that heading is the product name, so on the site the page is titled "Documentation", from the page list in the script. The generated files are not committed. Every generated page starts with a line saying which repository file it came from.

To translate a docs page, put a translated copy under `docs/i18n/<locale>/` with the same file name. It is served at `/<locale>/docs/<file>/`. Until then the site shows the English page with a note.

Edit the Markdown in the repository, never the generated pages.

## Site search

The Search button in the header opens a dialog over a Pagefind index. Starlight builds the index into `dist/pagefind/` at the end of `astro build`, over every docs page and every site page whose main element carries `data-pagefind-body`, one index per language. `src/components/SiteSearch.astro` holds the button, the dialog and the keyboard shortcuts (Ctrl K, Cmd K, or "/" outside a text field). `astro dev` builds no index, so the dialog says search works on the published site; `astro preview` serves the built one.

## Copy page and the Markdown files

Every docs page has a Copy page control beside its title, from `src/components/CopyPage.astro` through the `PageTitle` override in `src/components/starlight/`. The button copies the page as Markdown; the menu beside it also opens the Markdown file and the page's source on GitHub. The Markdown file is built next to each page by `src/pages/[...path].md.ts`: `/docs/setup.md` for `/docs/setup/`, and `/de/docs/setup.md` for the German route. It is the generated page with its links made absolute and its images pointed at the repository on the branch named by `sourceBranch` in `site.config.mjs`.

## The llms.txt files

`scripts/build-llms.mjs` writes two files for agents, in the format at [llmstxt.org](https://llmstxt.org/), from the built site:

- `llms.txt`: the definition, what the site and carrydown are, the plan owner and engineer phrases from the README's "What to tell your agent, and when" section, then the pages. A docs page links to its Markdown file. A site page has no Markdown file, so it links to its HTML page. Redirect pages are left out.
- `llms-full.txt`: the whole Markdown of the documentation and the site pages, in the same order, each headed by its title and its address. A docs page is its Markdown file as served. A site page is the main content of the built page, converted to Markdown.

The reading order is a short list of paths at the top of the script. A new docs page that is not on it is added at the end of the Documentation section. A worked example and the accessibility statement are listed under Optional, the section a reader may skip, and are left out of `llms-full.txt`.

## Search engines and sharing metadata

`src/components/Seo.astro` writes the title, description, canonical link, Open Graph and Twitter tags and the JSON-LD for each page. The docs get the same tags through `src/components/starlight/Head.astro`. The text for each page is in `src/seo/pages.ts`, which reads the locale strings in `src/i18n/`.

## Deploy

`.github/workflows/website.yml` builds, tests and deploys to GitHub Pages on a push to `main`. It uses no secret beyond the built-in `GITHUB_TOKEN`. The Pages source must be set to GitHub Actions, as in `docs-setup.md`.
