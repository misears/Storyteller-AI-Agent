Storyteller AI Quick Start Card
===============================

Use this if you want the fastest possible setup and first game.

Before You Start
----------------

- Windows PC
- Python installed

Fast Start (First Time)
-----------------------

1. Double-click `install_dependencies.bat`.
2. Wait until it says installation is complete.
3. Double-click the desktop shortcut **Storyteller AI** (or run `launch_storyteller_ai.bat`).
4. Open <http://127.0.0.1:8000/>

Start Your First Game
---------------------

1. Click **Setup**.
2. In **Create game session**:
   - Choose mode (`group`, `solo`, or `assistant`)
   - Add a title
   - Pick a setting
   - Click **Create Game**
3. Copy the **Session ID** shown in the result panel.
4. (Optional) Upload PDFs in Setup so the game can use your reference material.
5. Click **Go to Story Console**.
6. Paste Session ID, type your first action, click **Continue Story**.

Offline Mode (No Cloud API)
---------------------------

1. Run `launch_storyteller_ai_ollama.bat`.
2. Wait for Ollama/model checks to finish.
3. Open <http://127.0.0.1:8000/>

Where To Click
--------------

- **Setup**: create game, upload docs, choose model provider
- **Story Console**: play turns, create characters, retrieve references
- **Character Tracker**: manage and export character sheets

If Something Fails
------------------

- Missing environment: run `install_dependencies.bat` again
- Page not loading: confirm backend is running and open <http://127.0.0.1:8000/>
- Ollama issues: make sure Ollama is installed and running, then re-run `launch_storyteller_ai_ollama.bat`

Need Full Instructions?
-----------------------

See `END_USER_TUTORIAL.md` for the complete walkthrough.
