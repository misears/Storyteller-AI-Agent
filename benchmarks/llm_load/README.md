# LLM Worst-Case Load Bench

This folder benchmarks any model exposed through an **OpenAI-compatible streaming chat
completions endpoint**. That includes Ollama's `/v1` endpoint and compatible local servers,
hosted gateways, or proxies. It uses only Python's standard library and never writes prompts,
responses, or API keys into result files.

## Load controls

`workload.json` defines the expected maximum context (`context_window_tokens`, default 16,384),
output reserve (1,500 tokens), and default worst-case input target (12,000 estimated tokens).
The input target is intentionally a CLI/environment variable too, so you can benchmark the
maximum load your chosen model/profile will permit:

- `--input-tokens` or `LLM_BENCH_INPUT_TOKENS`: estimated prompt size; default 12,000.
- `--max-output-tokens`: response reserve; default 1,500.
- `--iterations`: request count; default 5.
- `--concurrency`: simultaneous requests; default 1. Raise this to emulate multiple active users.
- `--timeout`: per-request timeout in seconds; default 300.

The runner rejects input plus output limits above the configured context window. Since exact
tokenization varies by tokenizer, it creates a prompt using an approximate four characters per
token and records both that estimate and provider-reported usage when available. Use provider
usage as the authoritative token count. Prompt and response content are not persisted.

## Examples

Ollama local model:

```powershell
$env:OLLAMA_MODEL = "qwen2.5:7b"
python benchmarks/llm_load/benchmark.py --provider ollama --base-url http://127.0.0.1:11434/v1 --model $env:OLLAMA_MODEL --iterations 10 --concurrency 1
```

Other OpenAI-compatible service (keep keys in environment variables):

```powershell
$env:LLM_API_KEY = "..."
python benchmarks/llm_load/benchmark.py --provider gateway-name --base-url https://gateway.example/v1 --model model-name --input-tokens 12000 --max-output-tokens 1500 --iterations 20 --concurrency 3
```

## Recorded results

Each run creates three files under `results/` (git-ignored):

- `<run-id>.jsonl`: one privacy-conscious observation per request.
- `<run-id>.csv`: same request rows for spreadsheets.
- `<run-id>.summary.json`: configuration, success counts, p50/p95 time-to-first-token, mean output
  tokens/second, p95 total latency, and whether the T5.8 latency/throughput targets were met.

The T5.8 targets are p95 time to first token under 10 seconds and mean generation speed at least
15 tokens/second. A benchmark run alone does not assess tool-call quality or fabricated-roll rate;
those need a fixed scripted game-turn suite before selecting the default model.