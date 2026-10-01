"""Load-test an OpenAI-compatible LLM endpoint with a configurable worst-case prompt."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import statistics
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid


HERE = Path(__file__).resolve().parent
DEFAULT_WORKLOAD = HERE / "workload.json"
CSV_FIELDS = [
    "run_id", "request_id", "timestamp", "provider", "model", "base_url",
    "scenario", "concurrency", "target_input_tokens", "estimated_input_tokens",
    "actual_input_tokens", "actual_output_tokens", "output_chars", "ttft_seconds",
    "total_seconds", "output_tokens_per_second", "success", "error",
]


def load_workload(path: Path) -> dict[str, Any]:
    workload = json.loads(path.read_text(encoding="utf-8"))
    required = {"context_window_tokens", "max_output_tokens", "input_tokens", "system_prompt", "latest_turn"}
    missing = required - workload.keys()
    if missing:
        raise ValueError(f"workload missing fields: {', '.join(sorted(missing))}")
    return workload


def build_messages(workload: dict[str, Any], target_input_tokens: int) -> tuple[list[dict[str, str]], int]:
    if target_input_tokens < 1:
        raise ValueError("input token target must be positive")
    if target_input_tokens + workload["max_output_tokens"] > workload["context_window_tokens"]:
        raise ValueError("input target plus output reserve exceeds the configured context window")
    chars_per_token = int(workload.get("characters_per_estimated_token", 4))
    target_chars = target_input_tokens * chars_per_token
    system = workload["system_prompt"].strip()
    user_prefix = "[CAMPAIGN CONTEXT]\n"
    user_suffix = f"\n\n[LATEST PLAYER TURN]\n{workload['latest_turn']}"
    repeated_fact = (
        "Committed chronicle fact: the coterie negotiated with a rival faction; a witness remains "
        "unaccounted for; the current scene is public unless marked otherwise. Track cause and "
        "consequence consistently, do not reveal private notes, and use the selected ruleset.\n"
    )
    fixed_chars = len(system) + len(user_prefix) + len(user_suffix)
    fill_chars = max(0, target_chars - fixed_chars)
    context = (repeated_fact * math.ceil(fill_chars / len(repeated_fact)))[:fill_chars]
    user = f"{user_prefix}{context}{user_suffix}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    estimated_tokens = math.ceil(sum(len(message["content"]) for message in messages) / chars_per_token)
    return messages, estimated_tokens


def _endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    return base if base.endswith("/chat/completions") else f"{base}/chat/completions"


def _parse_sse_line(line: bytes) -> dict[str, Any] | None:
    decoded = line.decode("utf-8", errors="replace").strip()
    if not decoded.startswith("data:"):
        return None
    data = decoded[5:].strip()
    if not data or data == "[DONE]":
        return None
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def request_once(
    *, run_id: str, workload: dict[str, Any], provider: str, model: str,
    base_url: str, api_key: str, target_input_tokens: int, max_output_tokens: int,
    concurrency: int, timeout: float,
) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    first_token_at: float | None = None
    output_chars = 0
    actual_input_tokens = None
    actual_output_tokens = None
    error = ""
    success = False
    messages, estimated_input_tokens = build_messages(workload, target_input_tokens)
    body = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_output_tokens,
        "temperature": 0,
        "stream": True,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(_endpoint(base_url), data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            for line in response:
                chunk = _parse_sse_line(line)
                if not chunk:
                    continue
                usage = chunk.get("usage") or {}
                actual_input_tokens = usage.get("prompt_tokens", actual_input_tokens)
                actual_output_tokens = usage.get("completion_tokens", actual_output_tokens)
                choices = chunk.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content") or ""
                    if isinstance(content, str) and content:
                        if first_token_at is None:
                            first_token_at = time.perf_counter()
                        output_chars += len(content)
            success = True
    except HTTPError as exc:
        error = f"HTTP {exc.code}: {exc.read(1200).decode('utf-8', errors='replace')}"
    except (URLError, TimeoutError, OSError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    total_seconds = time.perf_counter() - started
    output_token_estimate = actual_output_tokens or math.ceil(output_chars / 4)
    return {
        "run_id": run_id, "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": provider, "model": model, "base_url": base_url,
        "scenario": workload.get("scenario", "custom"), "concurrency": concurrency,
        "target_input_tokens": target_input_tokens,
        "estimated_input_tokens": estimated_input_tokens,
        "actual_input_tokens": actual_input_tokens,
        "actual_output_tokens": actual_output_tokens,
        "output_chars": output_chars,
        "ttft_seconds": round(first_token_at - started, 6) if first_token_at is not None else None,
        "total_seconds": round(total_seconds, 6),
        "output_tokens_per_second": round(output_token_estimate / total_seconds, 3) if success and total_seconds else None,
        "success": success, "error": error,
    }


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1)]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [row for row in rows if row["success"]]
    ttft = [row["ttft_seconds"] for row in successful if row["ttft_seconds"] is not None]
    tps = [row["output_tokens_per_second"] for row in successful if row["output_tokens_per_second"] is not None]
    totals = [row["total_seconds"] for row in successful]
    return {
        "requests": len(rows), "successes": len(successful), "failures": len(rows) - len(successful),
        "ttft_p50_seconds": percentile(ttft, 0.50), "ttft_p95_seconds": percentile(ttft, 0.95),
        "tokens_per_second_mean": round(statistics.mean(tps), 3) if tps else None,
        "total_seconds_p95": percentile(totals, 0.95),
        "meets_t5_8_targets": bool(ttft and tps and percentile(ttft, 0.95) < 10 and statistics.mean(tps) >= 15),
    }


def write_results(output_dir: Path, run_id: str, rows: list[dict[str, Any]], summary: dict[str, Any]) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / f"{run_id}.jsonl"
    csv_path = output_dir / f"{run_id}.csv"
    summary_path = output_dir / f"{run_id}.summary.json"
    jsonl_path.write_text("".join(json.dumps(row, ensure_ascii=True) + "\n" for row in rows), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return jsonl_path, csv_path, summary_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="openai-compatible", help="Provider label stored in results")
    parser.add_argument("--base-url", default=os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1"))
    parser.add_argument("--model", default=os.getenv("LLM_MODEL", os.getenv("OLLAMA_MODEL", "")))
    parser.add_argument("--api-key-env", default="LLM_API_KEY", help="Environment variable holding the endpoint key")
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--input-tokens", type=int, default=None, help="Override worst-case estimated prompt size")
    parser.add_argument("--max-output-tokens", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--workload", type=Path, default=DEFAULT_WORKLOAD)
    parser.add_argument("--results-dir", type=Path, default=HERE / "results")
    args = parser.parse_args()
    if not args.model:
        parser.error("--model or LLM_MODEL is required")
    if args.iterations < 1 or args.concurrency < 1:
        parser.error("--iterations and --concurrency must be positive")
    workload = load_workload(args.workload)
    target = args.input_tokens or int(os.getenv("LLM_BENCH_INPUT_TOKENS", workload["input_tokens"]))
    max_output = args.max_output_tokens or int(workload["max_output_tokens"])
    if target + max_output > int(workload["context_window_tokens"]):
        parser.error("input target plus max output exceeds workload context window")
    api_key = os.getenv(args.api_key_env, "")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    rows = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(
            request_once, run_id=run_id, workload=workload, provider=args.provider,
            model=args.model, base_url=args.base_url, api_key=api_key,
            target_input_tokens=target, max_output_tokens=max_output,
            concurrency=args.concurrency, timeout=args.timeout,
        ) for _ in range(args.iterations)]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
    rows.sort(key=lambda row: row["timestamp"])
    summary = {
        "run_id": run_id, "provider": args.provider, "model": args.model,
        "base_url": args.base_url, "scenario": workload.get("scenario"),
        "context_window_tokens": workload["context_window_tokens"],
        "target_input_tokens": target, "max_output_tokens": max_output,
        "iterations": args.iterations, "concurrency": args.concurrency,
        **summarize(rows),
    }
    paths = write_results(args.results_dir, run_id, rows, summary)
    print(json.dumps({**summary, "results": [str(path) for path in paths]}, indent=2))
    return 0 if summary["successes"] == summary["requests"] else 1


if __name__ == "__main__":
    raise SystemExit(main())