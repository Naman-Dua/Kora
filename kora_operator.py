import copy
import re

from actions import execute_action_plan, plan_action_command
from chat_export import handle_export_command, is_export_request
from clipboard_ops import handle_clipboard_command, is_clipboard_request
from code_runner import handle_code_command, is_code_request
from dictionary_lookup import (
    handle_dictionary_command,
    handle_translate_command,
    is_dictionary_request,
    is_translate_request,
)
from daily_briefing import handle_briefing_command, is_briefing_request
from file_ops import handle_file_command, is_file_request
from focus_mode import handle_focus_command, is_focus_request
from ingest_docs import handle_ingest_command, is_ingest_request
from media_control import handle_media_command, is_media_request
from network_tools import handle_network_command, is_network_request
from news_feed import handle_news_command, is_news_request
from ocr import handle_ocr_command, is_ocr_request
from personas import handle_persona_command, is_persona_request
from plugin_loader import handle_plugin_command, is_plugin_request, try_plugin_handle
from process_mgmt import handle_process_command, is_process_request
from screen_analysis import analyze_screen, is_screen_request
from search_engine import extract_search_query, format_search_response, is_search_request, search_online
from skills import describe_skills, is_skill_list_request, parse_skill_command
from storage import load_automation, load_automations, mark_automation_ran, save_automation
from system_info import handle_system_command, is_system_request
from timer_tools import handle_stopwatch_command, is_stopwatch_request
from task_memory import handle_task_memory_command
from themes import handle_theme_command, is_theme_request
from url_summarizer import handle_url_summarize_command, is_url_summarize_request
from weather import handle_weather_command, is_weather_request
from web_monitor import handle_web_monitor_command, is_web_monitor_request
from window_mgmt import handle_window_command, is_window_request
from plugin_architect import handle_architect_command, is_architect_request
from mission_control import MissionControl
from self_healing import handle_self_healing

APPROVE_PATTERN = re.compile(r"^(?:approve|confirm|yes|do it|go ahead|proceed)$", re.IGNORECASE)
REJECT_PATTERN = re.compile(r"^(?:reject|cancel that|no|never mind|dont do that|don't do that)$", re.IGNORECASE)
SAVE_AUTOMATION_PATTERN = re.compile(
    r"^(?:save|store)\s+(?:this|last)\s+(?:workflow|automation)\s+as\s+(.+)$",
    re.IGNORECASE,
)
RUN_AUTOMATION_PATTERN = re.compile(
    r"^(?:run|start|replay)\s+(?:automation\s+)?(.+)$",
    re.IGNORECASE,
)
LIST_AUTOMATIONS_PATTERN = re.compile(
    r"^(?:list|show|what are)\s+(?:my\s+)?automations$",
    re.IGNORECASE,
)
STATUS_PATTERN = re.compile(r"^(?:operator status|status report)$", re.IGNORECASE)
REPEAT_PATTERN = re.compile(r"^(?:do that again|repeat that|again|run that again|same thing)$", re.IGNORECASE)


class OperatorState:
    def __init__(self):
        self.pending_approval = None
        self.last_workflow = None
        self.last_action = None
        self.last_query = None
        self.mission_control = MissionControl()


def _should_require_confirmation(plan, settings):
    return bool(
        plan.get("requires_confirmation")
        or (
            settings.get("require_action_confirmation", True)
            and len(plan.get("requests", [])) > 1
        )
    )


def _set_last_workflow(state, workflow):
    state.last_workflow = copy.deepcopy(workflow)


def _execute_workflow(workflow, state, settings, query=""):
    workflow_type = workflow["type"]
    payload = workflow["payload"]

    if workflow_type == "action_plan":
        _set_last_workflow(state, workflow)
        res = execute_action_plan(payload)
        reply = res["reply"]
        if not res["success"] and res["failures"]:
            healing_reply = handle_self_healing(res["failures"], query, type('obj', (object,), {'model_name': settings.get('model_name', 'llama3.1:8b')}))
            reply = f"{reply} {healing_reply}"
        return reply

    if workflow_type == "search":
        _set_last_workflow(state, workflow)
        return format_search_response(search_online(payload["query"]))

    if workflow_type == "screen":
        _set_last_workflow(state, workflow)
        return analyze_screen(payload["query"])

    if workflow_type == "task_memory":
        _set_last_workflow(state, workflow)
        return payload["reply"]

    if workflow_type == "skill":
        _set_last_workflow(state, workflow)
        return payload["reply"]

    return "I do not know how to run that workflow yet."


def _queue_workflow_for_approval(workflow, state):
    state.pending_approval = copy.deepcopy(workflow)


def _process_operator_result(result, query, settings):
    """
    Checks if a result failed and tries to attach a self-healing suggestion.
    """
    if not result or not isinstance(result, dict):
        return result
        
    if result.get("success") is False:
        failure_info = {
            "request": {"kind": result.get("action", "unknown"), "action": "execute", "label": "command"},
            "error": result.get("error", "Unknown error")
        }
        healing_reply = handle_self_healing([failure_info], query, type('obj', (object,), {'model_name': settings.get('model_name', 'llama3.1:8b')}))
        result["reply"] = f"{result['reply']} {healing_reply}"
        
    return result


def _automation_summary(items):
    if not items:
        return "There are no saved automations yet."
    return "Saved automations: " + "; ".join(item["name"] for item in items[:8]) + "."


def _handle_approval(query, state, settings):
    normalized = " ".join(str(query).strip().split())
    if not state.pending_approval:
        return None

    if APPROVE_PATTERN.match(normalized):
        workflow = state.pending_approval
        state.pending_approval = None
        reply = _execute_workflow(workflow, state, settings, query=state.last_query or query)
        if workflow.get("automation_name"):
            mark_automation_ran(workflow["automation_name"])
        return {"action": "approved", "reply": reply}

    if REJECT_PATTERN.match(normalized):
        state.pending_approval = None
        return {"action": "rejected", "reply": "Okay, I canceled that action."}

    return None


def _handle_automation_commands(query, state):
    normalized = " ".join(str(query).strip().split())

    if LIST_AUTOMATIONS_PATTERN.match(normalized):
        return {"action": "list_automations", "reply": _automation_summary(load_automations())}

    save_match = SAVE_AUTOMATION_PATTERN.match(normalized)
    if save_match:
        if not state.last_workflow:
            return {
                "action": "save_automation",
                "reply": "Run a workflow first, then I can save it as an automation.",
            }
        name = save_match.group(1).strip(" .")
        if not name:
            return None
        save_automation(name, state.last_workflow["type"], state.last_workflow["payload"])
        return {
            "action": "save_automation",
            "reply": f"Saved that workflow as {name}.",
        }

    run_match = RUN_AUTOMATION_PATTERN.match(normalized)
    if run_match and "automation" in normalized:
        name = run_match.group(1).strip(" .")
        automation = load_automation(name)
        if not automation:
            return {"action": "run_automation", "reply": f"I could not find an automation named {name}."}

        workflow = {
            "type": automation["automation_type"],
            "payload": automation["payload"],
            "automation_name": automation["name"],
        }
        if workflow["type"] == "action_plan" and _should_require_confirmation(
            workflow["payload"], {"require_action_confirmation": True}
        ):
            _queue_workflow_for_approval(workflow, state)
            return {
                "action": "run_automation",
                "reply": f"{automation['name']} is ready. Approve to run: {automation['payload']['summary']}.",
            }

        reply = _execute_workflow(workflow, state, {"require_action_confirmation": True})
        mark_automation_ran(automation["name"])
        return {"action": "run_automation", "reply": reply}

    return None


def _handle_contextual_repeat(query, state, settings):
    normalized = " ".join(str(query).strip().split())
    if not REPEAT_PATTERN.match(normalized):
        return None
    if not state.last_workflow:
        return {"action": "repeat", "reply": "There is nothing to repeat yet."}
    reply = _execute_workflow(state.last_workflow, state, settings)
    return {"action": "repeat", "reply": reply}


def handle_operator_command(query, settings, state, reminder_manager=None):
    state.last_query = query
    approval_reply = _handle_approval(query, state, settings)
    if approval_reply:
        return approval_reply

    # Contextual follow-ups
    repeat_reply = _handle_contextual_repeat(query, state, settings)
    if repeat_reply:
        return repeat_reply

    automation_reply = _handle_automation_commands(query, state)
    if automation_reply:
        return automation_reply

    normalized = " ".join(str(query).strip().split())
    if STATUS_PATTERN.match(normalized):
        pending = state.pending_approval["type"] if state.pending_approval else "none"
        return {"action": "operator_status", "reply": f"Operator is ready. Pending approval: {pending}."}

    task_reply = handle_task_memory_command(query)
    if task_reply:
        workflow = {"type": "task_memory", "payload": task_reply}
        _set_last_workflow(state, workflow)
        return {"action": task_reply["action"], "reply": task_reply["reply"]}

    # Personas
    if is_persona_request(query):
        result = handle_persona_command(query)
        if result:
            return result

    # Themes
    if is_theme_request(query):
        result = handle_theme_command(query)
        if result:
            return result

    # Plugin Architect
    if is_architect_request(query):
        result = handle_architect_command(query)
        if result:
            return result

    # Mission Control
    if state.mission_control.is_mission_request(query):
        result = state.mission_control.execute_mission(query)
        if result:
            return result

    # Plugins
    if is_plugin_request(query):
        result = handle_plugin_command(query)
        if result:
            return result

    plugin_result = try_plugin_handle(query)
    if plugin_result:
        return plugin_result

    if is_skill_list_request(query):
        return {"action": "list_skills", "reply": describe_skills()}

    # Clipboard
    if is_clipboard_request(query):
        result = _process_operator_result(handle_clipboard_command(query), query, settings)
        if result:
            return result

    # File operations
    if is_file_request(query):
        result = _process_operator_result(handle_file_command(query), query, settings)
        if result:
            return result

    # Document ingestion (RAG)
    if is_ingest_request(query):
        result = handle_ingest_command(query)
        if result:
            return result

    # Daily Briefing
    if is_briefing_request(query) and reminder_manager:
        result = handle_briefing_command(query, reminder_manager)
        if result:
            return result

    # Focus Mode
    if is_focus_request(query):
        result = handle_focus_command(query)
        if result:
            return result

    # Media control
    if is_media_request(query):
        result = handle_media_command(query)
        if result:
            return result

    # Window management
    if is_window_request(query):
        result = handle_window_command(query)
        if result:
            return result

    # Weather
    if is_weather_request(query):
        result = handle_weather_command(query)
        if result:
            return result

    # Dictionary
    if is_dictionary_request(query):
        result = handle_dictionary_command(query)
        if result:
            return result

    # Translation
    if is_translate_request(query):
        result = handle_translate_command(query)
        if result:
            return result

    # News
    if is_news_request(query):
        result = handle_news_command(query)
        if result:
            return result

    # URL summarizer
    if is_url_summarize_request(query):
        result = handle_url_summarize_command(query)
        if result:
            return result

    # Chat export
    if is_export_request(query):
        result = handle_export_command(query)
        if result:
            return result

    # Code execution
    if is_code_request(query):
        result = handle_code_command(query)
        if result:
            return result

    # System status
    if is_system_request(query):
        result = handle_system_command(query)
        if result:
            return result

    # Process management
    if is_process_request(query):
        result = _process_operator_result(handle_process_command(query), query, settings)
        if result:
            return result

    # Network tools
    if is_network_request(query):
        result = handle_network_command(query)
        if result:
            return result

    # Stopwatch
    if is_stopwatch_request(query):
        result = handle_stopwatch_command(query)
        if result:
            return result

    # Web monitor
    if is_web_monitor_request(query):
        result = handle_web_monitor_command(query)
        if result:
            return result

    # Search
    if is_search_request(query):
        workflow = {"type": "search", "payload": {"query": extract_search_query(query)}}
        reply = _execute_workflow(workflow, state, settings)
        return {"action": "search", "reply": reply}

    # OCR
    if is_ocr_request(query):
        result = handle_ocr_command(query)
        if result:
            return result

    # Screen analysis
    if is_screen_request(query):
        workflow = {"type": "screen", "payload": {"query": query}}
        reply = _execute_workflow(workflow, state, settings)
        return {"action": "screen", "reply": reply}

    skill_command = parse_skill_command(query)
    if skill_command:
        skill_name = skill_command["skill"]
        payload = skill_command["payload"]
        if skill_name == "research":
            workflow = {"type": "search", "payload": {"query": payload}}
            reply = _execute_workflow(workflow, state, settings)
            return {"action": "skill_research", "reply": reply}
        if skill_name == "vision":
            workflow = {"type": "screen", "payload": {"query": payload}}
            reply = _execute_workflow(workflow, state, settings)
            return {"action": "skill_vision", "reply": reply}
        if skill_name == "focus":
            task_reply = handle_task_memory_command(f"focus on {payload}")
            if task_reply:
                workflow = {"type": "task_memory", "payload": task_reply}
                _set_last_workflow(state, workflow)
                return {"action": "skill_focus", "reply": task_reply["reply"]}
        if skill_name == "automation":
            return {
                "action": "skill_automation",
                "reply": "Use 'save this workflow as ...' after a workflow runs, or 'list automations'.",
            }

    plan = plan_action_command(query)
    if plan:
        workflow = {"type": "action_plan", "payload": plan}
        _set_last_workflow(state, workflow)
        if _should_require_confirmation(plan, settings):
            _queue_workflow_for_approval(workflow, state)
            return {
                "action": "action_plan",
                "reply": f"I am ready to {plan['summary']}. Approve to continue.",
            }
        return {
            "action": "action_plan",
            "reply": _execute_workflow(workflow, state, settings, query=query),
        }

    return None
