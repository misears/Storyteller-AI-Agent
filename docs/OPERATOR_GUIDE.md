# Storyteller AI Operator Guide

## Run locally

Start the backend from `storyteller_ai` with the project environment and bind it to
`127.0.0.1`. The server runs SQLite migrations at startup and serves the React build from
`frontend/dist` when present; otherwise it falls back to the legacy pages.

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'storyteller_ai')
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Build the web client only when frontend source changes:

```powershell
Set-Location storyteller_ai/web
npm install
npm run build
```

Runtime data and uploaded PDFs belong under `backend/data` and are not committed. Keep source
documents selected per campaign; rule lookup will not search unselected documents.

## Backups and saves

Use named campaign saves before major changes. Campaign export excludes source PDFs. Keep a copy of
the exported archive and the local data directory when making a release backup.

## Security boundaries

The local server defaults to loopback origins. Clients never provide dice results. Secrets and GM-only
content must remain in GM-visible events and must not be copied into public narration.