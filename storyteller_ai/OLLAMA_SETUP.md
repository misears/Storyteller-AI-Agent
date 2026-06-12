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
- This is normal for CPU-only inference on 8B models
- First request takes ~30-60 seconds to warm up
- Subsequent requests in same session are faster
- Consider GPU acceleration if available

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
