"""Offline collection/evaluation CLI; no settings, credentials, DB or provider calls."""
import argparse
from pathlib import Path

from src.benchmark.contracts import BenchmarkError, keys, require
from src.benchmark.dataset import build_dataset
from src.benchmark.evaluation import evaluate
from src.benchmark.io import dataset_from_job, load_json, load_review_packets, write_json_new
from src.benchmark.reviews import build_review_packet


class _Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise BenchmarkError('benchmark_arguments_invalid')


def main(argv=None):
    parser = _Parser(description='Benchmark umano offline: qualità e priorità separate')
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--input', type=Path, required=True)
    prepare.add_argument('--prediction-version', required=True)
    prepare.add_argument('--from-job', action='store_true')
    prepare.add_argument('--captured-at')
    packet = commands.add_parser('review-packet')
    packet.add_argument('--dataset', type=Path, required=True)
    packet.add_argument('--reviewer', required=True)
    comparison = commands.add_parser('evaluate')
    comparison.add_argument('--dataset', type=Path, required=True)
    comparison.add_argument('--reviews', type=Path, nargs='+', required=True)
    for command in (prepare, packet, comparison):
        command.add_argument('--out', type=Path, required=True)
    try:
        args = parser.parse_args(argv)
        if args.command == 'prepare':
            require(bool(args.captured_at) == args.from_job)
            raw = load_json(args.input)
            if args.from_job:
                value = dataset_from_job(raw, prediction_version=args.prediction_version, captured_at=args.captured_at)
            else:
                keys(raw, ('schema_version', 'samples'))
                require(type(raw['schema_version']) is int and raw['schema_version'] == 1)
                value = build_dataset(raw['samples'], args.prediction_version)
        elif args.command == 'review-packet':
            value = build_review_packet(load_json(args.dataset), args.reviewer)
        else:
            require(len(args.reviews) <= 500)
            value = evaluate(load_json(args.dataset), load_review_packets(args.reviews))
        write_json_new(args.out, value)
        print('benchmark_ok')
        return 0
    except BenchmarkError as error:
        print(error.code)
        return 2
    except (OSError, ValueError, TypeError, RecursionError):
        print('benchmark_invalid')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
