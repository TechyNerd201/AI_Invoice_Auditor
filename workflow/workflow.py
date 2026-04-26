from state import JobState
from typing import Dict, Any
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage
from pathlib import Path    
from graph.agents.translate_agent import translate_agent_with_tools
from graph.agents.extractor_agent import extractor_agent_with_tools
from graph.agents.ingestion_agent import ingestion_agent
from graph.agents.report_agent import report_agent
from graph.agents.validation_agent import validation_agent_with_tools
from log_utils.logger import get_logger

logger = get_logger(__name__)


# Build and compile once at module load — avoids expensive recompilation per request
_graph = StateGraph(JobState)
_graph.add_node("extractor", extractor_agent_with_tools)
_graph.add_node("translate", translate_agent_with_tools)
_graph.add_node("ingest", ingestion_agent)
_graph.add_node("validate", validation_agent_with_tools)
_graph.add_node("report", report_agent)

_graph.add_edge(START, "extractor")
_graph.add_edge("extractor", "translate")
_graph.add_edge("translate", "validate")
_graph.add_edge("validate", "report")
_graph.add_edge("report", "ingest")

_compiled_workflow = _graph.compile()


def workflow(state: JobState) -> Dict[str, Any]:
    logger.info("[workflow] Starting for job_id=%s", state.get('job_id', 'unknown'))
    result = _compiled_workflow.invoke(
        state,
        config={"recursion_limit": 100},
    )
    logger.info("[workflow] Completed for job_id=%s", state.get('job_id', 'unknown'))
    return result


