# To do

Before launch: set INDEXING_ENABLED to true, remove the robots Disallow, submit the sitemap, verify the domain in Search Console.

Details:

- `INDEXING_ENABLED` is in `site.config.mjs`. One flag drives the `noindex, nofollow` meta tag on every page and `robots.txt`. Setting it to true removes the tag and writes `Allow: /` with the sitemap line.
- The sitemap is `sitemap-index.xml` in the site root. Submit it in Search Console after the custom domain is live.
- Verify the domain in Search Console with a DNS TXT record at the registrar. See `docs-setup.md` for the other DNS records.
