from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel

from core.domain import Action


class Tool(BaseModel):
    name: str
    description: str
    phase: str
    mitre_id: str
    platform: str
    preconditions: List[str]
    postconditions: List[str]
    implementation: Optional[str] = None
    safe_simulation: bool


@dataclass
class ToolRegistry:
    tools: Dict[str, Tool]

    @classmethod
    def load(cls, root: Path) -> "ToolRegistry":
        tools: Dict[str, Tool] = {}
        for path in root.rglob("*.yaml"):
            data = _load_yaml(path)
            tool = Tool.model_validate(data)
            tools[tool.name] = tool
        return cls(tools=tools)

    def get(self, name: str) -> Tool | None:
        return self.tools.get(name)

    def filter_actions(self, actions: List[Action], flags: List[str]) -> List[Action]:
        active_flags = set(flags)
        eligible: List[Action] = []
        for action in actions:
            if not action.tool:
                eligible.append(action)
                continue
            tool = self.get(action.tool)
            if tool is None:
                continue
            if all(pre in active_flags for pre in tool.preconditions):
                eligible.append(action)
        return eligible


def _load_yaml(path: Path) -> Dict:
    try:
        import yaml  # type: ignore
        return yaml.safe_load(path.read_text())
    except ImportError:
        return _parse_simple_yaml(path.read_text())


def _parse_simple_yaml(content: str) -> Dict:
    data: Dict[str, object] = {}
    current_key = None
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            if current_key is None:
                continue
            data.setdefault(current_key, [])
            if isinstance(data[current_key], list):
                data[current_key].append(line[2:].strip())
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            if value == "":
                data[key] = []
            else:
                if value.startswith("[") and value.endswith("]"):
                    inner = value[1:-1].strip()
                    if not inner:
                        data[key] = []
                    else:
                        data[key] = [item.strip() for item in inner.split(",")]
                    continue
                if value.lower() == "true":
                    data[key] = True
                elif value.lower() == "false":
                    data[key] = False
                else:
                    data[key] = value
    return data
