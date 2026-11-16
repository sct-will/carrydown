# Custom domain setup

The site is served at `https://sct-will.github.io/carrydown/` until the custom domain is on. Then it is served at `https://carried-context.dev/`. These are the steps for later. Nothing here is needed to build or deploy the site today.

## 1. DNS records at Squarespace

Open the DNS settings for `carried-context.dev` at Squarespace and add these records.

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
2. Under Custom domain, enter `carried-context.dev` and save. GitHub checks the DNS records.
3. When the check passes, tick Enforce HTTPS. GitHub issues the certificate, which can take up to an hour.

## 3. Switch the build to the domain

In `website/site.config.mjs`, set `customDomain` to `"carried-context.dev"`. The build then uses `https://carried-context.dev` as the site address and `/` as the base path, and writes a `CNAME` file into the output. Commit and let the workflow deploy.

## 4. Check

- `https://carried-context.dev/` loads over HTTPS.
- `https://www.carried-context.dev/` redirects to the apex.
- The old address `https://sct-will.github.io/carrydown/` redirects to the new one.

## 5. Launch steps

The search engine steps are in `TODO.md`.
