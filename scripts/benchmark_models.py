"""Benchmark configured LLM providers for turn latency and response throughput."""

import argparse
import asyncio
import os
from time import perf_counter

from storyteller_ai.backend.services.llm_client import LLMClient


async def benchmark(rounds: int) -> dict[str, float]:
    client = LLMClient()
    start = perf_counter()
    for index in range(rounds):
        await client.generate("You are a benchmark storyteller.", f"Benchmark turn {index}")
    elapsed = perf_counter() - start
    return {"rounds": rounds, "seconds": elapsed, "seconds_per_round": elapsed / rounds}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--provider", default=None)
    args = parser.parse_args()
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
    if args.rounds < 1:
        parser.error("--rounds must be positive")
    print(asyncio.run(benchmark(args.rounds)))


if __name__ == "__main__":
    main()