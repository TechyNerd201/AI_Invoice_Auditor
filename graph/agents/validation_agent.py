
from langchain_core.tools import tool

from pathlib import Path
import json

import os
import sys
import threading
import yaml
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_aws import ChatBedrock
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph, START, END
from state import JobState
from log_utils.logger import get_logger


logger = get_logger(__name__)

# Load validation rules from config
_rules_path = Path(__file__).resolve().parent.parent.parent / "config" / "rules.yaml"
try:
    with open(_rules_path, encoding="utf-8") as _f:
        _RULES = yaml.safe_load(_f)
except FileNotFoundError:
    logger.critical(
        "[validation_agent] rules.yaml not found at %s — validation rules will be empty.", _rules_path
    )
    raise FileNotFoundError(
        f"[validation_agent] Missing required config file: {_rules_path}"
    ) from None

_tolerances = _RULES.get("tolerances", {})
_accepted_currencies = _RULES.get("accepted_currencies", [])
_required_header_fields = _RULES.get("required_fields", {}).get("header", [])
_required_line_item_fields = _RULES.get("required_fields", {}).get("line_item", [])
_data_types = _RULES.get("data_types", {})
_validation_policies = _RULES.get("validation_policies", {})

val_data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "ERP_mockdata"

def _load_json(path: Path) -> list | dict:
    """Load a JSON file at import time with a clear error if missing or malformed."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.critical(
            "[validation_agent] Required ERP data file not found: %s — "
            "validation agent will be non-functional. "
            "Ensure the file exists before starting the API.",
            path,
        )
        raise FileNotFoundError(
            f"[validation_agent] Missing required ERP data file: {path}\n"
            f"Create the file or point val_data_dir to the correct directory."
        ) from None
    except json.JSONDecodeError as e:
        logger.critical(
            "[validation_agent] ERP data file is not valid JSON: %s — error: %s",
            path, e,
        )
        raise ValueError(
            f"[validation_agent] ERP data file contains invalid JSON: {path}\nDetail: {e}"
        ) from e

_PO_DATA     = _load_json(val_data_dir / "PO Records.json")
_VENDOR_DATA = _load_json(val_data_dir / "vendors.json")
_SKU_DATA    = _load_json(val_data_dir / "sku_master.json")

@tool
def division(num1: float, num2: float) -> float:
    """
    Divide num1 by num2 and return the result.

    Use this tool whenever you need to perform arithmetic division — for example,
    to compute a per-unit price or to derive a tax rate from a tax amount and subtotal.

    Args:
        num1: The dividend (number to be divided).
        num2: The divisor (number to divide by). Must not be zero.

    Returns:
        The result of num1 / num2.
        Returns an error message string if num2 is zero.
    """
    logger.debug("[validation_agent][tool.division] Calling division(%s, %s)", num1, num2)
    if num2 == 0:
        logger.warning("[validation_agent][tool.division] Division by zero attempted (num1=%s)", num1)
        return "Error: division by zero."
    return num1 / num2

@tool
def multiplication(num1: float, num2: float) -> float:
    """
    Multiply two numbers and return the result.

    Use this tool whenever you need to perform arithmetic multiplication — for example,
    to compute qty × unit_price when verifying an invoice line total.

    Args:
        num1: The first number.
        num2: The second number.

    Returns:
        The product of num1 and num2.
    """
    logger.debug("[validation_agent][tool.multiplication] Calling multiplication(%s, %s)", num1, num2)
    return num1 * num2

@tool
def addition(num1: float, num2: float) -> float:
    """
    Add two numbers and return the result.

    Use this tool whenever you need to perform arithmetic addition — for example,
    to compute subtotal + tax when verifying an invoice grand total.

    Args:
        num1: The first number.
        num2: The second number.

    Returns:
        The sum of num1 and num2.
    """
    logger.debug("[validation_agent][tool.addition] Calling addition(%s, %s)", num1, num2)
    return num1 + num2

@tool
def subtraction(num1: float, num2: float) -> float:
    """
    Subtract num2 from num1 and return the result.

    Use this tool whenever you need to perform arithmetic subtraction — for example,
    to compute the difference between an expected and an actual value when checking
    invoice totals or line item amounts.

    Args:
        num1: The minuend (number to subtract from).
        num2: The subtrahend (number to subtract).

    Returns:
        The result of num1 - num2.
    """
    logger.debug("[validation_agent][tool.subtraction] Calling subtraction(%s, %s)", num1, num2)
    return num1 - num2

@tool 
def find_PO_records( PO_number :str) -> dict:
    """
    Look up a Purchase Order (PO) from the ERP system by PO number.

    Use this tool when you need to verify whether a PO exists in the system
    and to retrieve its details such as vendor ID, line items, quantities,
    unit prices, and currencies.

    Args:
        PO_number: The PO number from the invoice (e.g. 'PO-1001'). 
                   Case-insensitive.

    Returns:
        On success: {"success": True, "result": <PO record>, "error": None}
        On failure: {"success": False, "result": None, "error": "<reason>"}

        Each PO record contains:
          - po_number: str
          - vendor_id: str
          - line_items: list of {item_code, description, qty, unit_price, currency}
    """
    logger.debug("[validation_agent][tool.find_PO_records] Looking up PO number: %r", PO_number)
    try:
        po_number = PO_number.strip().upper()
        po_data = None
        for record in _PO_DATA:
            if record["po_number"] == po_number:
                logger.debug("[validation_agent][tool.find_PO_records] Found PO record for '%s'", po_number)
                return {"success": True, "result": record, "error": None}
        
        logger.warning("[validation_agent][tool.find_PO_records] PO '%s' not found in ERP", po_number)
        return {"success": False, "result": None,"error_type": "PO_NOT_FOUND" , "error": f"PO '{po_number}' not found in ERP"}

    except Exception as e:
        logger.error("[validation_agent][tool.find_PO_records] Error during lookup for PO '%s': %s", PO_number, e, exc_info=True)
        return {"success": False, "result": None,"error_type": "tool_error", "error": "Error occurred during executing the tool."}

@tool 
def find_vendor_records(vendor_id: str) -> dict:
    """
    Look up a vendor from the ERP vendor data by vendor ID.

    Use this tool when you need to verify whether the vendor on the invoice
    exists in the system and to check their registered details such as
    vendor name, country, and expected currency.

    Args:
        vendor_id: The vendor ID from the invoice (e.g. 'VEND-001').
                   Case-insensitive.

    Returns:
        On success: {"success": True, "result": <vendor record>, "error": None}
        On failure: {"success": False, "result": None, "error": "<reason>"}

        Each vendor record contains:
          - vendor_id: str
          - vendor_name: str
          - country: str
          - currency: str (expected currency for this vendor, e.g. 'USD', 'EUR')
    """
    logger.debug("[validation_agent][tool.find_vendor_records] Looking up vendor_id: %r", vendor_id)
    try:
        vendor_id = vendor_id.strip().upper()
        for record in _VENDOR_DATA:
            if record["vendor_id"] == vendor_id:
                logger.debug("[validation_agent][tool.find_vendor_records] Found vendor record for '%s'", vendor_id)
                return {"success": True , "result": record, "error": None}
        
        logger.warning("[validation_agent][tool.find_vendor_records] Vendor '%s' not found in ERP", vendor_id)
        return {"success": False, "result": None,"error_type": "VENDOR_NOT_FOUND", "error": f"Vendor '{vendor_id}' not found in ERP"}

    except Exception as e:
        logger.error("[validation_agent][tool.find_vendor_records] Error during lookup for vendor '%s': %s", vendor_id, e, exc_info=True)
        return {"success": False, "result": None,"error_type": "tool_error", "error": f"Error occurred during executing the tool."}

@tool
def find_sku_records(sku_code: str) -> dict:
    """
    Look up an item from the company's SKU master (product catalogue) by item code.

    Use this tool to verify whether an item code on the invoice is a recognized
    product in our system, and to retrieve its expected unit of measure (UOM)
    and applicable GST tax rate.

    Args:
        sku_code: The item/product code from the invoice (e.g. 'SKU-001').
                  Case-insensitive.

    Returns:
        On success: {"success": True, "result": <SKU record>, "error": None}
        On failure: {"success": False, "result": None, "error": "<reason>"}

        Each SKU record contains:
          - item_code: str
          - category: str  (e.g. 'Packaging', 'Safety', 'Logistics')
          - uom: str       (unit of measure, e.g. 'roll', 'pair', 'piece')
          - gst_rate: int  (applicable GST percentage, e.g. 10)
    """
    logger.debug("[validation_agent][tool.find_sku_records] Looking up sku_code: %r", sku_code)
    try:
        sku_code = sku_code.strip().upper()
        for record in _SKU_DATA:
            if record["item_code"] == sku_code:
                logger.debug("[validation_agent][tool.find_sku_records] Found SKU record for '%s'", sku_code)
                return {'success': True, 'result': record, 'error': None}
        
        logger.warning("[validation_agent][tool.find_sku_records] SKU '%s' not found in ERP", sku_code)
        return {'success': False, 'result': None,"error_type": "SKU_NOT_FOUND", 'error': f'SKU "{sku_code}" not found in ERP'}
        
    
    except Exception as e:
        logger.error("[validation_agent][tool.find_sku_records] Error during lookup for SKU '%s': %s", sku_code, e, exc_info=True)
        return {'success': False, 'result': None,"error_type": "tool_error", 'error': f'Error occurred during executing the tool;{str(e)}'}


# ---------------------------------------------------------------------------
# Findings buffer — thread-local so concurrent jobs never share state
# ---------------------------------------------------------------------------

_thread_local = threading.local()


def _get_findings_buffer() -> list:
    """Return the findings buffer for the current thread, creating it if needed."""
    if not hasattr(_thread_local, "findings_buffer"):
        _thread_local.findings_buffer = []
    return _thread_local.findings_buffer


@tool
def record_finding(check: str, status: str, message: str) -> str:
    """
    Record a validation finding after completing each check.

    You MUST call this tool after every validation check — whether it passed,
    failed, or resulted in a warning. This is the only way validation results
    are captured and passed to the next stage (RAG ingestion and report generation).

    Args:
        check:   Short machine-readable name of the check. Use one of:
                   'vendor_exists', 'vendor_currency', 'po_exists', 'po_vendor_match',
                   'line_item_exists', 'line_item_qty', 'line_item_price',
                   'line_item_currency', 'tax_rate', 'total_calculation'
        status:  Result of the check. Must be exactly one of: 'pass', 'fail', 'warning'
                   - 'pass'    : check succeeded, values match
                   - 'fail'    : check failed, mismatch or missing data found
                   - 'warning' : check could not be completed (e.g. field missing on invoice)
        message: Human-readable description of the finding, including relevant values.
                 Give descriptive message .
    Returns:
        Confirmation that the finding was recorded.
    """
    try:
        logger.info("[validation_agent][tool.record_finding] [%s] %s: %s", status.upper(), check, message)
        _get_findings_buffer().append({"check": check, "status": status, "message": message})
        return f"Finding recorded: [{status.upper()}] {check} — {message}"

    except Exception as e:
        logger.error("[validation_agent][tool.record_finding] Error recording finding (check='%s'): %s", check, e, exc_info=True)
        return f"Error recording finding: {str(e)}"



# nodes
def update_state_node(state: JobState) -> dict:
    buf = _get_findings_buffer()
    findings = list(buf)
    buf.clear()

    failed  = any(f["status"] == "fail" for f in findings)
    passed  = not failed

    logger.info("[validation_agent][update_state_node] Done. findings=%d, passed=%s", len(findings), passed)
    return {
        "validation_findings": findings,   # operator.add appends to existing list
        "validation_passed":   passed,
    }

# Build and compile once at module load — avoids expensive recompilation per request
_val_llm = ChatBedrock(
    model_id=os.getenv("AWS_BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0"),
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    model_kwargs={"temperature": 0},
)
_val_tools = [find_PO_records, find_vendor_records, find_sku_records, record_finding, addition, subtraction, multiplication, division]
_val_llm_with_tools = _val_llm.bind_tools(_val_tools)


def _val_llm_node(s: JobState) -> Dict:
    response = _val_llm_with_tools.invoke(s["messages"])
    return {"messages": [response]}


_val_tool_node = ToolNode(_val_tools)

_val_graph = StateGraph(JobState)
_val_graph.add_node("llm",          _val_llm_node)
_val_graph.add_node("tools",        _val_tool_node)
_val_graph.add_node("update_state", update_state_node)

_val_graph.add_edge(START, "llm")
_val_graph.add_conditional_edges("llm", tools_condition, {
    "tools": "tools",
    END: "update_state"
})
_val_graph.add_edge("tools", "llm")
_val_graph.add_edge("update_state", END)

_compiled_validation_agent = _val_graph.compile()


def validation_agent_with_tools(state: JobState) -> Dict[str, Any]:
    """
    Validation agent built with StateGraph using JobState directly.
    """
    try:
        logger.info("[validation_agent][validation_agent_with_tools] Starting for job_id=%s", state.get('job_id', 'unknown'))
        events = []
        events.append(SystemMessage(content=f"[validation_agent] Starting for job_id={state.get('job_id')}"))

        invoice_data = {
            "invoice_text": state.get("raw_invoice_text", ""),
            "tables": state.get("tables", []),
            "line_items": state.get("line_items", []),
            "metadata": state.get("metadata", {})
        }
        invoice_json = json.dumps(invoice_data, indent=2, ensure_ascii=False)

        result = _compiled_validation_agent.invoke(
            {
                **state,
                "messages": [
                    SystemMessage(content=f"""
You are a strict invoice validator agent. Use the provided tools to fetch ERP data and validate the invoice.
Never make up information. Never justify mismatches. Flag every discrepancy.

=== VALIDATION RULES (from rules.yaml — apply these exactly) ===

Required header fields that MUST be present: {_required_header_fields}
Required line item fields that MUST be present: {_required_line_item_fields}

Expected data types for each field — validate that values match these types:
{_data_types}
Rules:
- str: must be a non-empty string
- float: must be a valid number (integer or decimal)
- date: must be a recognisable date format (e.g. YYYY-MM-DD, DD-Mon-YYYY)
Flag as FAIL if a field contains the wrong type (e.g. total_amount is "N/A" instead of a number).

Accepted currencies: {_accepted_currencies}
(Reject any currency not in this list)

Tolerances when comparing invoice vs ERP:
- Unit price difference: ±{_tolerances.get('price_difference_percent', 5)}%
  (flag as FAIL if deviation exceeds this)
- Quantity difference: ±{_tolerances.get('quantity_difference_percent', 0)}%
  (quantity must match exactly — zero tolerance)
- Tax amount difference: ±{_tolerances.get('tax_difference_percent', 2)}%
  (flag as FAIL if deviation exceeds this)

=== MANDATORY CHECKS ===
1. Vendor name on invoice matches ERP vendor record.
2. PO number exists in ERP.
3. Quantity per line item matches ERP PO — EXACT match required (0% tolerance).
4. Unit price per line item is within ±{_tolerances.get('price_difference_percent', 5)}% of ERP PO price.
5. Tax rate for each item matches SKU master.
6. All arithmetic is correct (qty × unit_price = line total, sum of lines = subtotal, subtotal + tax = grand total).
7. All required header fields are present: {_required_header_fields}.
8. Invoice currency is one of the accepted currencies: {_accepted_currencies}.

Also perform any additional validations you find relevant.

=== VALIDATION POLICIES (apply these exactly) ===
- Missing mandatory field → action: {_validation_policies.get('missing_field_action', 'flag')} (mark as FAIL if action is 'flag' or 'reject')
- Total mismatch beyond tolerance → action: {_validation_policies.get('total_mismatch_action', 'manual_review')} (flag as MANUAL REVIEW if action is 'manual_review')
- Invalid/unsupported currency → action: {_validation_policies.get('invalid_currency_action', 'reject')} (hard FAIL if action is 'reject')
- Auto-approve only if ALL checks pass AND translation confidence ≥ {_validation_policies.get('auto_approve_confidence_threshold', 0.95)}
"""),
                    HumanMessage(content=f"""Validate the invoice below against ERP records. Think through each aspect of the invoice, look up relevant ERP data using the tools, and call record_finding for every check you perform.

    Invoice data:
    {invoice_json}
    Think step by step and do the arithematics carefully.
    """)
                ],
                "validation_findings": [],
                "validation_passed":   None,
            },
            config={"recursion_limit": 100},
        )

        logger.info("[validation_agent][validation_agent_with_tools] Completed for job_id=%s. findings=%d, passed=%s",
                    state.get('job_id', 'unknown'),
                    len(result.get("validation_findings", [])),
                    result.get("validation_passed"))
        events.append(SystemMessage(content=f"[validation_agent] Completed for job_id={state.get('job_id', 'unknown')}"))
        result = {
            "events": events,
            "validation_findings": result.get("validation_findings", []),
            "validation_passed":   result.get("validation_passed"),
        }
        logger.warning("STATE IN VALIDATION AGENT : %s", result)
        return result
    
    except Exception as e:
        logger.error("[validation_agent][validation_agent_with_tools] Error: %s", e, exc_info=True)
        return {
            "events": [SystemMessage(content=f"[validation_agent][validation_agent_with_tools] Error: {str(e)}")],
            "validation_findings": [],
            "validation_passed":   None,
            "error": [f"[validation_agent] Error occurred: {e}"]
            }


# if __name__ == "__main__":
#     from dotenv import load_dotenv
#     load_dotenv()
#     state ={
#         'error': [],
#         'raw_invoice_text': "OceanFreight Pvt Ltd\n3 Coastal Road, Mumbai,India\nDate: 1 June 2025\nPO: PO-1006\n------------------------------------------------\nItem Code | Description | Qty | Unit | Total\n------------------------------------------------\nSKU-501 | Container Transport | 5 | 8000 | 40000\n------------------------------------------------\n Subtotal: 40000\nTax (10%): 4000\nTotal: 44000\n------------------------------------------------", 
#         'tables': [],
#         'line_items': [], 
#         'metadata': {'sender': 'accounts@oceanfreight.in', 'subject': 'Invoice for Container Transport - PO-1006', 'received_timestamp': '2025-06-01T09:00:00Z',  'language': 'en','attachments': ['INV_EN_006_malformed.pdf']}, 
#         'invoice_extract_method': 'pdf_text', 
#         'extraction_confidence': 0.9, 
#         'warnings': []
#     }

#     result = validation_agent_with_tools(state)
#     print(result)
