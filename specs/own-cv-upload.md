# Own CV upload

## Goal

Let Maaz keep his own latest CV in the app, separate from the CVs the app
generates from his profile. When he applies, the **Attach CV** button in the
apply window reveals his own uploaded CV (so he can drag it into the job form).
If he has not uploaded one, the button falls back to the generated CV for that
job.

## What changes

1. **Backend** — a new `uploaded_cv` table and `/api/own-cv` endpoints
   (upload / list / download / delete). Files are stored under
   `backend/data/own_cv/`, kept as-is, never parsed into the profile.
2. **Profile page** — a new "Your own resume" box with **Upload CV**, plus
   Download / Reveal in folder / Remove for each uploaded file.
3. **Apply window** — `📎 Attach CV` now asks the backend for the latest own CV
   and reveals that; falls back to the generated CV when none exists.

## Not in scope

- Parsing the uploaded CV into profile records (that is the existing
  "Upload resume" flow and stays unchanged).
- Auto-attaching the file into web forms. The app only reveals the file in the
  OS file manager, as it does today; Maaz drags it in himself.

## Ideas for later

- A per-job choice of "my CV vs generated CV" right in the apply toolbar.
- Remember which CV was used for each application.
