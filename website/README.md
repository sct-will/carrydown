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

1. `scripts/build-docs.mjs` generates the docs pages from `README.md`, `docs/*.md` and `sample/expense-approvals/README.md`.
2. `astro build` writes the site to `dist/`.
3. `scripts/build-og-image.mjs` renders the 1200 by 630 social image to `dist/og-image.png`.
4. `scripts/build-llms.mjs` writes `dist/llms.txt` from the built pages.
5. `scripts/build-robots.mjs` writes `dist/robots.txt`.

To refresh the committed `public/og-image.png` after changing the image script, run `node scripts/build-og-image.mjs --public`.

## Test

Build first, then:

```bash
npm test
```

This runs, in order:

- `scripts/check-docs-sync.mjs` regenerates the docs into a temporary folder and fails with a diff if the generated pages differ from the repository's Markdown.
- `tests/routes.mjs` starts `astro preview` and expects 200 for every page, in every locale, and for every internal link and asset.
- `tests/reflow.mjs` takes screenshots of a bounded set of pages (the four site pages at six widths, plus Japanese, docs and fallback samples) in both themes into `tests/screenshots/` and fails on horizontal overflow, text under 12 px and tap targets under 44 px.
- `tests/a11y.mjs` runs axe-core on a bounded set (the four site pages in every locale in both themes, every English docs page and one fallback docs page per locale in light) and fails on any violation.

Type checks: `npx astro check`.

## Design

The design is the round 2 mock-up in `specs/carried-context-site/mockups-v2/` (paper and thread), carried into the site in November 2026.

- Type: Fraunces for display, with its optical size axis set per size; Atkinson Hyperlegible Next for text, with true small capitals for the eyebrow labels, old-style figures in running text and tabular figures where numbers line up; Geist Mono for code. All three are self-hosted from their Fontsource packages, imported in `src/styles/tokens.css`. Chinese and Japanese pages put a native sans after the text face and a native serif after the display face (`src/styles/locales.css`).
- The second line of the home page title stays one string in the locale file; the `h1Emphasis` key beside it names the part set in the amber, upright in the same face. A translation may move that part or leave it empty.
- Theme: light is the default. The control offers Light, Dark and Auto; the choice is kept in `localStorage` under `cc-theme` and resolved to `data-theme` on `<html>` before first paint by `src/components/ThemeScript.astro`. The tests reach the dark theme by storing that choice.
- Motion follows one rule, written at the top of `src/styles/chrome.css`: it answers something, happens once, takes 150 to 600 ms for interface feedback, uses one easing family and only transform, opacity, clip and stroke, and is off under reduced motion. The home page diagram draws itself as the reader scrolls it into view (a scroll-driven animation in `src/styles/site.css`, with a timed fallback), page changes are cross-document view transitions (with a guard in `ThemeScript.astro` that skips a transition still unfinished after 600 ms, since an embedded or automated browser can hold one for seconds), and a theme change crossfades.

## Settings

All settings are in `site.config.mjs`.

| Setting | What it does |
| --- | --- |
| `customDomain` | Empty until the domain is connected. Empty means the site is built for `https://sct-will.github.io/carrydown/`. Set it to `"carriedcontext.dev"` to build for the root of that domain and write a `CNAME` file. See `docs-setup.md` for the DNS and Pages steps. |
| `goatcounterCode` | Empty means no analytics. Set it to your GoatCounter site code, for example `"carried-context"`, and every page loads the GoatCounter script with `data-goatcounter` set to `https://<code>.goatcounter.com/count`. GoatCounter is cookie free. Nothing else is tracked. |
| `INDEXING_ENABLED` | False until launch. While false, every page has `<meta name="robots" content="noindex, nofollow">` and `robots.txt` says `Disallow: /`. See `TODO.md`. |

## How the docs are generated

`scripts/build-docs.mjs` reads `README.md`, every `docs/*.md` and `sample/expense-approvals/README.md` from the repository root. It writes them into Starlight's content collection with front matter, rewrites links between those files to site routes and links to other repository files to their GitHub addresses, copies the images they use, and builds the sidebar from the page titles. The generated files are not committed. Every generated page starts with a line saying which repository file it came from.

To translate a docs page, put a translated copy under `docs/i18n/<locale>/` with the same file name. It is served at `/<locale>/docs/<file>/`. Until then the site shows the English page with a note.

Edit the Markdown in the repository, never the generated pages.

## Site search

The Search button in the header opens a dialog over a Pagefind index. Starlight builds the index into `dist/pagefind/` at the end of `astro build`, over every docs page and every site page whose main element carries `data-pagefind-body`, one index per language. `src/components/SiteSearch.astro` holds the button, the dialog and the keyboard shortcuts (Ctrl K, Cmd K, or "/" outside a text field). `astro dev` builds no index, so the dialog says search works on the published site; `astro preview` serves the built one.

## Copy page and the Markdown files

Every docs page has a Copy page control beside its title, from `src/components/CopyPage.astro` through the `PageTitle` override in `src/components/starlight/`. The button copies the page as Markdown; the menu beside it also opens the Markdown file and the page's source on GitHub. The Markdown file is built next to each page by `src/pages/[...path].md.ts`: `/docs/setup.md` for `/docs/setup/`, and `/de/docs/setup.md` for the German route. It is the generated page with its links made absolute and its images pointed at the repository on the branch named by `sourceBranch` in `site.config.mjs`.

## Search engines and sharing metadata

`src/components/Seo.astro` writes the title, description, canonical link, Open Graph and Twitter tags and the JSON-LD for each page. The docs get the same tags through `src/components/starlight/Head.astro`. The text for each page is in `src/seo/pages.ts`, which reads the locale strings in `src/i18n/`.

## Deploy

`.github/workflows/website.yml` builds, tests and deploys to GitHub Pages on a push to `main`. It uses no secret beyond the built-in `GITHUB_TOKEN`. The Pages source must be set to GitHub Actions, as in `docs-setup.md`.
