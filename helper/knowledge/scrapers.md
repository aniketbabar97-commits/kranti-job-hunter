# Job search / scraping approaches

## StepStone (farhadvaseghi/job-scraper, verified 2026-08; kdkiss/mcp-stepstone)
- URL: `https://www.stepstone.de/jobs/<term>/in-<zip>?radius=<km>&ag=age_7&q="<term>"`. Do NOT add `action=facet_selected;age;age_7`, because that query black-holes the request (it hangs until timeout).
- Plain `requests` from datacenter IPs hangs. A real headless Chromium (Playwright) gets the page.
- Card hooks: `[data-at="job-item"]`, `job-item-title`, `job-item-company-name`, `job-item-location`, `job-item-timeago`. Older or alternate markup: `article[data-testid="job-item"]`, `[data-testid*=job-title]`. Fallback: anchors matching `/stellenangebote--*.html`. Card text is `|`-separated.
- Block fingerprints to log: cloudflare, captcha, "are you a human", "access denied", "unusual traffic", px-captcha (PerimeterX), datadome, incapsula.

## XING
- Option A (Playwright): cards `[data-testid="job-search-result"]` (20 per page), fallbacks `job-teaser`, `article[data-testid]`. Title `[data-testid="job-teaser-list-title"]`, links `/jobs/<city>-<slug>-<id>`, `time` for age, `[data-testid="apply-button"]` ("Einfach bewerben" = easy apply vs external). Zero results usually means a block or consent wall, not bad selectors.
- Option B (robots-friendly, no browser): `https://www.xing.com/jobs/sitemap.xml.gz` is a sitemap index whose chunks hold about 50k URLs each. Keyword-match the URL slug, then fetch the job page and parse `script[type="application/ld+json"]` (JobPosting). `/jobs/search` is disallowed in robots.txt (nidhicj).

## Bundesagentur für Arbeit (official API)
- `GET https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs?was=<kw>&wo=<ort>&umkreis=<km>&veroeffentlichtseit=<days>&page=1&size=50` with header `X-API-Key: jobboerse-jobsuche` (the public client id). v4/v5 now return "403 No match found". v6 renamed fields: `ergebnisliste`, `referenznummer`, `stellenangebotsTitel`, `firma`, `stellenlokationen[0].adresse.ort`, `datumErsteVeroeffentlichung`, `vertragsdauer`. Docs: jobsuche.api.bund.dev.

## Glassdoor (JobSpy, MIT)
- GraphQL POST `https://www.glassdoor.<tld>/graph` with a `gd-csrf-token` header (JobSpy ships a static token that still works) and `JobSearchResultsQuery`. Location id comes from `/autocomplete/location`. Uses `curl_cffi` for a TLS fingerprint. Heavy Cloudflare protection, so expect 403s without a proxy.

## Google Jobs (JobSpy)
- `https://www.google.com/search?q=<q>&udm=8` (jobs vertical). Pagination via `https://www.google.com/async/callback:550?fc=<data-async-fc>&fcv=3&async=<param>`, where the cursor is read from `div[jsname="Yust4d"][data-async-fc]`. Fragile, because the async param is version-pinned.

## LinkedIn guest API (JobSpy)
- `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=&location=&f_TPR=r86400&start=N`, and details at `/jobs-guest/jobs/api/jobPosting/<id>`. No login needed. Rate-limited (HTTP 429 after about 10 pages per IP).

## Workday CXS (public JSON)
- Search: `POST https://<tenant>.wdN.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs` with body `{"appliedFacets":{},"limit":20,"offset":0,"searchText":"<kw>"}`. The response has `total` and `jobPostings[].externalPath`. Location facets go in `appliedFacets.locations`/`locationCountry` (ids from the `facets` in the response).
- Detail: `GET https://<host>/wday/cxs/<tenant>/<site>/job/<slug>` (path = externalPath without `/job/`). Gives `jobPostingInfo.title`, `jobDescription`, `jobReqId`, `canApply`, `postedOn`. A 404 or `canApply:false` means closed (PS12007 precheck.py). The site is the path segment after the optional locale: `/en-US/<site>/job/...`.

## SuccessFactors search
- None of the repos had an API. Career sites (`career<N>.successfactors.com/career?company=<id>` or the custom RMK domain `/search/?q=&locationsearch=&startrow=N`) are server-rendered, with rows `tr.data-row` / `a.jobTitle-link`. Many RMK sites expose `/sitemap.xml`.

## Other public ATS feeds
- Greenhouse `boards-api.greenhouse.io/v1/boards/<t>/jobs`, Lever `api.lever.co/v0/postings/<c>?mode=json`, Ashby `api.ashbyhq.com/posting-api/job-board/<org>`, Personio XML `https://<c>.jobs.personio.de/xml`, Arbeitnow `https://www.arbeitnow.com/api/job-board-api` (DE, free).
