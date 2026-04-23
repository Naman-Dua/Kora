import copy
import re

from actions import execute_action_plan, plan_action_command
from screen_analysis import analyze_screen, is_screen_request
from search_engine import extract_search_query, format_search_response, is_search_request, search_online
from skills import describe_skills, is_skill_list_request, parse_skill_command
from storage import load_automation, load_automations, mark_automation_ran, save_automation
from task_memory import handle_task_memory_command

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


class OperatorState:
    def __init__(self):
        self.pending_approval = None
        self.last_workflow = None


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


def _execute_workflow(workflow, state, settings):
    workflow_type = workflow["type"]
    payload = workflow["payload"]

    if workflow_type == "action_plan":
        _set_last_workflow(state, workflow)
        return execute_action_plan(payload)

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
        reply = _execute_workflow(workflow, state, settings)
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


def handle_operator_command(query, settings, state):
    approval_reply = _handle_approval(query, state, settings)
    if approval_reply:
        return approval_reply

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

    if is_skill_list_request(query):
        return {"action": "list_skills", "reply": describe_skills()}

    if is_search_request(query):
        workflow = {"type": "search", "payload": {"query": extract_search_query(query)}}
        reply = _execute_workflow(workflow, state, settings)
        return {"action": "search", "reply": reply}

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
            "reply": _execute_workflow(workflow, state, settings),
        }

    return None
