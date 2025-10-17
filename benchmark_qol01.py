#!/usr/bin/env python3
"""Benchmark script for QOL-01 MD5 tree caching optimization.

Tests the performance improvement of using MD5-validated cache:
1. First run: Full processing (no cache)
2. Second run: Uses MD5 cache (if tree unchanged)
3. Third run: Uses cache again

Shows timing and speedup metrics.
"""

import os
import sys
import time
import subprocess
import json
from pathlib import Path
import shutil


class Colors:
    """ANSI color codes"""
    BLUE = "\033[38;5;33m"
    GREEN = "\033[38;5;46m"
    YELLOW = "\033[38;5;226m"
    RED = "\033[38;5;196m"
    CYAN = "\033[38;5;51m"
    GRAY = "\033[38;5;244m"
    BOLD = "\033[1m"
    END = "\033[0m"


def get_cache_dir():
    """Get blade cache directory"""
    cache_home = os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache'))
    return os.path.join(cache_home, 'snek', 'blade')


def clear_cache():
    """Clear all blade cache to force full reprocessing"""
    cache_dir = get_cache_dir()
    if Path(cache_dir).exists():
        shutil.rmtree(cache_dir)
        print(f"{Colors.YELLOW}Cleared cache: {cache_dir}{Colors.END}")


def get_data_dir():
    """Get blade data directory"""
    data_home = os.environ.get('XDG_DB_HOME',
                               os.environ.get('XDG_DATA_HOME',
                                            os.path.expanduser('~/.local/share')))
    return os.path.join(data_home, 'snek', 'blade')


def get_processing_time():
    """Extract processing time from tree metadata"""
    cache_dir = get_cache_dir()
    metadata_file = os.path.join(cache_dir, 'tree_metadata.json')

    if not Path(metadata_file).exists():
        return None

    try:
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
            return metadata.get('processing_time')
    except (json.JSONDecodeError, IOError):
        return None


def run_blade_data():
    """Run blade data command and capture output"""
    result = subprocess.run(
        ['python3', 'blade.py', 'data'],
        capture_output=True,
        text=True,
        timeout=300
    )
    return result.stdout, result.stderr, result.returncode


def parse_output_time(output):
    """Extract time from blade output (looks for 'Processed in X.XXs')"""
    for line in output.split('\n'):
        if 'Processed in' in line and 's' in line:
            # Extract number from "Processed in 12.34s"
            try:
                time_str = line.split('Processed in')[1].split('s')[0].strip()
                return float(time_str)
            except (ValueError, IndexError):
                pass
    return None


def main():
    """Run benchmark suite"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}╔══════════════════════════════════════════════════╗{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}║  QOL-01: MD5 Tree Caching Optimization Benchmark ║{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚══════════════════════════════════════════════════╝{Colors.END}\n")

    # Check we're in the right directory
    if not Path('blade.py').exists():
        print(f"{Colors.RED}Error: blade.py not found in current directory{Colors.END}")
        sys.exit(1)

    results = []

    # Run 1: Clear cache and do full processing
    print(f"{Colors.BOLD}Run 1: Full Processing (Cache Cleared){Colors.END}")
    print(f"{Colors.GRAY}{'─'*50}{Colors.END}")
    clear_cache()
    start_time = time.time()
    stdout, stderr, returncode = run_blade_data()
    elapsed_time = time.time() - start_time

    if returncode != 0:
        print(f"{Colors.RED}Failed to run blade data{Colors.END}")
        print(f"stderr: {stderr}")
        sys.exit(1)

    # Show last few lines of output
    output_lines = stdout.strip().split('\n')
    for line in output_lines[-5:]:
        print(line)

    parsed_time_1 = parse_output_time(stdout)
    print(f"\n{Colors.GREEN}✅ Run 1 Complete{Colors.END}")
    print(f"   Elapsed: {elapsed_time:.2f}s")
    if parsed_time_1:
        print(f"   Processing: {parsed_time_1:.2f}s")
    results.append(('Full Processing', elapsed_time, parsed_time_1))

    # Run 2: Use cache (tree unchanged)
    print(f"\n{Colors.BOLD}Run 2: Using MD5 Cache (Tree Unchanged){Colors.END}")
    print(f"{Colors.GRAY}{'─'*50}{Colors.END}")
    start_time = time.time()
    stdout, stderr, returncode = run_blade_data()
    elapsed_time = time.time() - start_time

    if returncode != 0:
        print(f"{Colors.RED}Failed to run blade data{Colors.END}")
        print(f"stderr: {stderr}")
        sys.exit(1)

    # Show last few lines of output
    output_lines = stdout.strip().split('\n')
    for line in output_lines[-5:]:
        print(line)

    parsed_time_2 = parse_output_time(stdout)
    print(f"\n{Colors.GREEN}✅ Run 2 Complete{Colors.END}")
    print(f"   Elapsed: {elapsed_time:.2f}s")
    if parsed_time_2:
        print(f"   Processing: {parsed_time_2:.2f}s")
    results.append(('Using Cache (1st)', elapsed_time, parsed_time_2))

    # Run 3: Use cache again
    print(f"\n{Colors.BOLD}Run 3: Using MD5 Cache Again{Colors.END}")
    print(f"{Colors.GRAY}{'─'*50}{Colors.END}")
    start_time = time.time()
    stdout, stderr, returncode = run_blade_data()
    elapsed_time = time.time() - start_time

    if returncode != 0:
        print(f"{Colors.RED}Failed to run blade data{Colors.END}")
        print(f"stderr: {stderr}")
        sys.exit(1)

    # Show last few lines of output
    output_lines = stdout.strip().split('\n')
    for line in output_lines[-5:]:
        print(line)

    parsed_time_3 = parse_output_time(stdout)
    print(f"\n{Colors.GREEN}✅ Run 3 Complete{Colors.END}")
    print(f"   Elapsed: {elapsed_time:.2f}s")
    if parsed_time_3:
        print(f"   Processing: {parsed_time_3:.2f}s")
    results.append(('Using Cache (2nd)', elapsed_time, parsed_time_3))

    # Summary
    print(f"\n{Colors.BOLD}{Colors.CYAN}╔══════════════════════════════════════════════════╗{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}║  Benchmark Summary{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚══════════════════════════════════════════════════╝{Colors.END}\n")

    print(f"{Colors.BOLD}{'Run':<25} {'Elapsed':<15} {'Processing':<15}{Colors.END}")
    print(f"{Colors.GRAY}{'─'*55}{Colors.END}")

    for name, elapsed, processing in results:
        elapsed_str = f"{elapsed:.2f}s"
        proc_str = f"{processing:.2f}s" if processing else "N/A"
        print(f"{name:<25} {elapsed_str:<15} {proc_str:<15}")

    # Calculate speedup
    if results[0][1] > 0 and results[1][1] > 0:
        speedup_2 = results[0][1] / results[1][1]
        speedup_3 = results[0][1] / results[2][1]

        print(f"\n{Colors.BOLD}Performance Improvement:{Colors.END}")
        print(f"   Run 2 vs Run 1: {Colors.GREEN}{speedup_2:.1f}x faster{Colors.END}")
        print(f"   Run 3 vs Run 1: {Colors.GREEN}{speedup_3:.1f}x faster{Colors.END}")

        if speedup_2 > 10:
            print(f"   {Colors.GREEN}✨ Exceptional improvement!{Colors.END}")
        elif speedup_2 > 5:
            print(f"   {Colors.GREEN}🚀 Significant speedup!{Colors.END}")
        elif speedup_2 > 2:
            print(f"   {Colors.YELLOW}⚡ Moderate improvement{Colors.END}")
        else:
            print(f"   {Colors.YELLOW}📊 Slight improvement{Colors.END}")

    print()


if __name__ == '__main__':
    main()
