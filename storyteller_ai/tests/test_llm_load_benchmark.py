import csv
import json
import pytest

from benchmarks.llm_load.benchmark import build_messages, summarize, write_results


def test_worst_case_prompt_tracks_configured_input_budget():
    workload = {
        "context_window_tokens": 16000,
        "max_output_tokens": 1500,
        "characters_per_estimated_token": 4,
        "system_prompt": "system",
        "latest_turn": "latest action",
    }

    messages, estimate = build_messages(workload, 12000)

    assert len(messages) == 2
    assert estimate <= 12000
    assert estimate >= 11999


def test_prompt_rejects_load_above_context_window():
    workload = {
        "context_window_tokens": 16000, "max_output_tokens": 2000,
        "system_prompt": "system", "latest_turn": "action",
    }

    with pytest.raises(ValueError, match="context window"):
        build_messages(workload, 15000)


def test_summary_reports_percentiles_and_thresholds():
    rows = [
        {"success": True, "ttft_seconds": 1.0, "output_tokens_per_second": 20.0, "total_seconds": 3.0},
        {"success": True, "ttft_seconds": 2.0, "output_tokens_per_second": 16.0, "total_seconds": 4.0},
    ]

    summary = summarize(rows)

    assert summary["ttft_p95_seconds"] == 2.0
    assert summary["tokens_per_second_mean"] == 18.0
    assert summary["meets_t5_8_targets"] is True


def test_results_are_recorded_in_jsonl_csv_and_summary(tmp_path):
    row = {
        "run_id": "run-1", "request_id": "request-1", "timestamp": "now",
        "provider": "local", "model": "test", "base_url": "http://localhost/v1",
        "scenario": "worst-case", "concurrency": 1, "target_input_tokens": 100,
        "estimated_input_tokens": 100, "actual_input_tokens": None,
        "actual_output_tokens": None, "output_chars": 80, "ttft_seconds": 1.0,
        "total_seconds": 2.0, "output_tokens_per_second": 10.0,
        "success": True, "error": "",
    }
    summary = summarize([row])

    jsonl, csv_path, summary_path = write_results(tmp_path, "run-1", [row], summary)

    assert json.loads(jsonl.read_text())["model"] == "test"
    with csv_path.open(newline="", encoding="utf-8") as stream:
        assert next(csv.DictReader(stream))["request_id"] == "request-1"
    assert json.loads(summary_path.read_text())["requests"] == 1