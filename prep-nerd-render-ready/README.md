# prep-Nerd.ai API

A responsive Flask web app for the prep-Nerd.ai study workspace. Render runs the application through `wsgi.py`; Flask serves the included frontend at `/` and the JSON API from the same origin. The former Streamlit interface has been replaced.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set SECRET_KEY to a private random value. Set GEMINI_API_KEY for AI features.
flask --app app run --host 0.0.0.0 --port 5000
```

The default SQLite file is `instance/prep_nerd.db`; override it with `DATABASE_PATH`. The database is initialized on startup. The existing root-level `prep_nerd.db` is sample content and is not used by the API or included as a deployment database. Add `GEMINI_API_KEY` to `.env` to enable AI. The default model is `gemini-3.8-flash`; set `GEMINI_MODEL` to override it. Ordinary public webpages can still be imported without a key using the safe HTML text extractor; Gemini URL Context is attempted when a key is configured. YouTube processing requires a key and generates detailed study notes, not a claimed full or verbatim transcript.

## Render deployment

1. Push this project to a Git repository and create a Render **Blueprint** from it, or create a Python web service using `render.yaml`.
2. Confirm the service uses the **Starter** plan. The Blueprint creates a 1 GB persistent disk at `/var/data` and sets `DATABASE_PATH=/var/data/prep_nerd.db`.
3. Render generates `SECRET_KEY` securely. Set `GEMINI_API_KEY` in the service's Environment settings if AI features are required; do not commit it. `GEMINI_MODEL` defaults to `gemini-3.8-flash`.
4. Deploy. Render runs `pip install -r requirements.txt` and `gunicorn wsgi:app`.

The SQLite disk preserves data across deploys but is attached to this single service instance; it is not a multi-instance database. Back up the disk/database before destructive infrastructure changes.

## Workspace identity and security limitation

There is **no OAuth, account system, or user authentication** in this API. A signed, HttpOnly, SameSite=Lax Flask session cookie carries an anonymous workspace UUID; database `user_id` ownership ensures normal API queries and mutations are scoped to that UUID. Anyone who possesses or copies that cookie can use that workspace, and clearing/replacing the cookie creates a different workspace. Do not treat this as identity verification or confidential per-user account security. Production cookies are Secure; local HTTP cookies are not.

All state-changing API routes require `X-CSRF-Token`, obtained from `GET /api/bootstrap` as `csrf_token`. Keep the session cookie and CSRF token together in the frontend. Uploads are capped at 20 MB; request bodies are capped at 25 MB. A lightweight per-IP request limit is enabled. URL extraction rejects private/internal network destinations and validates redirects.

## API

All responses are JSON. Errors use `{ "error": "..." }` and do not expose SDK exception details or secrets.

- `GET /api/bootstrap` — CSRF token, active source (including content), source list, artifacts, mistakes, AI configuration and model.
- `POST /api/sources` — JSON `{ "kind":"text", "title":"...", "text":"..." }`; JSON `{ "kind":"url", "url":"https://..." }`; or multipart form with explicit `kind=file` and `file`. A successful import becomes active; a failed import leaves the active source unchanged.
- `POST /api/sources/<id>/activate` — activate a source in this workspace.
- `DELETE /api/sources/<id>` — delete an owned source; deleting the active source switches to the newest remaining source.
- `POST /api/generate` — `{ "action":"summary|notes|quiz|flashcards|mock_exam", "style", "difficulty", "count", "depth", "title" }`. Quiz/mock-exam `count` must be 5, 10, 15, 20, or 25. The generated artifact is saved and returned as `{ "artifact": ... }`.
- `POST /api/chat` — `{ "question":"..." }`; answer uses the active source.
- `GET /api/artifacts?kind=...` — list owned artifacts, optionally filtered by kind.
- `PATCH /api/artifacts/<id>` — `{ "title":"...", "payload": ... }`.
- `POST /api/grade` — `{ "kind":"quiz|mock_exam", "title":"...", "questions":[...], "answers":{ "0":"A" } }`; deterministic score and any missed questions are saved.
- `PATCH /api/mistakes/<id>` — `{ "status":"Reviewed|Needs More Practice" }`.

Example authenticated state-changing request after bootstrap:

```bash
curl -b cookies.txt -c cookies.txt \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF_TOKEN" \
  -d '{"kind":"text","title":"Cell biology","text":"Mitochondria produce ATP through cellular respiration."}' \
  http://localhost:5000/api/sources
```

## Verification

```bash
python -m py_compile app.py wsgi.py core/*.py
pytest -q
```
