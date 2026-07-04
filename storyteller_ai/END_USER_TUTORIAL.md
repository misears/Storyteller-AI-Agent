Storyteller AI End-User Tutorial
================================

This guide walks you through installing Storyteller AI, creating a game session, and running your story turn by turn.

Who This Is For
---------------

- Players and Storytellers who want to use the app through its browser UI
- First-time users on Windows

What You Need
-------------

- Windows PC
- Python installed and available in PATH
- Internet connection for cloud models (OpenAI/Anthropic)
- Optional: Ollama for offline/local model play

Step 1: Install Dependencies (First Run Only)
---------------------------------------------

1. In the project folder, double-click `install_dependencies.bat`.
2. Wait for installation to finish.
3. The installer creates a desktop shortcut named **Storyteller AI**.

What this does:

- Creates a local virtual environment in `venv`
- Installs required Python packages
- Creates a launcher shortcut on your Desktop

Step 2: Launch the App
----------------------

Choose one launch method:

- Standard launch (default provider behavior):
  - Double-click the desktop shortcut, or run `launch_storyteller_ai.bat`
- Offline launch with Ollama + local Llama2:
  - Run `launch_storyteller_ai_ollama.bat`

When startup is successful, open:

- <http://127.0.0.1:8000/>

Step 3: Home Page Overview
--------------------------

On the Home page you will see three options:

- **Setup**: create a game, upload documents, choose LLM provider, set layout preferences
- **Story Console**: play turns, create characters, retrieve reference text
- **Character Tracker**: manage full character sheets and export

Recommended order for a new game:

1. Setup
2. Story Console
3. Character Tracker (optional during play)

Step 4: Set Up a Game Session
-----------------------------

Open **Setup** and complete the sections in order.

1) Create game session

- Select **Mode**: `group`, `solo`, or `assistant`
- Enter **Game title**
- Choose **Setting**
- Pick **Campaign genres** (optional but recommended)
- Select active documents for this session from **Choose loaded documents**
- Click **Create Game**

Important:

- Copy/save the **Session ID** shown in the result box. You will need it in Story Console.

1) Upload story documents (PDF)

- In Setup section 2, choose one or more PDFs
- Optionally tag them with genres
- Click **Upload PDFs**

Tips:

- OCR status appears above upload controls.
- If OCR shows unavailable, scanned PDFs may not ingest as well until Tesseract OCR is installed.
- You can retag or delete documents in the **Loaded documents** area.

1) Configure LLM options

- Choose **Provider**: `openai`, `anthropic`, `ollama`, or `mock`
- Enter model name
- If using Ollama, set URL and optional model override
- Click **Save LLM Settings**

1) Customize page layout (optional)

- Choose theme, spacing density, and font scale
- Click **Apply Layout** to save preferences
- Use **Reset Layout** to return to defaults

Step 5: Play in Story Console
-----------------------------

Open **Story Console**.

Continue the story

1. Paste your Session ID into **Session ID**
2. Enter a prompt in **What happens next?**
3. Click **Continue Story**
4. Read the AI response in the result area

Character creation

1. Enter Session ID
2. Fill Name, Clan/Type, and Notes
3. Click **Create Character**

Reference retrieval

1. Enter a question in **Query**
2. Click **Retrieve**
3. Review extracted reference text from uploaded docs

Step 6: Use Character Tracker (Optional but Recommended)
--------------------------------------------------------

Open **Character Tracker** for richer sheet management.

You can:

- Select an existing session or create standalone sheets
- Choose genre and audience (player/storyteller)
- Fill dynamic template fields
- Save sheets internally
- Export to PDF or Word (`.docx`)

Stopping the App
----------------

- Close the terminal window(s) opened by the launcher script.
- To start again later, run the same launcher you used before.

Troubleshooting
---------------

If `venv` is missing:

- Re-run `install_dependencies.bat`

If page does not load:

- Confirm terminal shows Uvicorn running on `127.0.0.1:8000`
- Open <http://127.0.0.1:8000/> manually

If using Ollama and model responses fail:

- Confirm Ollama is installed and running
- Confirm model exists locally (for example `llama2:7b`)
- Re-run `launch_storyteller_ai_ollama.bat`

If PDF quality is poor on scanned files:

- Install Tesseract OCR and ensure `tesseract.exe` is available
- Restart the launcher after installing OCR

Related Docs
------------

- `README.md`
- `QUICK_START_CARD.md`
- `OLLAMA_QUICKSTART.md`
- `OLLAMA_SETUP.md`
