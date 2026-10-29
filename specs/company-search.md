# Find a company by name (job sources)

## Goal
Let the user type a company name and have the app find that company's careers
page, detect its job system, and add it as a job source with one tap.

## What exists already
- **Custom sources** (Settings → "Your own job sources"): RSS, Greenhouse,
  Lever, Ashby, company careers URL, generic URL. This is the "add a job board"
  capability — already shipped.
- `backend/company_site.py::find_company_site()` resolves a company's careers
  page (follow redirects, then search "<company> careers" via DuckDuckGo/Bing).
- `backend/custom_scrapers.py::_detect_ats()` detects Greenhouse/Lever/Ashby.

## What this adds
- A backend `POST /api/settings/sources/resolve` endpoint: `{name}` →
  `{found, url, kind, value, label}` using the existing resolver + ATS detector.
- A "Find a company by name" field in `CustomSources.jsx`: type a name, see what
  was found (company + detected system), one tap to add it. It then joins the
  normal scan.

## Out of scope
- Scanning a company immediately on add (jobs appear on the next/daily scan, or
  the on-demand scan).
- Editing the resolved URL before adding.

## Test plan
- Backend unit test for the resolve endpoint (mocked resolver)
- `npm run build` + full backend suite
