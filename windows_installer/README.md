# Storyteller AI Windows Installer

## For the person installing Storyteller AI

Use `StorytellerAI-Setup.exe` when supplied. Double-click it, review the computer
check, choose a model, and continue. Leave the setup window open until it finishes.
If supplied a ZIP instead, extract the entire ZIP first, open the extracted folder,
and double-click `Install.cmd`. Type YES when asked to approve installation.
The ZIP installs the balanced 4B model by default.

Setup handles Python, a private virtual environment, the application's Python
packages, Ollama, and the selected model. You do not need to activate Python,
use a terminal, or create an AI account. Internet access is needed to download
Ollama if missing and the first AI model. Allow at least 20 GB free disk space
on the installation and Windows profile drives. Windows 10/11 x64 is required.
Organization-managed computers may restrict downloaded programs or scripts;
contact your administrator instead of disabling your organization's protections.

An existing compatible Python 3.12 x64 installation is reused without changing
its packages. Otherwise setup installs a private runtime. The application always
uses its own virtual environment, not your global Python packages.

Model choices:

- Balanced: Qwen3 4B, about 2.5 GB; the default for most computers.
- Higher quality: Qwen3 8B, about 5.2 GB; a good candidate for a Ryzen 9,
  RTX 4070 Laptop GPU, and 64 GB RAM. Long conversations can still slow it down.
- Low memory: Qwen3 1.7B, about 1.4 GB; simpler output for low-memory computers.

After setup, open the Storyteller AI desktop shortcut. Your browser opens the
application. Keep its console window open while playing; close it to stop.
The local AI service may continue running in the background.

If setup fails, its message identifies the problem and the log location.
Run Repair Storyteller AI from the Start menu to retry. If installation failed
before shortcuts were created, rerun the original installer.
Repair requires confirmation and preserves campaign data, but resets the LLM
configuration to local Ollama and the model selected during installation.

Campaign files and logs live in `%LOCALAPPDATA%\StorytellerAI`, separately from
the program. Upgrades and uninstall do not remove campaign data, your existing
Ollama installation, downloaded models, or the private Python runtime.
Remove those separately only when you no longer need them.
The ZIP installation does not register a Windows uninstaller; remove its program
folder and shortcuts manually after closing the application. Keep campaign data
unless you deliberately want to delete it.

Optional dependency: Tesseract OCR is needed only for scanned/image-only PDFs.
The installer offers optional OCR support; select the scanned-PDF OCR task to install
the exact `UB-Mannheim.TesseractOCR` WinGet package. WinGet verifies the package hash,
and Windows may request administrator approval. The ZIP installer asks before opting
in. OCR errors include a page number and repair guidance; text PDFs work without OCR.
Choose **Repair OCR for Storyteller AI** from the Start menu to check or retry later.
If WinGet or administrator approval is unavailable, use the linked official Windows
instructions and include English (`eng`) language data. No manual PATH edits are needed.

Windows may warn about an unsigned Storyteller installer. Release signing is
the distributor's responsibility; verify the source before running it.

## For the person building the installer

Packaging code and generated artifacts are isolated in this folder. Running the
build does not modify source, development environment, or campaign data. No
existing `.env`, API keys, virtual environments, document uploads, or backend
data are included in the distributable.

1. From the workspace root run:

   ```powershell
   .\windows_installer\Build.ps1
   ```

2. Distribute `windows_installer/output/StorytellerAI-Setup.exe`.
   The build also creates `StorytellerAI-Install.zip` for script-based setup.

Build reuses Inno Setup 6 when available, or downloads a signed portable compiler
inside the ignored output folder. It does not install the compiler system-wide.
See the [Inno Setup website](https://jrsoftware.org/isinfo.php) for licensing.

To create only the ZIP without Inno Setup:

```powershell
.\windows_installer\Build.ps1 -PrepareOnly
```

To use a compiler installed elsewhere:

```powershell
.\windows_installer\Build.ps1 -CompilerPath 'C:\path\to\ISCC.exe'
```

Build needs Python with pip and internet access. It downloads Windows x64
CPython 3.12 wheels for the exact application's requirements and the signed
official Python 3.12.10 installer. Dependency-resolution failures stop the build;
they are not ignored or silently replaced with unpinned versions. The Python
version is configurable within 3.12; use an official release with a Windows
installer, and review runtime security support before distributing.

Build checks the Python installer's Authenticode signature and generates SHA-256
checksums for the payload. Install verifies that payload before use and checks
the downloaded Ollama installer's Authenticode signature. These checks detect
damaged files; they do not replace signing the final installer or establishing
trust in its distributor. Review Ollama/model/Python/package licenses before
redistribution. Ollama is downloaded at install time rather than redistributed.

Validation without installing software:

```powershell
.\windows_installer\Test-Installer.ps1
.\windows_installer\Install.ps1 -CheckOnly
```

Before release, test on a clean Windows x64 VM: missing Python/Ollama, existing
Python/Ollama, both model choices, interrupted downloads and retry, paths with
spaces, launch/browser health, repair, upgrade, uninstall, and preserved data.
GPU performance and model download/generation require a real target-machine
test. Silent EXE setup still requires network for missing AI components.

Ollama defaults to 10 seconds to connect, 600 seconds between response data, and
900 seconds for the full generation, with one retry for connection failures only.
Native tool calls use an 8K context, up to 800 output tokens, and Qwen thinking
disabled by default; these can be configured through the local LLM settings API or `.env`.
The play screen shows elapsed time, allows cancellation during generation, and
preserves the action for an idempotent retry. Campaign turns use a validated,
bounded tool loop; dice/state/tool audit and final narration commit atomically.
Configure timeout, context, output, and thinking values through the local LLM
settings endpoint or `.env`; see `OLLAMA_SETUP.md` for bounds. Live Qwen and
owner-installed-app validation remains tracked by T11.8.
This installer does not claim local/cloud feature parity or instant CPU replies.
