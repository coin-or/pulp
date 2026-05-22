"""Benchmark write_mps on a large bin-packing MIP."""

import argparse
import cProfile
import pstats
import tempfile
import time
from pathlib import Path

from pulp.tests.bin_packing_problem import create_bin_packing_problem


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--bins", type=int, default=100)
    p.add_argument("--items", type=int, default=99)
    p.add_argument("--repeat", type=int, default=3)
    p.add_argument("--profile", action="store_true")
    p.add_argument("--rename", action="store_true")
    args = p.parse_args()

    prob = create_bin_packing_problem(args.bins, args.items)

    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "bench.mps")
        if args.profile:
            cProfile.runctx(
                "prob.writeMPS(path, rename=args.rename)",
                globals(),
                locals(),
                "benchmark_mps_write.prof",
            )
            stats = pstats.Stats("benchmark_mps_write.prof").sort_stats("cumtime")
            stats.print_stats(30)
            return

        durations = []
        for _ in range(args.repeat):
            t0 = time.perf_counter()
            prob.writeMPS(path, rename=args.rename)
            durations.append(time.perf_counter() - t0)
        size = Path(path).stat().st_size
        print(f"size={size:,}B repeats={args.repeat}")
        print(
            f"  min={min(durations):.3f}s  "
            f"median={sorted(durations)[len(durations) // 2]:.3f}s"
        )


if __name__ == "__main__":
    main()
