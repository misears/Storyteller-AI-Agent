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
Use PDF library roles to separate core rules, mechanical supplements, lore, and published chronicles.
Unclassified legacy PDFs remain references until you assign their purpose. XP review and rules lookup
search only selected core-rule and supplement PDFs. Chronicle sources stores a selected scenario
book and page; the GM receives a bounded page window during turns.

## Backups and saves

Use named campaign saves before major changes. Campaign export excludes source PDFs. Keep a copy of
the exported archive and the local data directory when making a release backup.
Back up `character_sheets.json` with the rest of the data directory: XP balances, pending requests,
AI reviews, and human decisions are stored there. Campaign branch saves do not rewind the XP ledger.

## Security boundaries

The local server defaults to loopback origins. Clients never provide dice results. Secrets and GM-only
content must remain in GM-visible events and must not be copied into public narration.

Advancement approval and chronicle-source configuration are restricted to loopback clients on the
host computer. Approval requires an explicit human confirmation, name, and reason after a positive
server-generated AI review. This is a trusted desktop-operator workflow, not authenticated user roles:
do not expose the application through a public reverse proxy or claim that same-machine users are
isolated from one another. Player-supplied data cannot directly write XP or AI review results.