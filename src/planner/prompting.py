from __future__ import annotations

import json
from typing import List

from core.domain import Action, ActionType

SYSTEM_PROMPT = """\
You are an autonomous red team agent reasoning about attack paths.

You will receive:
- The current objective
- The current attack graph state
- A list of available actions with their parameters

Your task: choose the single best next action to advance toward the objective.

Important:
- never select a role present in failed_assume_roles
- if multiple roles are assumable, prefer the role that best advances toward the objective
- after a failed pivot, try a different valid branch instead of looping on the same discovery step
- if enumeration is already sufficient and assume_role is available, do not keep choosing enumerate
- if there are progress actions available from an already assumed role, explore that active branch before switching pivots

You MUST respond with valid JSON only. No explanation, no markdown, no preamble.

Response schema:
{
  "action_index": <integer index from available_actions>,
  "reason": "<one sentence explaining why this action advances the objective>"
}

If no action is viable, respond with action_index -1 and explain in reason.
"""


def build_prompt(snapshot, available_actions: List[Action]) -> str:
    actions_repr = [a.model_dump() for a in available_actions]
    candidate_roles = list(getattr(snapshot, "candidate_roles", [])) or list(
        dict.fromkeys(
            action.target
            for action in available_actions
            if action.action_type == ActionType.ASSUME_ROLE and action.target
        )
    )
    enumeration_actions = [
        action
        for action in available_actions
        if action.action_type == ActionType.ENUMERATE
    ]
    assume_actions = [
        action
        for action in available_actions
        if action.action_type == ActionType.ASSUME_ROLE
    ]
    active_assumed_roles = getattr(snapshot, "active_assumed_roles", [])
    active_branch_action_count = getattr(snapshot, "active_branch_action_count", 0)
    enumeration_sufficient = getattr(snapshot, "enumeration_sufficient", False)
    should_commit_to_pivot = getattr(snapshot, "should_commit_to_pivot", False)
    should_explore_current_branch = getattr(snapshot, "should_explore_current_branch", False)
    failed_assume_roles = getattr(snapshot, "failed_assume_roles", [])
    tested_assume_roles = getattr(snapshot, "tested_assume_roles", [])
    planner_guidance = {
        "enumeration_sufficient": enumeration_sufficient,
        "should_commit_to_pivot": should_commit_to_pivot,
        "active_assumed_roles": active_assumed_roles,
        "active_branch_action_count": active_branch_action_count,
        "should_explore_current_branch": should_explore_current_branch,
        "candidate_roles": candidate_roles,
        "failed_assume_roles": failed_assume_roles,
        "tested_assume_roles": tested_assume_roles,
        "candidate_paths": [
            {
                "target": path.target,
                "status": path.status,
                "times_tested": path.times_tested,
                "has_progress_actions": path.has_progress_actions,
                "path_score": path.path_score,
                "observed_resources": path.observed_resources,
                "lookahead_signals": path.lookahead_signals,
            }
            for path in getattr(snapshot, "candidate_paths", [])
        ],
        "guidance": (
            "If enumeration_sufficient is true and assume_role actions are available, "
            "prefer a non-failed assume_role instead of repeating enumerate. "
            "If should_explore_current_branch is true, prefer an action from active_assumed_roles "
            "before opening a new pivot. Never choose a role listed in failed_assume_roles. "
            "If no active branch has progress, backtrack to an untested candidate path before "
            "revisiting tested or failed pivots. When multiple pivots are available, prefer the "
            "candidate path with the highest path_score rather than following presentation order. "
            "Treat observed_resources that closely match the objective target as strong evidence. "
            "Also treat lookahead_signals from actions available in a branch as useful evidence "
            "when ranking pivots before exploring them."
        ),
        "enumerate_action_count": len(enumeration_actions),
        "assume_role_action_count": len(assume_actions),
    }
    return json.dumps(
        {
            "objective": {
                "description": snapshot.objective.description,
                "target": snapshot.objective.target,
            },
            "flags": snapshot.fixture_state.get("flags", []),
            "steps_taken": snapshot.steps_taken,
            "path_memory": {
                "tested_assume_roles": tested_assume_roles,
                "failed_assume_roles": failed_assume_roles,
                "active_assumed_roles": active_assumed_roles,
                "candidate_paths": planner_guidance["candidate_paths"],
            },
            "planner_guidance": planner_guidance,
            "available_actions": [
                {"index": idx, **action} for idx, action in enumerate(actions_repr)
            ],
        },
        indent=2,
    )
