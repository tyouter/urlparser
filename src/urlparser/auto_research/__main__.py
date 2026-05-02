"""
Auto Research CLI

Usage:
    python -m urlparser.auto_research run              # Full research cycle
    python -m urlparser.auto_research run --quick       # Quick cycle (50 URLs)
    python -m urlparser.auto_research dataset           # Build dataset only
    python -m urlparser.auto_research validate          # Validate dataset coverage
    python -m urlparser.auto_research benchmark         # Efficiency benchmark only
"""

import asyncio
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog='urlparser.auto_research',
        description='urlparser Auto Research Framework',
    )
    subparsers = parser.add_subparsers(dest='command')

    run_parser = subparsers.add_parser('run', help='Run full research cycle')
    run_parser.add_argument('--quick', action='store_true', help='Quick mode (50 URLs)')
    run_parser.add_argument('--sample', type=int, default=50, help='Sample size for quick mode')
    run_parser.add_argument('--concurrent', type=int, default=3, help='Max concurrent parses')
    run_parser.add_argument('--success-rate', type=float, default=0.99, help='Target success rate')
    run_parser.add_argument('--target-ppm', type=float, default=10.0, help='Target parses per minute')
    run_parser.add_argument('--output-dir', type=str, default=None)

    ds_parser = subparsers.add_parser('dataset', help='Build dataset only')
    ds_parser.add_argument('--output', type=str, default=None)

    val_parser = subparsers.add_parser('validate', help='Validate dataset')
    val_parser.add_argument('--dataset', type=str, default=None)

    bm_parser = subparsers.add_parser('benchmark', help='Efficiency benchmark only')
    bm_parser.add_argument('--concurrent', type=int, default=3)
    bm_parser.add_argument('--quick', action='store_true')
    bm_parser.add_argument('--sample', type=int, default=50)

    args = parser.parse_args()

    if args.command == 'run':
        asyncio.run(_run_research(args))
    elif args.command == 'dataset':
        _build_dataset(args)
    elif args.command == 'validate':
        _validate_dataset(args)
    elif args.command == 'benchmark':
        asyncio.run(_run_benchmark(args))
    else:
        parser.print_help()


async def _run_research(args):
    from .runner import ResearchRunner
    runner = ResearchRunner(
        target_success_rate=args.success_rate,
        target_ppm=args.target_ppm,
        max_concurrent=args.concurrent,
        quick_mode=args.quick,
        quick_sample=args.sample,
    )
    report = await runner.run(output_dir=args.output_dir)
    sys.exit(0 if report.overall_pass else 1)


def _build_dataset(args):
    from .dataset import DatasetBuilder
    from .runner import DATASET_PATH
    builder = DatasetBuilder()
    entries = builder.build()
    output = args.output or str(DATASET_PATH)
    data = builder.to_json(output)
    print(builder.summary())
    print(f"\nSaved {data['metadata']['total']} entries to {output}")


def _validate_dataset(args):
    from .dataset import DatasetBuilder
    from pathlib import Path
    import json

    dataset_path = args.dataset
    if not dataset_path:
        from .runner import DATASET_PATH
        dataset_path = str(DATASET_PATH)

    if not Path(dataset_path).exists():
        print(f"Dataset not found: {dataset_path}")
        print("Run 'python -m urlparser.auto_research dataset' first.")
        sys.exit(1)

    entries = DatasetBuilder.load_json(dataset_path)
    from collections import Counter
    counts = Counter(e.platform for e in entries)

    print(f"Dataset: {len(entries)} URLs, {len(counts)} platforms")
    for p, c in sorted(counts.items()):
        print(f"  {p}: {c}")

    min_size = 500
    if len(entries) >= min_size:
        print(f"\nPASS: {len(entries)} >= {min_size}")
    else:
        print(f"\nFAIL: {len(entries)} < {min_size}")


async def _run_benchmark(args):
    from .runner import ResearchRunner
    runner = ResearchRunner(
        max_concurrent=args.concurrent,
        quick_mode=args.quick,
        quick_sample=args.sample,
    )
    report = await runner.run()
    sys.exit(0 if report.benchmark_pass else 1)


if __name__ == '__main__':
    main()
