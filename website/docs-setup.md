# Custom domain reference

The site is served at `https://carriedcontext.dev/`. GitHub Pages serves it from the website workflow. This page records what is configured and how to check it. Every check below is read only.

## What is configured

### DNS records

The domain's DNS is hosted at Squarespace. It has these records.

| Host | Type | Value |
| --- | --- | --- |
| `@` (the apex) | A | 185.199.108.153 |
| `@` (the apex) | A | 185.199.109.153 |
| `@` (the apex) | A | 185.199.110.153 |
| `@` (the apex) | A | 185.199.111.153 |
| `www` | CNAME | sct-will.github.io |

Keep no other A or CNAME records for the apex or for `www`. The CNAME value has no trailing path. A Search Console verification record, when it is added, is a TXT record and does not affect these. See `TODO.md`.

### GitHub Pages

In the repository settings, under Pages:

- Source is GitHub Actions. Every deploy comes from the website workflow, and nothing is served from a branch.
- The custom domain is `carriedcontext.dev`, and the domain is verified.
- Enforce HTTPS is on. The certificate covers `carriedcontext.dev` and `www.carriedcontext.dev`. GitHub renews it.

### Build settings

In `website/site.config.mjs`, `customDomain` is `'carriedcontext.dev'`. The build then uses `https://carriedcontext.dev` as the site address and `/` as the base path. Emptying it would build for `https://sct-will.github.io/carrydown/` instead. Do not do that while the domain is on.

### The CNAME file

The build writes a `CNAME` file into `website/dist/` with the line `carriedcontext.dev`. The integration in `website/astro.config.mjs` writes it whenever `customDomain` is set. It is not committed.

## How to check it

```bash
gh api repos/sct-will/carrydown/pages
dig +short carriedcontext.dev
dig +short www.carriedcontext.dev CNAME
curl -sI https://carriedcontext.dev/
curl -sI http://carriedcontext.dev/
curl -sI https://www.carriedcontext.dev/
curl -sI https://sct-will.github.io/carrydown/
cat website/dist/CNAME
```

Expect:

- The Pages API shows `"cname":"carriedcontext.dev"`, `"build_type":"workflow"`, `"protected_domain_state":"verified"`, `"https_enforced":true` and a certificate in the `approved` state with its expiry date.
- The apex resolves to the four addresses in the table, and `www` is a CNAME for `sct-will.github.io`.
- `https://carriedcontext.dev/` answers `200`.
- `https://www.carriedcontext.dev/`, `http://carriedcontext.dev/` and the old address `https://sct-will.github.io/carrydown/` answer `301` to `https://carriedcontext.dev/`. A path is kept, for example `/definition/`.
- After a build, `website/dist/CNAME` holds `carriedcontext.dev`.

Last checked 2026-11-22. All of the above held. The certificate expires 2027-02-14 and is renewed by GitHub.

## Launch steps

The search engine steps are in `TODO.md`.

## What was set on the repository, 2026-11-16

- GitHub Actions is enabled, restricted to actions written by GitHub and by verified creators. The website workflow uses GitHub's own actions only, pinned by commit.
- GitHub Pages is enabled with the build type set to the workflow, so every deploy comes from the website workflow and nothing is served from a branch.
- A placeholder branch named gh-pages exists with one README. GitHub required a branch to exist before Pages could be turned on, and turning the branch off turns Pages off with it. Leave the branch alone.
- The github-pages environment allows deploys from main and from the website branch.

## Open maintenance step

The website branch has merged. Remove it from the github-pages environment's list of branches allowed to deploy, and remove gh-pages from that list too if nothing deploys from it. On 2026-11-22 the list named main, website and gh-pages.
