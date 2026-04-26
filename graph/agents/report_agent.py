import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
import json
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq as ChatOpenAI
from state import JobState
from dotenv import load_dotenv
from log_utils.logger import get_logger
load_dotenv()

logger = get_logger(__name__)



def report_agent(state: JobState) -> Dict[str, Any]:
    """
    Report Agent: Generates comprehensive, business-ready audit report.
    Uses LLM to translate technical findings into executive-level insights.
    """
    try:
        logger.info("[report_agent][report_agent] Starting for job_id=%s", state.get('job_id', 'unknown'))
        events =[]
        events.append(SystemMessage(content=f"[reporting_agent] Starting. job_id={state.get('job_id')}"))

        llm = ChatOpenAI(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0,
        )

        # Extract state data
        findings          = state.get("validation_findings", [])
        validation_passed = state.get("validation_passed")
        metadata          = state.get("metadata", {})
        raw_invoice_text  = state.get("raw_invoice_text", "")
        line_items        = state.get("line_items", [])
        tables            = state.get("tables", [])
        warnings          = state.get("warnings", [])
        job_id            = state.get("job_id", "N/A")
        extraction_confidence = state.get("extraction_confidence")
        detected_language = state.get("detected_language")
        po_number         = state.get("po_number", "Not provided")
        vendor_id         = state.get("vendor_id", "Not provided")

        # Categorize findings
        passed_findings  = [f for f in findings if f.get("status") == "pass"]
        failed_findings  = [f for f in findings if f.get("status") == "fail"]
        warning_findings = [f for f in findings if f.get("status") == "warning"]

        logger.debug("[report_agent][report_agent] Findings breakdown — passed=%d, failed=%d, warnings=%d for job_id=%s",
                     len(passed_findings), len(failed_findings), len(warning_findings), job_id)

        # Determine audit result
        if validation_passed and not warning_findings:
            audit_result = "APPROVED"
        elif validation_passed and warning_findings:
            audit_result = "REVIEW REQUIRED"
        else:
            audit_result = "REJECTED"

        # Prepare structured data for LLM
        invoice_data = {
            "job_id": job_id,
            "audit_date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "audit_result": audit_result,
            "audit_summary": {
                "total_checks": len(findings),
                "passed": len(passed_findings),
                "failed": len(failed_findings),
                "warnings": len(warning_findings),
            },
            "invoice": {
                "po_number": po_number,
                "vendor_id": vendor_id,
                "raw_text": raw_invoice_text[:500],  # Truncate for prompt efficiency
                "line_items": line_items,
                "line_item_count": len(line_items),
                "extraction_confidence": extraction_confidence,
                "detected_language": detected_language,
            },
            "metadata": metadata,
            "validation_findings": {
                "passed": passed_findings,
                "failed": failed_findings,
                "warnings": warning_findings,
            },
            "agent_warnings": warnings,
        }

        # ========================================================================
        # IMPROVED SYSTEM PROMPT
        # ========================================================================
        
        system_prompt = """You are a Senior Invoice Audit Specialist at a global logistics company.

    Your task: Generate a formal, comprehensive, and business-ready invoice audit report in Markdown format.

    AUDIENCE:
    - Finance Managers (approve/reject payment)
    - Compliance Officers (ensure regulatory adherence)
    - Senior Management (understand financial risk)
    - Non-technical business stakeholders

    They need plain English explanations — NO technical jargon, NO system codes, NO assumptions.

    ---

    REPORT STRUCTURE:

    # Invoice Audit Report

    ## 1. Executive Summary
    - **Job ID**: [value]
    - **Audit Date**: [value]
    - **Final Verdict**: ✅ APPROVED / ⚠️ REVIEW REQUIRED / ❌ REJECTED

    **Summary** (4-5 sentences):
    - What invoice was audited (PO number, vendor)
    - What the system verified (e.g., "validated against purchase order PO-1002 and vendor master")
    - What was found (e.g., "2 critical discrepancies and 1 warning")
    - Final recommendation (approve, review, or reject)

    ---

    ## 2. Invoice Overview

    Present key invoice details in plain business language:

    | Field | Value |
    |-------|-------|
    | Purchase Order (PO) Number | [value or "Not provided"] |
    | Vendor ID | [value or "Not provided"] |
    | Invoice Number | [value or "Not provided"] |
    | Invoice Date | [value or "Not provided"] |
    | Currency | [value or "Not provided"] |
    | Subtotal | [value or "Not provided"] |
    | Tax | [value or "Not provided"] |
    | Grand Total | [value or "Not provided"] |
    | Language Detected | [value] |
    | Extraction Confidence | [value]% |

    **Line Items:**

    If line items exist, present as:

    | # | Description | Qty | Unit Price | Currency | Total |
    |---|-------------|-----|------------|----------|-------|
    | 1 | ... | ... | ... | ... | ... |

    If no line items: "No line items extracted."

    ---

    ## 3. Validation Summary

    | Metric | Count |
    |--------|-------|
    | **Total Checks** | [number] |
    | ✅ **Passed** | [number] |
    | ❌ **Failed** | [number] |
    | ⚠️ **Warnings** | [number] |

    **Interpretation** (2-3 sentences):
    Explain what these numbers mean in business terms. Example:
    "The system ran 12 validation checks. 10 passed successfully, confirming the invoice matches the purchase order. However, 2 checks failed due to price discrepancies, indicating potential overbilling."

    ---

    ## 4. Detailed Findings

    ### TRANSLATION GUIDE (CRITICAL):
    NEVER use raw technical check names. Always translate to plain English:

    | Technical Name | Plain English Title |
    |----------------|---------------------|
    | `vendor_exists` | "Vendor Identity Verification" |
    | `vendor_name` | "Vendor Name Match" |
    | `vendor_currency` | "Vendor Currency Consistency" |
    | `po_exists` | "Purchase Order Existence Check" |
    | `po_vendor_match` | "PO-Vendor Cross-Reference" |
    | `line_item_exists` | "Line Item ERP Verification" |
    | `line_item_qty` | "Quantity Match Against PO" |
    | `line_item_price` | "Unit Price Match Against PO" |
    | `line_item_currency` | "Line Item Currency Verification" |
    | `tax_rate` | "Tax Rate Compliance Check" |
    | `total_calculation` | "Invoice Total Calculation Accuracy" |
    | `invoice_number` | "Invoice Number Validation" |
    | [other] | Translate to business-friendly language |

    ---

    ### 4.1 ✅ Passed Checks

    For each passed check:

    **[Plain English Title]**

    - **Purpose**: Explain what this check verifies and why it matters (1-2 sentences)
    - **Result**: What was confirmed (1 sentence)
    - **Business Impact**: Why this is positive (1 sentence)

    Example:
    **Vendor Identity Verification**
    - **Purpose**: Confirms the vendor exists in our approved vendor master database and is authorized to invoice us.
    - **Result**: Vendor ID VEND-002 was successfully verified in the system.
    - **Business Impact**: This ensures we are paying a legitimate, pre-approved supplier.

    ---

    ### 4.2 ❌ Failed Checks

    For each failed check:

    **[Plain English Title]**

    - **Purpose**: What this check verifies and why it's critical (1-2 sentences)
    - **Expected**: What should have been found (from PO/ERP)
    - **Actual**: What was found on the invoice
    - **Discrepancy**: Calculate and state the difference (amount, percentage, etc.)
    - **Business Impact**: What risk this creates (overbilling, fraud, compliance violation, etc.)
    - **Severity**: CRITICAL / HIGH / MEDIUM

    Example:
    **Unit Price Match Against PO**
    - **Purpose**: Verifies that the unit price on the invoice matches the agreed price in the purchase order.
    - **Expected**: $1.25 per unit (per PO-1002)
    - **Actual**: $1.50 per unit (per invoice)
    - **Discrepancy**: $0.25 overcharge per unit (20% higher than agreed)
    - **Business Impact**: Potential overbilling of $50 for this line item. This suggests either a pricing error or unauthorized price increase.
    - **Severity**: CRITICAL

    ---

    ### 4.3 ⚠️ Warnings

    For each warning:

    **[Plain English Title]**

    - **Purpose**: What this check verifies (1-2 sentences)
    - **Issue**: Why the check could not be completed (missing data, unclear value, etc.)
    - **Risk**: What could go wrong if this is ignored (1-2 sentences)
    - **Recommended Action**: What should be done to resolve this (1 sentence)

    Example:
    **Tax Rate Compliance Check**
    - **Purpose**: Verifies that the GST/tax rate applied matches the rate defined in the SKU master for this item category.
    - **Issue**: Item code was not found on the invoice, so the system could not verify the correct tax rate.
    - **Risk**: Incorrect tax rate could result in underpayment or overpayment of taxes, leading to compliance issues.
    - **Recommended Action**: Manually verify the tax rate with the vendor and update the invoice if needed.

    ---

    ## 5. Recommendations

    Provide numbered, specific, actionable steps for the finance team:

    1. **For Failed Check: [Plain English Title]**
    - Action: [What to do]
    - Owner: [Who should do it - e.g., "Finance Manager", "Procurement Team"]
    - Priority: URGENT / HIGH / MEDIUM

    2. **For Warning: [Plain English Title]**
    - Action: [What to do]
    - Owner: [Who should do it]
    - Priority: MEDIUM / LOW

    If ALL checks passed:
    "✅ All validation checks passed successfully. This invoice is approved for payment processing. No further action required."

    ---

    ## 6. Pipeline & System Warnings

    If agent_warnings exist:
    List each warning with:
    - **Agent**: Which processing stage (extractor, translator, validator)
    - **Issue**: Plain English description
    - **Impact**: How this might affect the audit accuracy

    If no warnings:
    "✅ No system errors encountered during invoice processing."

    ---

    ## 7. Audit Trail

    | Processing Step | Status | Notes |
    |----------------|--------|-------|
    | Document Extraction | ✅/❌ | [brief note] |
    | Language Translation | ✅/❌ | [brief note] |
    | PO Matching | ✅/❌ | [brief note] |
    | Validation | ✅/❌ | [brief note] |
    | Report Generation | ✅/❌ | [brief note] |

    ---

    ## 8. Conclusion

    Restate the final verdict and next steps in 2-3 sentences.

    Example:
    "Based on the validation findings, this invoice is **REJECTED** due to 2 critical price discrepancies totaling $150 in potential overbilling. The invoice should be returned to the vendor for correction before payment is processed."

    ---

    CRITICAL RULES:
    1. ✅ Use ONLY the data provided — no assumptions, no invention
    2. ✅ ALWAYS translate technical check names to plain English
    3. ✅ Write for non-technical business readers
    4. ✅ If data is missing, write "Not provided" — never guess
    5. ✅ Output pure Markdown — no code fences, no JSON wrapper
    6. ✅ Be specific with numbers (amounts, percentages, counts)
    7. ✅ Every failed check must have a recommendation
    8. ✅ Use emojis sparingly for visual clarity (✅ ❌ ⚠️)
    """

        # ========================================================================
        # HUMAN PROMPT
        # ========================================================================
        
        human_prompt = f"""Generate the complete invoice audit report using this data:

    {json.dumps(invoice_data, indent=2, ensure_ascii=False)}

    Remember:
    - Translate all technical check names to plain English
    - Explain every finding as if to a non-technical finance manager
    - Be specific with numbers and percentages
    - Provide actionable recommendations for failed checks
    - Output should in text only.
    """

        # ========================================================================
        # INVOKE LLM
        # ========================================================================
        
        try:
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt),
            ])
            
            audit_report = response.content
            
            # Save report
            reports_dir = Path(__file__).resolve().parent.parent.parent / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            report_filename = reports_dir / f"audit_report_{job_id}.md"
            with open(report_filename, "w", encoding="utf-8") as f:
                f.write(audit_report)
            
            logger.info("[report_agent][report_agent] Report saved to '%s' for job_id=%s", report_filename, job_id)
            events.append(SystemMessage(content=f"[reporting_agent]  Report generated: {report_filename}"))
              
            result = {
                "report": audit_report,
                "events": events
            }
            logger.warning("STATE IN REPORT AGENT : %s", result)
            return result
        
        except Exception as e:
            logger.error("[report_agent][report_agent] LLM invocation failed for job_id=%s: %s", job_id, e, exc_info=True)
            
            return {
                "events": [SystemMessage(content=f"[reporting_agent] Error generating report: {str(e)}")],
                "error": [f"[reporting_agent]: Reporting Agent failed: {e}"],
            }
    except Exception as e:
        logger.error("[report_agent][report_agent] Fatal error for job_id=%s: %s", state.get('job_id', 'unknown'), e, exc_info=True)
        return {
            "events": [SystemMessage(content=f"Error generating report: {str(e)}")],
            "error": [f"[reporting_agent]: Reporting Agent  failed: {e}"],
        }

