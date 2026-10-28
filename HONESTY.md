# HONESTY.md

## Tested and working (ran locally, saw the result)
- **CV output** — generated on a throwaway DB with a fake profile: filename
  `Syed_Maaz_Saif_Product_Manager.pdf`, PDF + Word copy both written to the
  chosen `cv_folder`, PDF text extractable (ATS-safe).
- **Cover letters + screener answers** — fact-based, cover letter saved as PDF.
- **Follow-up assistant** — returns only "Applied" jobs with no reply after 5
  days (correctly excluded a replied job).
- **"Where am I stuck"** — diagnosis returns the expected heading.
- **ATS keyword check** — correct missing keywords + profile tips.
- **Company careers-page scanning** — ATS detection unit-tested (Greenhouse,
  Lever, Ashby, embed URL, no-ATS); live Greenhouse "stripe" fetch returned 714
  jobs.
- Existing suite: `python -m unittest discover -s tests` → 30 tests pass.
- `backend.main` imports cleanly; `npm run build` succeeds; electron files pass
  `node --check`.

## Partial / unproven
- The desktop app was not launched in this environment — no GUI click-through.
  All UI, apply-window buttons, and the `cv_folder` migration against the live
  database (runs on next app start) need a real launch to confirm.
- Lever and Ashby live fetches were not run (only Greenhouse verified live).

## Needs human review
- Privacy: generated files and the profile stay local. `cv_folder` is a user-set
  path; no name/path is hard-coded. // HUMAN REVIEW NEEDED: resume/profile data
- "Attach CV" reveals the file in Finder/Explorer (one drag away); it does not
  inject files into a job site's upload field — browsers block that, and the
  app's rule is "you apply yourself; the app never submits for you".
