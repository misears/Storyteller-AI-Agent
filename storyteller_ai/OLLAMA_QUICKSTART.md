# Ollama Quick Start for Storyteller AI Agent

## TL;DR - Get Running in 5 Minutes

### 1. Install Ollama
**Download:** https://ollama.ai (Windows version)

Run the installer and let it complete. Ollama will auto-start.

### 2. Download a Model (in PowerShell)
```powershell
ollama pull llama2:7b
```
Wait 5-10 minutes for download (~7GB).

### 3. Create Your .env File
Copy `.env.example` to `.env` and update:

```env
LLM_PROVIDER=ollama
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama2:7b
```

### 4. Run Your App
```powershell
cd "c:\Users\misea\OneDrive\Documents\AI Project Folders\Storyteller AI Agent\storyteller_ai"
python -m uvicorn storyteller_ai.backend.main:app --reload
```

### 5. Test It
Open browser: `http://127.0.0.1:8000`

---

## Automated Setup (Easier)

Run this PowerShell command in your project directory:

```powershell
.\setup_ollama.ps1 -Action install -Model llama2:7b
```

This will:
- ✓ Check if Ollama is installed
- ✓ Start the Ollama server
- ✓ Download the model
- ✓ Verify everything works

---

## Available Models (Choose 1)

| Model | Size | Speed | Quality | Command |
|-------|------|-------|---------|---------|
| Llama 2 7B | 7GB | Slow | Excellent | `ollama pull llama2:7b` |
| Mistral 7B | 7GB | Fast | Good | `ollama pull mistral:7b` |
| Neural Chat | 7GB | Medium | Very Good | `ollama pull neural-chat:7b` |

**Recommendation:** Start with `llama2:7b` for best story quality

---

## Verify Everything Works

```powershell
# Check Ollama is running
curl http://127.0.0.1:11434

# List your models
ollama list

# Test with the model directly
ollama run llama2:7b
# Type: "Write a 2-sentence fantasy story opening"
# Press Ctrl+D to exit
```

---

## Environment Variables Explained

```env
LLM_PROVIDER=ollama
```
Tells the app to use your local Ollama model instead of cloud APIs.

```env
OLLAMA_URL=http://127.0.0.1:11434
```
Where your Ollama server is running (default local port).

```env
OLLAMA_MODEL=llama2:7b
```
Must match a model you've downloaded (see `ollama list`)

---

## Troubleshooting

**Q: "Connection refused" error?**
- Ollama server isn't running
- Run: `ollama serve` in a PowerShell window
- Keep it running while you use your app

**Q: "Model not found" error?**
- Download it: `ollama pull llama2:7b`
- Check what you have: `ollama list`

**Q: Very slow responses?**
- This is normal! CPU-only inference is slow
- First request: 30-90 seconds (model loads)
- Later requests: 5-20 seconds
- If you have a GPU, Ollama will auto-detect it

**Q: High memory usage?**
- 8B models use ~10GB RAM on CPU
- This is normal
- Consider `mistral:7b` for slightly better performance

**Q: How do I run completely offline?**
- ✓ Install Ollama and download model once (needs internet)
- ✓ After that, both the app and Ollama can run 100% offline
- ✓ Just need: `ollama serve` running + your app running

---

## Next Steps After Setup

1. **Update .env** (copy from .env.example)
2. **Start Ollama** (`ollama serve`)
3. **Run your backend** (use the task or `python -m uvicorn...`)
4. **Test the UI** (http://127.0.0.1:8000)
5. **Create a story!**

---

## File Reference

- **OLLAMA_SETUP.md** - Detailed setup guide
- **setup_ollama.ps1** - Automated setup script
- **.env.example** - Configuration template
- **backend/services/llm_client.py** - Ollama integration code (already done!)

---

## Questions?

Check `OLLAMA_SETUP.md` for the detailed guide with all options and advanced configuration.

**Your app is now ready to work completely offline! 🎉**
