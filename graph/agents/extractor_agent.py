from __future__ import annotations
import pdfplumber
import pytesseract
from PIL import Image
from dotenv import load_dotenv
from state import JobState
import os

from typing import Optional, TypedDict, Dict, Any, List, NotRequired
from typing import List, Dict, Any
from pathlib import Path
import sys
import json
from log_utils.logger import get_logger
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_groq import ChatGroq as ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph, MessagesState, START, END
from typing import Optional, Annotated
from langgraph.graph.message import add_messages

logger = get_logger(__name__)



load_dotenv()


@tool
def extract_pdf_text(pdf_path: str) -> str:
    """
    Extract plain text from a PDF file using pdfplumber.
    Use this for digital PDFs with selectable text.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text as a string
    """
    logger.info("[extract_pdf_text] Extracting text from: %s", pdf_path)
    texts: List[str] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text.strip():
                    texts.append(text)
        logger.debug("[extract_pdf_text] Extracted text from %d page(s): %s", len(texts), pdf_path)
        return "\n\n".join(texts)
    except Exception as e:
        logger.error("[extract_pdf_text] Failed for %s: %s", pdf_path, e, exc_info=True)
        return json.dumps({"error": f"Error extracting PDF text: {str(e)}"})


@tool
def extract_pdf_tables(pdf_path: str) -> str:
    """
    Extract tables from a PDF file using pdfplumber.
    Returns structured table data as JSON string.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        JSON string with tables: [{page, table_index, rows, row_count, col_count}, ...]
    """
    logger.info("[extract_pdf_tables] Extracting tables from: %s", pdf_path)
    all_tables: List[Dict[str, Any]] = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                for table_idx, table in enumerate(tables):
                    if not table or len(table) == 0:
                        continue
                    
                    # Filter empty rows
                    rows = [row for row in table if any(cell and str(cell).strip() for cell in row)]
                    
                    if rows:
                        all_tables.append({
                            "page": page_num,
                            "table_index": table_idx,
                            "rows": rows,
                            "row_count": len(rows),
                            "col_count": len(rows[0]) if rows else 0,
                        })
        
        logger.debug("[extract_pdf_tables] Found %d table(s) in: %s", len(all_tables), pdf_path)
        return json.dumps(all_tables, ensure_ascii=True)  # ensure_ascii=True escapes control chars as \uXXXX, preventing JSONDecodeError on parse
    except Exception as e:
        logger.error("[extract_pdf_tables] Failed for %s: %s", pdf_path, e, exc_info=True)
        return json.dumps({"error": f"Error extracting tables: {str(e)}"})


@tool
def extract_line_items_from_table(table_json: str) -> str:
    """
    Post-process extracted tables to extract clean line items (charges/products).
    Handles merged cells and splits multi-line rows.

    Args:
        table_json: JSON string from extract_pdf_tables — pass the FULL output
                    (either a list of tables or a single table dict).

    Returns:
        JSON string with line items: [{description, quantity, rate, currency, amount_vnd}, ...]
    """
    import re
    
    try:

        table = json.loads(table_json, strict=False)
        if isinstance(table, list):
            if not table:
                return json.dumps([])
            table = table[0]
        if "error" in table:
            return table_json
        
        rows = table.get("rows", [])
        logger.debug("[extract_line_items_from_table] Processing table with %d rows", len(rows))
        line_items: List[Dict[str, Any]] = []
        
        # Find header row (contains "Charge Description")
        header_idx = None
        for i, row in enumerate(rows):
            if row and row[0] and "Charge Description" in str(row[0]):
                header_idx = i
                break
        
        if header_idx is None:
            logger.warning("[extract_line_items_from_table] Header row ('Charge Description') not found — returning empty")
            return json.dumps([])
        
        # Process rows after header
        for i in range(header_idx + 1, len(rows)):
            cell = rows[i][0]

            # Check ALL cells in the row for totals/footer keywords, not just column 0
            full_row_text = " ".join(str(c).lower() for c in rows[i] if c)
            if any(kw in full_row_text for kw in ["rate of exchange", "total excluding", "total including", "vat applied", "total vat"]):
                break

            if not cell or not isinstance(cell, str):
                continue
            
            # Split merged rows (separated by newlines)
            lines = [ln.strip() for ln in cell.split("\n") if ln.strip()]
            
            # Get amounts from column 2 (if exists)
            amount_col = rows[i][2] if len(rows[i]) > 2 and rows[i][2] else None
            amounts = []
            if amount_col and isinstance(amount_col, str):
                amounts = [a.strip() for a in amount_col.split("\n") if a.strip()]
            
            for line_idx, line in enumerate(lines):
                # Remove leading codes
                line = re.sub(r"^(40RH|20GP|C|F1)\s+", "", line).strip()
                
                # Find currency
                currencies = ["USD", "VND", "EUR"]
                currency = None
                currency_idx = -1
                
                parts = line.split()
                for j, part in enumerate(parts):
                    if part in currencies:
                        currency = part
                        currency_idx = j
                        break
                
                if currency_idx == -1:
                    # Handle UNI (unit) case
                    if "UNI" in line:
                        match = re.match(r"^(.+?)\s+\d+UNI\s+(.+)", line)
                        if match:
                            desc = match.group(1).strip()
                            rest = match.group(2).strip()
                            nums = re.findall(r"[\d,\.]+", rest)
                            rate = nums[0].replace(",", "") if nums else ""
                            
                            item = {
                                "description": desc,
                                "quantity": "1",
                                "rate": rate,
                                "currency": "VND",
                                "amount_vnd": amounts[line_idx] if line_idx < len(amounts) else "",
                            }
                            line_items.append(item)
                    continue
                
                # Extract rate and quantity
                rate = None
                qty = None
                
                # Check before and after currency
                if currency_idx > 0:
                    try:
                        candidate = parts[currency_idx - 1].replace(",", "")
                        float(candidate)
                        rate = candidate
                    except:
                        pass
                
                if currency_idx + 1 < len(parts):
                    try:
                        candidate = parts[currency_idx + 1].replace(",", "")
                        float(candidate)
                        if rate and len(rate) < 3:  # likely qty
                            qty = rate
                            rate = candidate
                        elif not rate:
                            rate = candidate
                    except:
                        pass
                
                # Description is everything before currency section
                desc_end = currency_idx - 1 if rate and currency_idx > 1 else currency_idx
                description = " ".join(parts[:desc_end]).strip()
                
                item = {
                    "description": description,
                    "quantity": qty or "1",
                    "rate": rate or "",
                    "currency": currency or "",
                    "amount_vnd": amounts[line_idx] if line_idx < len(amounts) else "",
                }
                line_items.append(item)
        
        logger.debug("[extract_line_items_from_table] Extracted %d line item(s)", len(line_items))
        return json.dumps(line_items, ensure_ascii=False)
    
    except Exception as e:
        logger.error("[extract_line_items_from_table] Error parsing line items: %s", e, exc_info=True)
        return json.dumps({"error": f"Error parsing line items: {str(e)}"})


@tool
def ocr_image(image_path: str, lang: str = "eng+vie") -> str:
    """
    OCR an image invoice using Tesseract.
    Supports multiple languages (default: English + Vietnamese).
    
    Args:
        image_path: Path to the image file
        lang: Tesseract language code (default: "eng+vie")
        
    Returns:
        Extracted text as a string
    """
    logger.info("[ocr_image] Running OCR on: %s | lang=%s", image_path, lang)
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang=lang)
        logger.debug("[ocr_image] OCR produced %d chars from: %s", len(text), image_path)
        return text
    except Exception as e:
        logger.error("[ocr_image] OCR failed on %s: %s", image_path, e, exc_info=True)
        return json.dumps({"error": f"Error during OCR: {str(e)}"})


@tool
def extract_metadata(metadata_path: str) -> str:
    """
    Extract metadata from JSON or XML file.
    
    Args:
        metadata_path: Path to metadata file (.json or .xml)
        
    Returns:
        Metadata as JSON string
    """
    logger.info("[extract_metadata] Extracting metadata from: %s", metadata_path)
    try:
        ext = Path(metadata_path).suffix.lower()  # includes the dot e.g. ".json"
        
        if ext == ".json":
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.debug("[extract_metadata] Loaded JSON metadata with %d keys from: %s", len(data), metadata_path)
            return json.dumps(data, ensure_ascii=False)
        
        elif ext == ".xml":
            with open(metadata_path, "r", encoding="utf-8") as f:
                content = f.read()
            logger.debug("[extract_metadata] Loaded XML metadata (%d chars) from: %s", len(content), metadata_path)
            return content
        
        else:
            logger.warning("[extract_metadata] Unsupported metadata file type '%s': %s", ext, metadata_path)
            return json.dumps({"error": f"Unsupported metadata file type: {ext}"})
    
    except Exception as e:
        logger.error("[extract_metadata] Failed for %s: %s", metadata_path, e, exc_info=True)
        return json.dumps({"error": f"Error extracting metadata: {str(e)}"})
    

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _is_error(content: str) -> bool:
    try:
        parsed = json.loads(content)
        return isinstance(parsed, dict) and "error" in parsed
    except (json.JSONDecodeError, TypeError):
        return False


def _error_msg(content: str) -> str:
    try:
        return json.loads(content).get("error", content)
    except (json.JSONDecodeError, TypeError):
        return content


def _last_tool_messages(s: JobState) -> List[ToolMessage]:
    """Return only the ToolMessages from the last tool call batch."""
    msgs = []
    for msg in reversed(s["messages"]):
        if isinstance(msg, AIMessage):
            break
        if isinstance(msg, ToolMessage):
            msgs.append(msg)
    return msgs


# ---------------------------------------------------------------------------
# Module-level LLM + tools (created once)
# ---------------------------------------------------------------------------

_llm = ChatOpenAI(
    model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0,
)
_ext_tools = [extract_pdf_text, extract_pdf_tables, extract_line_items_from_table, ocr_image, extract_metadata]
_llm_with_tools = _llm.bind_tools(_ext_tools)


# ---------------------------------------------------------------------------
# Module-level graph nodes
# ---------------------------------------------------------------------------

def _llm_node(s: JobState) -> Dict:
    response = _llm_with_tools.invoke(s["messages"])
    return {"messages": [response]}


def _error_check_node(s: JobState) -> Dict:
    for msg in _last_tool_messages(s):
        if msg.name in ("extract_pdf_text", "ocr_image") and _is_error(msg.content):
            error = f"Invoice extraction failed [{msg.name}]: {_error_msg(msg.content)}"
            logger.error("[extractor_agent][error_check] Critical error detected: %s", error)
            return {"error": [error]}
    return {}  # no critical error — omit key so reducer is not triggered


def _route_after_error_check(s: JobState) -> str:
    return "handle_error" if s.get("error") else "update_state"


def _handle_error_node(s: JobState) -> Dict:
    logger.error("[extractor_agent][handle_error] Job failed: %s", s['error'])
    return {}  # error already accumulated by _error_check_node


def _update_state_node(s: JobState) -> Dict:
    updates: Dict[str, Any] = {}
    new_warnings: List[Dict[str, Any]] = []

    for msg in _last_tool_messages(s):
        if msg.name in ("extract_pdf_text", "ocr_image"):
            updates["raw_invoice_text"] = msg.content
            updates["invoice_extract_method"] = "pdf_text" if msg.name == "extract_pdf_text" else "image_ocr"
            updates["extraction_confidence"] = 0.9 if msg.name == "extract_pdf_text" else 0.7

        elif msg.name == "extract_pdf_tables":
            if _is_error(msg.content):
                new_warnings.append({"agent": "extractor_agent", "tool": msg.name, "error": _error_msg(msg.content)})
                updates["tables"] = []
            else:
                try:
                    updates["tables"] = json.loads(msg.content)
                except (json.JSONDecodeError, TypeError):
                    updates["tables"] = []

        elif msg.name == "extract_line_items_from_table":
            if _is_error(msg.content):
                new_warnings.append({"agent": "extractor_agent", "tool": msg.name, "error": _error_msg(msg.content)})
                updates["line_items"] = []
            else:
                try:
                    updates["line_items"] = json.loads(msg.content)
                except (json.JSONDecodeError, TypeError):
                    updates["line_items"] = []

        elif msg.name == "extract_metadata":
            if _is_error(msg.content):
                new_warnings.append({"agent": "extractor_agent", "tool": msg.name, "error": _error_msg(msg.content)})
            else:
                try:
                    updates["metadata"] = json.loads(msg.content)
                except (json.JSONDecodeError, TypeError):
                    updates["metadata"] = msg.content

    if new_warnings:
        for w in new_warnings:
            logger.warning("[extractor_agent][update_state] Tool warning — tool=%s: %s", w.get('tool'), w.get('error'))
        updates["warnings"] = new_warnings  # reducer appends these to existing warnings

    logger.debug("[extractor_agent][update_state] Updated fields: %s",
                 {k: str(v)[:200] for k, v in updates.items()})
    return updates


# ---------------------------------------------------------------------------
# Build and compile once at module load — avoids expensive recompilation per request
# ---------------------------------------------------------------------------

_ext_tool_node = ToolNode(_ext_tools)

_ext_graph = StateGraph(JobState)
_ext_graph.add_node("llm",          _llm_node)
_ext_graph.add_node("tools",        _ext_tool_node)
_ext_graph.add_node("error_check",  _error_check_node)
_ext_graph.add_node("update_state", _update_state_node)
_ext_graph.add_node("handle_error", _handle_error_node)

_ext_graph.add_edge(START, "llm")
_ext_graph.add_conditional_edges("llm", tools_condition)           # → "tools" or END
_ext_graph.add_edge("tools", "error_check")                        # always check for errors first
_ext_graph.add_conditional_edges("error_check", _route_after_error_check)  # → "update_state" or "handle_error"
_ext_graph.add_edge("update_state", "llm")                         # loop back
_ext_graph.add_edge("handle_error", END)                           # terminate gracefully

_compiled_extractor = _ext_graph.compile()


def extractor_agent_with_tools(state: JobState) -> Dict[str, Any]:
    """
    Extractor agent built with StateGraph using JobState directly.

    Graph flow:
    START → llm → tools_condition → tools → error_check → update_state → llm (loop)
                       ↓ no tool calls            ↓ critical error
                      END                      handle_error → END
    """
    try:
        logger.debug("[extractor_agent] Full state received: %s", state)
        events = []
        events.append(SystemMessage(content=f"[extractor_agent] Started for job_id={state.get('job_id', 'unknown')}"))
        logger.info("[extractor_agent] Starting for job_id=%s", state.get('job_id', 'unknown'))

        invoice_path = state["invoice_path"]
        metadata_path = state.get("metadata_path")

        prompt = f"Extract all data from the invoice at: {invoice_path}"
        if metadata_path:
            prompt += f"\nAlso extract metadata from: {metadata_path}"

        result = _compiled_extractor.invoke({
            **state,
            "messages": [
                SystemMessage(
                    "You are an invoice extraction agent. "
                    "Given an invoice file path, use the appropriate tools to extract text and tables. "
                    "If it's a PDF, extract both text and tables. If it's an image, use OCR. "
                    "After extracting tables, also extract line items from them."
                ),
                HumanMessage(prompt),
            ]
        })
        events.append(SystemMessage(content=f"[extractor_agent] Completed Extraction  for job_id={state.get('job_id', 'unknown')}"))
        logger.info("[extractor_agent] Extraction completed for job_id=%s", state.get('job_id', 'unknown'))

        logger.warning("STATE IN EXTRACTOR AGENT : %s", result)
        return {
            "events": events,
            "raw_invoice_text": result.get("raw_invoice_text"),
            "tables": result.get("tables", []),
            "line_items": result.get("line_items", []),
            "metadata": result.get("metadata"),
            "invoice_extract_method": result.get("invoice_extract_method"),
            "extraction_confidence": result.get("extraction_confidence"),
            "warnings": result.get("warnings") or [],
        }

    except Exception as e:
        logger.error("[extractor_agent] Fatal error for job_id=%s: %s", state.get('job_id', 'unknown'), e, exc_info=True)
        return {
            "events": [SystemMessage(content=f"[extractor_agent] Failed for job_id={state.get('job_id', 'unknown')}: {e}")],
            "error": [f"[extractor_agent] Error occurred: {e}"]
        }





# if __name__ == "__main__":
#     state = {
#         "job_id": 1234,
#         "invoice_path": r"data\incoming\Actual_invoice.pdf",
#         "metadata_path": r"data\incoming\INV_EN_006_malformed.meta.json",
#     }
#     result = extractor_agent_with_tools(state)
#     print(result)
    