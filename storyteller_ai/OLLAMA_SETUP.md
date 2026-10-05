# Ollama Setup Guide for Storyteller AI Agent

This guide will help you set up a local Ollama 8B model for offline development.

## Prerequisites

- Windows 10/11
- At least 8GB RAM (16GB+ recommended for smooth performance)
- ~10GB disk space for the 8B model
- GPU recommended but CPU-only works

## Step 1: Install Ollama

### Option A: Download Installer (Recommended)
1. Visit [ollama.ai](https://ollama.ai)
2. Click "Download" and select Windows
3. Download and run the installer
4. Follow the installation wizard
5. Ollama will start automatically on Windows startup

### Option B: Using Windows Package Manager (Scoop)
```powershell
scoop install ollama
```

### Verify Installation
```powershell
ollama --version
```

## Step 2: Start the Ollama Server

The Ollama server should start automatically after installation. To verify it's running:

```powershell
# Test if Ollama is running on default port 11434
curl http://127.0.0.1:11434
```

If it's not running, start it manually:
```powershell
ollama serve
```

## Step 3: Download an 8B Model

Choose one of the following lightweight 8B models:

### Option 1: Llama 2 8B (Recommended for General Use)
```powershell
ollama pull llama2:7b
```

### Option 2: Mistral 7B (Better for faster inference)
```powershell
ollama pull mistral:7b
```

### Option 3: Neural Chat 7B
```powershell
ollama pull neural-chat:7b
```

**Note:** The numbers after the colon indicate model size. These will download ~5-7GB.

### Monitor Download Progress
```powershell
# This will show the download progress
ollama pull llama2:7b
```

## Step 4: Test the Model Locally

Once downloaded, test it:

```powershell
ollama run llama2:7b
```

Then type a test prompt like:
```
What is a good opening for a fantasy story?
```

Press Ctrl+D to exit.

## Step 5: Configure Your Project

### Update .env File

Add or update these variables in your `.env` file:

```env
# Use Ollama as the LLM provider
LLM_PROVIDER=ollama

# Ollama server URL (default)
OLLAMA_URL=http://127.0.0.1:11434

# Model name (must match what you pulled)
OLLAMA_MODEL=llama2:7b

# Local inference budgets (seconds); see "Timeouts and cancellation" below
OLLAMA_CONNECT_TIMEOUT=10
OLLAMA_READ_TIMEOUT=600
OLLAMA_TOTAL_TIMEOUT=900
OLLAMA_CONNECT_RETRIES=1

# Optional: disable OpenAI/Anthropic keys when using Ollama
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

### Create .env if it doesn't exist:

Create a file named `.env` in the project root:
```
cd c:\Users\misea\OneDrive\Documents\AI Project Folders\Storyteller AI Agent\storyteller_ai
# Create .env with the above content
```

## Step 6: Test Integration

### Run Backend with Ollama
```powershell
# In PowerShell at your project root
$env:LLM_PROVIDER = "ollama"
$env:OLLAMA_MODEL = "llama2:7b"
python -m uvicorn storyteller_ai.backend.main:app --reload
```

### Test the API
```powershell
# In another terminal
$uri = "http://127.0.0.1:8000/api/v1/generate"
$body = @{
    system_prompt = "You are a fantasy storyteller."
    user_message = "Start an adventure in a forest."
} | ConvertTo-Json

Invoke-WebRequest -Uri $uri -Method Post -Body $body -ContentType "application/json"
```

## Troubleshooting

### Timeouts and cancellation

Ollama uses a 10-second connection timeout, a 600-second response-idle timeout,
and a 900-second total generation budget by default. Only connection failures
retry, at most once. A read timeout is not retried because Ollama may still be
generating. When a budget expires, the app reports that the turn was not
committed. The play screen shows elapsed time and offers a cancel button during
generation; cancellation is disabled once the response is being saved. Failed
actions remain in the composer and reuse their request ID on retry, so a lost
success response cannot create a duplicate turn.

Set `OLLAMA_CONNECT_TIMEOUT`, `OLLAMA_READ_TIMEOUT`, `OLLAMA_TOTAL_TIMEOUT`, or
`OLLAMA_CONNECT_RETRIES` in `.env` to change defaults. Timeouts are bounded to
1-120 seconds for connection, 1-1800 seconds for idle response, and 1-3600
seconds total; connect retries are limited to 0-3. These variables are read on
startup. The local `PUT /settings/llm` endpoint can adjust the same values for
the current process. For a slow CPU model, increase the total budget while
keeping it above the read timeout.

Native `/api/chat` tool requests also expose `OLLAMA_CONTEXT_WINDOW` (default
8192 tokens), `OLLAMA_MAX_OUTPUT_TOKENS` (default 800), and `OLLAMA_THINK`.
Context is bounded to 1,024-131,072 tokens; output is bounded to 64-8,192
tokens. `OLLAMA_THINK` accepts `false`, `true`, `low`, `medium`, or `high`;
available thinking modes depend on the model. Qwen3 supports `false` to suppress
reasoning output, which is the default. Keep the context/output budget within
the model's available memory, particularly on an 8 GB GPU.

### Game tools

Campaign turns send registered tool schemas to Ollama and accept at most 6 tool
rounds and 12 calls per turn. The server validates each call's JSON schema and
authority before execution. Dice are evaluated with the server's branch RNG;
state patches and tool audit events remain staged until final narration is ready,
then commit atomically with the player action, rolls, and GM response. A timeout,
cancellation, invalid loop limit, or failed generation therefore cannot leave a
partial tool-driven turn. Saved branches replay committed state-patch events.

Models without native tool support use only a final fenced `storyteller-actions`
or legacy `json` action block. The same server validation applies, and the model
receives tool results before it narrates. Plain text is never mined for actions.

### Ollama server not responding
```powershell
# Check if Ollama is running
tasklist | findstr ollama

# Start it if not running
ollama serve

# Check the URL (default is http://127.0.0.1:11434)
curl http://127.0.0.1:11434
```

### Model not found
```powershell
# List available models
ollama list

# Pull the model again
ollama pull llama2:7b
```

### Slow inference
- This is normal for CPU-only inference and larger models.
- The play screen shows generation time. Cancel if needed; a cancelled generation
    does not create a turn event.
- Increase the bounded total timeout for slow CPU models. Keep in mind that a
    read timeout is an idle interval, while the total timeout covers the request.
- Consider a smaller model if responses regularly exceed your configured budget.

### High memory usage
- 8B models need ~16GB RAM on CPU
- Reduce context length in requests if running out of memory
- Consider a smaller model like llama2:3b

## Performance Notes

### CPU-only Performance (Approximate)
- **First request:** 30-90 seconds (model loading)
- **Subsequent requests:** 5-20 seconds
- **GPU (if available):** 2-10 seconds

### Memory Usage
- **llama2:7b:** ~8-10GB RAM
- **mistral:7b:** ~7-9GB RAM
- **llama2:3b:** ~4-5GB RAM (if you need faster, smaller model)

## Switching Models

To switch to a different model:

1. Pull the new model:
   ```powershell
   ollama pull mistral:7b
   ```

2. Update your `.env` file:
   ```env
   OLLAMA_MODEL=mistral:7b
   ```

3. Restart your application

## Running Offline

Once a model is downloaded:
1. Ollama server must be running: `ollama serve`
2. Your app can work completely offline (no internet needed)
3. Both Ollama and your backend must be running to use the service

## Advanced: Custom Model Parameters

To use custom inference parameters in your app, you can modify `llm_client.py`:

```python
# In OllamaProvider.generate()
payload = {
    "model": _get_ollama_model(),
    "messages": [...],
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 40,
    "num_predict": 800,  # max tokens
}
```

## Next Steps

1. ✅ Install Ollama
2. ✅ Download a model (llama2:7b recommended)
3. ✅ Update `.env` with Ollama settings
4. ✅ Test the integration
5. ✅ Run your backend with Ollama

Your Storyteller AI Agent will now run completely offline!
