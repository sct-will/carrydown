# Custom domain setup

The site is served at `https://sct-will.github.io/carrydown/` until the custom domain is on. Then it is served at `https://carriedcontext.dev/`. These are the steps for later. Nothing here is needed to build or deploy the site today.

## 1. DNS records at Squarespace

Open the DNS settings for `carriedcontext.dev` at Squarespace and add these records.

| Host | Type | Value |
| --- | --- | --- |
| `@` (the apex) | A | 185.199.108.153 |
| `@` (the apex) | A | 185.199.109.153 |
| `@` (the apex) | A | 185.199.110.153 |
| `@` (the apex) | A | 185.199.111.153 |
| `www` | CNAME | sct-will.github.io |

Remove any other A or CNAME records for the apex and for `www`, such as the default Squarespace ones. Do not add a trailing path to the CNAME value.

DNS changes can take from a few minutes to a day to spread.

## 2. Pages settings on GitHub

In the repository, open Settings, then Pages.

1. Under Build and deployment, set Source to GitHub Actions.
2. Under Custom domain, enter `carriedcontext.dev` and save. GitHub checks the DNS records.
3. When the check passes, tick Enforce HTTPS. GitHub issues the certificate, which can take up to an hour.

## 3. Switch the build to the domain

In `website/site.config.mjs`, set `customDomain` to `"carriedcontext.dev"`. The build then uses `https://carriedcontext.dev` as the site address and `/` as the base path, and writes a `CNAME` file into the output. Commit and let the workflow deploy.

## 4. Check

- `https://carriedcontext.dev/` loads over HTTPS.
- `https://www.carriedcontext.dev/` redirects to the apex.
- The old address `https://sct-will.github.io/carrydown/` redirects to the new one.

## 5. Launch steps

The search engine steps are in `TODO.md`.

## What was set on the repository, 16 November 2026

- GitHub Actions is enabled, restricted to actions written by GitHub and by verified creators. The website workflow uses GitHub's own actions only, pinned by commit.
- GitHub Pages is enabled with the build type set to the workflow, so every deploy comes from the website workflow and nothing is served from a branch.
- A placeholder branch named gh-pages exists with one README. GitHub required a branch to exist before Pages could be turned on, and turning the branch off turns Pages off with it. Leave the branch alone.
- The github-pages environment allows deploys from main and from the website branch. Remove the website branch from that list after the merge.
