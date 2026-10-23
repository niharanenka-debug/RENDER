# Build status

This release converts Prep Nerd from Streamlit to a Flask web app deployable on Render. The app serves its bundled responsive frontend and JSON API from one service.

Implemented features include the dashboard, summarizer, flashcards, grounded study chat, quizzes, timed mock exams, and mistake notebook. A single active source is stored in the browser's signed workspace session; every study operation loads that active source. New text, file, or URL source becomes active across all tools. Explicit source-kind selection prevents a stale hidden upload from overriding a URL; failed imports leave the previous source active.

File uploads support TXT, PDF, Markdown, PPTX, and DOCX. Public webpage imports use Gemini URL Context when configured, falling back to the existing safe page-text extractor. Public YouTube URLs use Gemini's video input to create detailed study notes (not a claimed full transcript).

## Verification

- `python3 -m py_compile app.py wsgi.py core/*.py` — passed.
- `pytest -q` — passed, including source activation, latest-source behavior, failed-import behavior, session isolation, and app/static serving tests.
- `node --check static/app.js` — passed; frontend uses safe text-node rendering for model output.
- Render-style Gunicorn smoke test — homepage, static assets, and `/api/bootstrap` returned HTTP 200.
- Gemini requests were not tested because this environment has no configured `GEMINI_API_KEY`.

## Deployment notes

- `render.yaml` creates a Starter web service and a 1 GB persistent disk mounted at `/var/data` for SQLite.
- Configure `GEMINI_API_KEY` in Render's environment settings to enable Gemini features.
- Workspaces use anonymous signed cookies, not OAuth or account authentication.
- The local SQLite disk is attached to one service instance and is not a multi-instance database.
- Legacy `.ppt` files remain unsupported; use `.pptx`.
