#!/usr/bin/env python
"""
Quick Test Runner - AI Invoice Auditor

Usage:
    python run_tests.py          # Run all quick tests
    python run_tests.py --full   # Run all tests including slow
    python run_tests.py --help   # Show options
"""

import subprocess
import sys
import argparse
from pathlib import Path


def run_command(cmd: list, description: str = None):
    """Run a command and print result"""
    if description:
        print(f"\n{'='*70}")
        print(f"🧪 {description}")
        print(f"{'='*70}")
    
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Run AI Invoice Auditor tests")
    parser.add_argument("--full", action="store_true", help="Run all tests including slow ones")
    parser.add_argument("--smoke", action="store_true", help="Run quick smoke tests only")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("--html", action="store_true", help="Generate HTML test report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--marker", "-m", help="Run tests matching marker (e.g., 'not slow')")
    
    args = parser.parse_args()
    
    # Base pytest command
    cmd = ["python", "-m", "pytest", "tests/integration/", "-v"]
    
    # Add markers
    if args.smoke:
        cmd.extend(["-m", "not slow"])
        description = "Smoke Tests (Quick)"
    elif args.full:
        description = "Full Test Suite"
    elif args.marker:
        cmd.extend(["-m", args.marker])
        description = f"Tests: {args.marker}"
    else:
        cmd.extend(["-m", "not slow"])
        description = "Quick Tests (Recommended)"
    
    # Add options
    if args.verbose:
        cmd.append("-vv")
    
    if args.coverage:
        cmd.extend(["--cov=API", "--cov=services", "--cov-report=term-missing"])
        description += " + Coverage"
    
    if args.html:
        cmd.append("--html=tests/output/report.html")
        description += " + HTML Report"
    
    # Run tests
    success = run_command(cmd, description)
    
    # Post-test info
    if success:
        print("\n" + "="*70)
        print("✅ All tests passed!")
        print("="*70)
        
        if args.coverage:
            print("\n📊 Coverage report generated")
        if args.html:
            print("\n📄 HTML report: tests/output/report.html")
    else:
        print("\n" + "="*70)
        print("❌ Some tests failed")
        print("="*70)
        sys.exit(1)


if __name__ == "__main__":
    main()
