
import operator
from typing import Optional, List, Dict, Any, Annotated
from pydantic import BaseModel, Field
from typing import TypedDict, NotRequired
from langgraph.graph.message import add_messages

class JobState(TypedDict):
    job_id: str
    invoice_path: str
    metadata_path: NotRequired[Optional[str]]
    messages: NotRequired[Annotated[List, add_messages]]  # needed for LangGraph tool loop
    events: NotRequired[Annotated[List, add_messages]]  # needed for LangGraph tool loop
    warnings: NotRequired[Annotated[List, operator.add]]
    error: NotRequired[Annotated[List[str], operator.add]]  # accumulates errors from all agents
    raw_invoice_text: NotRequired[Optional[str]]
    tables: NotRequired[List[Dict[str, Any]]]
    invoice_extract_method: NotRequired[Optional[str]]
    extraction_confidence: NotRequired[Optional[float]]
    metadata: NotRequired[Any]
    line_items: NotRequired[List[Dict[str, Any]]]
    fields_queue:       NotRequired[List[str]]
    current_field:      NotRequired[Optional[str]]
    detected_language:  NotRequired[Optional[str]]
    last_translation:   NotRequired[Optional[Dict[str, Any]]]
    retry_count:        NotRequired[int]
    # validator agent fields
    validation_findings: NotRequired[Annotated[List[Dict[str, Any]], operator.add]]
    validation_passed:   NotRequired[Optional[bool]]
    report : NotRequired[Optional[str]]
    chunk_count : NotRequired[Optional[int]]