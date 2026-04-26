"""
demo.py — End-to-end workflow demo for the AI Invoice Auditor.

Usage (from project root):
    python demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent))

from workflow.workflow import workflow

# ── Invoice to demo ────────────────────────────────────────────────────────
INVOICE_PATH  = str(Path("data/incoming/INV_ES_003.pdf").resolve())
METADATA_PATH = str(Path("data/incoming/INV_ES_003.meta.json").resolve())
JOB_ID        = "DEMO-002"

SEP = "=" * 70


def section(title: str):
    print(f"\n{SEP}\n  {title}\n{SEP}")


def main():
    section("AI INVOICE AUDITOR — DEMO")
    print(f"  Job ID   : {JOB_ID}")
    print(f"  Invoice  : {INVOICE_PATH}")
    print(f"  Metadata : {METADATA_PATH}")

    # ── Run ───────────────────────────────────────────────────────────────
    section("RUNNING PIPELINE")
    print("  extractor → translate → validate → report → ingest")

    result = workflow({
        "job_id":        JOB_ID,
        "invoice_path":  INVOICE_PATH,
        "metadata_path": METADATA_PATH,
    })

    # ── Errors ────────────────────────────────────────────────────────────
    errors   = result.get("error", [])
    warnings = result.get("warnings", [])
    findings = result.get("validation_findings", [])
    passed   = result.get("validation_passed")
    report   = result.get("report")
    chunks   = result.get("chunk_count")

    section("PIPELINE ERRORS & WARNINGS")
    if errors:
        print(f"  ❌ Errors ({len(errors)}):")
        for e in errors:
            print(f"     • {e}")
    else:
        print("  ✅ No pipeline errors")

    if warnings:
        print(f"\n  ⚠️  Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"     • {w}")
    else:
        print("  ✅ No warnings")

    # ── Validation ────────────────────────────────────────────────────────
    section("VALIDATION RESULTS")
    if findings:
        passed_f  = [f for f in findings if f["status"] == "pass"]
        failed_f  = [f for f in findings if f["status"] == "fail"]
        warning_f = [f for f in findings if f["status"] == "warning"]

        print(f"  Total checks   : {len(findings)}")
        print(f"  ✅ Passed      : {len(passed_f)}")
        print(f"  ❌ Failed      : {len(failed_f)}")
        print(f"  ⚠️  Warnings   : {len(warning_f)}")
        print(f"  Overall result : {'PASSED' if passed else 'FAILED'}")

        if failed_f:
            print("\n  Failed checks:")
            for f in failed_f:
                print(f"     [{f['check']}] {f['message']}")
        if warning_f:
            print("\n  Warning checks:")
            for f in warning_f:
                print(f"     [{f['check']}] {f['message']}")
    else:
        print("  No validation findings (skipped due to extractor error or empty invoice)")

    # ── Report ────────────────────────────────────────────────────────────
    section("AUDIT REPORT PREVIEW")
    if report:
        print(report[:600].strip())
        if len(report) > 600:
            print(f"\n  ... [{len(report) - 600} more characters] ...")
        print(f"\n  Full report saved → audit_report_{JOB_ID}.md")
    else:
        print("  No report generated")

    # ── Ingestion ─────────────────────────────────────────────────────────
    section("QDRANT INGESTION")
    if chunks is not None:
        print(f"  ✅ {chunks} vector(s) stored in Qdrant")
    else:
        print("  Ingestion skipped or failed")

    section("DEMO COMPLETE")
    return result


if __name__ == "__main__":
    main()
