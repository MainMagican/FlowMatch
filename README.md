# FlowMatch

FlowMatch is a demo full-stack workflow/opportunity-matching platform for
large organizations. It helps employees:

- Break silos across departments by discovering and understanding end-to-end
  workflows outside their own team.
- Scale up by shadowing colleagues, offering to teach a skill, or requesting
  help.
- Push backlog tasks across departments so anyone with the right skill can
  pick them up.
- Discover cross-department opportunities to automate or share solutions
  with colleagues facing similar challenges.

Built with **Flask + stdlib `sqlite3`** on the backend and **vanilla
HTML/CSS/JS** on the frontend (no build tooling, no Node.js required).

## Project structure

```
flowmatch/
  backend/    Flask API (app/, tests/)
  frontend/   Static HTML/CSS/JS app + simple dev server (serve.py)
```

## Running locally

### Backend (API, default port 8100)

```powershell
cd flowmatch/backend
pip install -r requirements.txt
python -m app.main
```

The first run seeds a demo dataset (~239 synthetic users across 14
departments) into `flowmatch.db` (git-ignored, regenerated automatically).

### Frontend (static server, default port 5600)

```powershell
cd flowmatch/frontend
python serve.py
```

Then open `http://127.0.0.1:5600` in your browser and log in as any of the
seeded demo users.

## Running tests

```powershell
cd flowmatch/backend
python -m pytest tests -q
```

## Notes

- This is a demo/prototype app — the login flow uses simple dev-mode tokens,
  not production authentication.
- `flowmatch.db` is regenerated from seed data on first run and is not
  committed to source control.
