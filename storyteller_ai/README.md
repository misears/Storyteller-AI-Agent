# Storyteller AI

Storyteller AI is a local-first tabletop RPG campaign assistant. The FastAPI backend serves the React interface, campaign APIs, event history, dice, document library, and AI provider settings.

## Install and play

For the Windows installer, setup, repair, and data locations, see [the installer guide](../windows_installer/README.md). For player workflows, see [the end-user tutorial](END_USER_TUTORIAL.md) and [quick-start card](QUICK_START_CARD.md).

The installed app binds to loopback and opens its browser UI. AI provider selection, local model management, and protected cloud-key entry are available from **AI provider setup** in the app.

## Developer workflow

- Python dependencies: `requirements.txt`; development tools: `requirements-dev.txt`.
- Web source: `web/`; build with `npm ci` and `npm run build` from that directory. Vite writes production assets to `frontend/dist/`.
- Start the backend from this directory with `python desktop_entry.py`. Desktop mode refuses non-loopback host overrides.
- Run tests and lint with `scripts/run_test_lint.ps1` from PowerShell. The script supplies the repository root for the benchmark package import and restores the previous `PYTHONPATH` afterward.
- Campaign/event data and AI preferences are stored separately from source. Provider credentials are protected with Windows DPAPI and are never included in installer artifacts.

See [the task tracker](../docs/IMPLEMENTATION_TASKS.md) for implementation and release status. The older [setup scaffold](../SETUP_STORYTELLER_TASK.md) is historical context, not an active generator.