from __future__ import annotations
from typing import List, Dict, Any
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from services.aws_translate_service import LambdaTranslationClient
import langdetect
from state import JobState
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage
from log_utils.logger import get_logger


logger = get_logger(__name__)

# Initialize Lambda client
lambda_client = LambdaTranslationClient(
    function_name="InvoiceTranslatorFunction",
    region="ap-south-1"
)


def pick_next_field_node(state: JobState) -> str:
   queue = state.get("fields_queue", [])
   current = queue.pop(0)
   logger.debug("[translate_agent][pick_next_field] Processing field '%s' | %d field(s) remaining", current, len(queue))
   return {"current_field": current, "fields_queue": queue}

def detect_language_node(state : JobState):
    try:
        field = state['current_field']
        text = state.get(field)

        # Guard: empty values → default to English
        if not text or (isinstance(text, str) and not text.strip()):
            logger.debug("[translate_agent][detect_language] Field '%s' is empty — defaulting to 'en'", field)
            return {"detected_language": "en"}

        # For list/dict fields, serialize to string for language detection
        if isinstance(text, (list, dict)):
            text_for_detection = json.dumps(text, ensure_ascii=False)
        else:
            text_for_detection = text

        detected_language = langdetect.detect(text_for_detection)
        logger.debug("[translate_agent][detect_language] Field '%s' detected as '%s'", field, detected_language)
        return {"detected_language": detected_language}
    
    except langdetect.lang_detect_exception.LangDetectException:
        logger.warning("[translate_agent][detect_language] LangDetect failed for field '%s' — defaulting to 'en'", state.get('current_field'))
        return {"detected_language": "en"}
    
    except Exception as e:
        logger.error("[translate_agent][detect_language] Unexpected error for field '%s': %s", state.get('current_field'), e, exc_info=True)
        return {"detected_language": "en"}

def route_language_node(state: JobState) -> str:
    detected_language = state.get("detected_language")
    return "english" if detected_language == "en" else "not_english"

def translate_node(state: JobState) -> Dict:
    try:
        field = state.get('current_field')
        text = state.get(field)
        detected_language = state.get("detected_language")
        logger.info("[translate_agent][translate] Translating field '%s' (lang='%s', type=%s)", field, detected_language, type(text).__name__)

        if isinstance(text, dict):
            # Mode 4 — metadata dict: translate each string value individually
            translated = lambda_client.translate_metadata(text, detected_language)
            result = json.dumps(translated, ensure_ascii=False)
        elif isinstance(text, list):
            # Mode 3 — line items: translate all string values per item
            translated = lambda_client.translate_line_items(text, detected_language)
            result = json.dumps(translated, ensure_ascii=False)
        else:
            # Mode 1 — plain text
            result = lambda_client.translate_text(text, detected_language)

        logger.debug("[translate_agent][translate] Success for field '%s'", field)
        return {"last_translation": {"success": True, "result": result, "error": None}}
    except Exception as e:
        logger.error("[translate_agent][translate] Failed for field '%s': %s", state.get('current_field'), e, exc_info=True)
        return {"last_translation": {"success": False, "error": str(e), "result": None}}

def check_errors_node(state: JobState):
    try:
        return "success" if state.get("last_translation", {}).get("success", False) else "error"

    except Exception as e:
        return "error"


def log_warning_node(state: JobState) -> Dict:
    error_info = state.get('last_translation', {}).get("error", "Unknown error")
    current_field = state.get('current_field')
    logger.warning("[translate_agent][log_warning] Gave up translating field '%s' after max retries: %s", current_field, error_info)
    return {"warnings": [{"agent": "translate_agent", "field": current_field, "error": error_info}]}
    

def update_field_node(state: JobState) -> Dict:
    current_field = state.get('current_field')
    translated_text = state.get('last_translation', {}).get('result', '')
    # restore list/dict fields from JSON string if original was structured
    original = state.get(current_field)
    if isinstance(original, (list, dict)):
        try:
            translated_text = json.loads(translated_text)
        except Exception as e:
            logger.warning(
                "[translate_agent][update_field] Could not parse translated '%s' back to %s "
                "— keeping original untranslated value. JSON error: %s",
                current_field, type(original).__name__, e,
            )
            translated_text = original  # keep original type, never return a broken string
    logger.info("[translate_agent][update_field] Updated field '%s' with translated content", current_field)
    return {current_field: translated_text}

def check_remaining_node(state: JobState):
    return "has_more" if state.get('fields_queue') else "done"


def check_retry_node(state: JobState) -> str:
    """Conditional edge — retry if under limit, else give up."""
    retries = state.get("retry_count", 0)
    return "retry" if retries < 3 else "give_up"


def increment_retry_node(state: JobState) -> Dict:
    """Bumps retry counter by 1 then loops back to translate."""
    count = state.get("retry_count", 0) + 1
    logger.warning("[translate_agent][increment_retry] Retry %d/3 for field '%s'", count, state.get('current_field'))
    return {"retry_count": count}


def reset_retry_node(state: JobState) -> Dict:
    """Resets retry counter after a successful translation."""
    return {"retry_count": 0}


def _noop_node(s: JobState) -> dict:
    return {}


# Build and compile once at module load — avoids expensive recompilation per request
_translate_graph = StateGraph(JobState)
_translate_graph.add_node("pick_next_field",  pick_next_field_node)
_translate_graph.add_node("detect_language",  detect_language_node)
_translate_graph.add_node("translate",        translate_node)
_translate_graph.add_node("reset_retry",      reset_retry_node)
_translate_graph.add_node("increment_retry",  increment_retry_node)
_translate_graph.add_node("update_field",     update_field_node)
_translate_graph.add_node("log_warning",      log_warning_node)
_translate_graph.add_node("check_remaining",  _noop_node)  # passthrough — routing via conditional edge
_translate_graph.add_node("check_retry",      _noop_node)  # passthrough — routing via conditional edge

_translate_graph.add_edge(START, "pick_next_field")
_translate_graph.add_edge("pick_next_field", "detect_language")

_translate_graph.add_conditional_edges("detect_language", route_language_node, {
    "english":     "check_remaining",
    "not_english": "translate",
})

_translate_graph.add_conditional_edges("translate", check_errors_node, {
    "success": "reset_retry",
    "error":   "check_retry",
})

_translate_graph.add_conditional_edges("check_retry", check_retry_node, {
    "retry":   "increment_retry",
    "give_up": "log_warning",
})

_translate_graph.add_edge("increment_retry", "translate")       # retry loop
_translate_graph.add_edge("reset_retry",     "update_field")
_translate_graph.add_edge("update_field",    "check_remaining")
_translate_graph.add_edge("log_warning",     "check_remaining")

_translate_graph.add_conditional_edges("check_remaining", check_remaining_node, {
    "has_more": "pick_next_field",
    "done":     END,
})

_compiled_translate_agent = _translate_graph.compile()


# ---------------------------------------------------------------------------
# Main agent function
# ---------------------------------------------------------------------------

def translate_agent_with_tools(state: JobState) -> Dict[str, Any]:
    """
    Deterministic translate agent built with StateGraph — no LLM required.

    Graph flow:
    START → pick_next_field → detect_language
              ↓ route_language
         english     → check_remaining
         not_english → translate
              ↓ check_errors
         success → reset_retry → update_field → check_remaining
         error   → check_retry
              ↓
         retry    → increment_retry → translate  (retry loop)
         give_up  → log_warning    → check_remaining
              ↓ check_remaining
         has_more → pick_next_field  (field loop)
         done     → END
    """
    try:
        logger.info("[translate_agent] Starting for job_id=%s", state.get('job_id', 'unknown'))
        events=[]
        events.append(SystemMessage(content=f"[translate_agent] Started for job_id={state.get('job_id', 'unknown')}"))

        fields_queue = [
            f for f in ["raw_invoice_text", "line_items", "tables", "metadata"]
            if state.get(f)
        ]

        result = _compiled_translate_agent.invoke({
            **state,
            "fields_queue":     fields_queue,
            "current_field":    None,
            "detected_language": None,
            "last_translation": None,
            "retry_count":      0,
        })
        events.append(SystemMessage(content=f"[translate_agent] Completed for job_id={state.get('job_id', 'unknown')}"))
        logger.info("[translate_agent] Completed for job_id=%s", state.get('job_id', 'unknown'))

        result = {
            "events": events,
            "raw_invoice_text":  result.get("raw_invoice_text",  state.get("raw_invoice_text")),
            "line_items":        result.get("line_items",        state.get("line_items", [])),
            "tables":            result.get("tables",            state.get("tables", [])),
            "metadata":          result.get("metadata",          state.get("metadata")),
            "warnings":          result.get("warnings", []),
        }
        logger.warning("STATE IN TRANSLATE AGENT : %s", result)
        return result
    
    except Exception as e:
        logger.error("[translate_agent] Fatal error for job_id=%s: %s", state.get('job_id', 'unknown'), e, exc_info=True)
        return {
            "events": [SystemMessage(content=f"[translate_agent] Failed: {str(e)}")],
            "error": [f"[translate_agent]: Agent failed: {e}"],
            }
        



# if __name__ == "__main__":
#     state = {
#         "job_id": "DEMO-001",
#         "invoice_path": r"data\incoming\INV_DE_004.pdf",
#         "raw_invoice_text": (
#             "Rechnungsnummer: INV-1002\nDatum: 20. April 2025\n"
#             "Beschreibung: Containerdichtungen\nMenge: 200 Einheiten\n"
#             "Einzelpreis: 1,25 $\nZwischensumme: 250,00 $\n"
#             "Steuer (10 %): 25,00 $\nGesamtbetrag: 275,00 $"
#         ),
#         "tables": [],
#         "line_items": [],
#         "metadata": None,
#         "warnings": [],
#     }
#     result = translate_agent_with_tools(state)
#     print(result)








    

   




