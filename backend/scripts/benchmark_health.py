"""Measure local non-ML API latency without requiring Firebase credentials."""

import statistics
import time

from fastapi.testclient import TestClient

from app.main import app


def main() -> None:
    samples: list[float] = []
    with TestClient(app) as client:
        for _ in range(100):
            started = time.perf_counter()
            response = client.get("/health")
            elapsed_ms = (time.perf_counter() - started) * 1000
            if response.status_code != 200:
                raise RuntimeError(f"Health request failed: {response.status_code}")
            samples.append(elapsed_ms)

    ordered = sorted(samples)
    p95 = ordered[94]
    print(
        f"samples={len(samples)} median_ms={statistics.median(samples):.2f} "
        f"p95_ms={p95:.2f} max_ms={max(samples):.2f}"
    )


if __name__ == "__main__":
    main()
