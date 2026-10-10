# Kranti Job Hunter

Twice a day (about 06:47 and 16:47 German time) this repo searches for every new
SAP Commerce Cloud / Hybris / e-commerce opening in Germany and remote in the EU,
scores each one against `cv.md`, and emails a ranked digest.

## What it searches

| Source | How |
|---|---|
| Bundesagentur für Arbeit (Arbeitsagentur) | Job-search API (unofficial, used by the official app) |
| LinkedIn | JobSpy library, Germany + remote-EU pass |
| Indeed.de | JobSpy library |
| LinkedIn recruiter posts ("#hiring SAP Commerce…") | Google search via Serper.dev (optional, `SERPER_API_KEY`) |

Every keyword in `config.yaml` → `queries` runs on every source. Tiers:
SAP Commerce/Hybris → other commerce platforms (Salesforce Commerce Cloud,
commercetools, Spryker, Shopware…) → e-commerce analyst/consultant/PO roles →
adjacent (Java for e-commerce, SAP CPQ, PIM).

A job is kept if its title/description mentions one of `relevance_terms`, and
dropped if its title has one of `exclude_title_terms` (internships, warehouse,
sales). The same job on several boards is shown once, and a job is never sent twice.

## The digest

Every job shows its age (🆕 ≤1 day, 2–3 days, 4–7 days, 7+ days); newest first within each group. Each run looks back 7 days, but a job is only ever sent once.

Split into 🇬🇧 **English-speaking** and 🇩🇪 **German-speaking** jobs (posting in German or fluent German required), each ranked separately:

- 🎯 **Strong match** (80+), 👍 **Good fit / can learn** (60–79), 👀 **Worth a look** (30–59), 🗂 **Low match** (titles only)
- Each job: score, title, company, location, remote flag, salary if posted, and a one-line reason.
- **Source health** at the bottom: a ⚠️ means a source returned nothing or failed, so you know if something is being missed.

## Setup (GitHub → Settings → Secrets and variables → Actions)

| Secret | Needed | Notes |
|---|---|---|
| `TO_EMAIL`, `TO_EMAIL_2` | yes | One address each (or comma-separated) |
| `GMAIL_USER` + `GMAIL_APP_PASSWORD` | one email method | Gmail App Password (Google account → Security → App passwords). Used first |
| `RESEND_API_KEY` + `FROM_EMAIL` | optional backup | Without a verified domain, Resend only delivers to the Resend account's own address |
| `GEMINI_API_KEY` | recommended | AI scoring (free tier is enough) |
| `SERPER_API_KEY` | optional | Free key from serper.dev (2,500 searches, no card). Enables LinkedIn recruiter posts |
| `GROQ_API_KEY` | optional | Backup AI scorer. Without any AI key, keyword scoring is used |

Test it: **Actions → Job hunt → Run workflow** (tick *Dry run* to only preview;
the digest is attached to the run as an artifact). Tick *Only send a test email*
to check email delivery in under a minute.

## Files

- `config.yaml` – keywords, filters, locations
- `cv.md` – candidate profile used for scoring (update when the CV changes)
- `hunter/` – code (`sources.py`, `score.py`, `digest.py`, `main.py`)
- `data/seen.json` – jobs already sent (kept 90 days)
- `data/jobs_log.csv` – every job ever sent, opens in Excel

## Limits

LinkedIn and Indeed sometimes block automated searches; the health section shows
when that happens. StepStone and XING aren't scraped (they block bots). For full
coverage also keep email alerts on StepStone, XING and LinkedIn for "SAP Commerce" / "Hybris".
