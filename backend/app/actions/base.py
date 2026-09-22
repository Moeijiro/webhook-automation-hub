"""The adapter contract every action implements.

Adding an integration means adding one module here plus one line in the
registry: a Pydantic config model, the list of fields that are secret, and a
``run`` method returning an :class:`ActionOutcome`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import BaseModel


@dataclass(slots=True)
class ActionContext:
    """Everything an action is allowed to know about the run."""

    payload: Any
    workflow_name: str
    execution_id: int


@dataclass(slots=True)
class ActionOutcome:
    """The result of one attempt."""

    ok: bool
    detail: str = ""
    status_code: int | None = None
    response_excerpt: str | None = None
    # Whether a retry could plausibly succeed (timeouts, 5xx, 429 -- not 400).
    retryable: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def as_result(self) -> dict[str, Any]:
        """Shape stored in ``Execution.action_result`` and shown in the UI."""
        data: dict[str, Any] = {"ok": self.ok, "detail": self.detail}
        if self.status_code is not None:
            data["status_code"] = self.status_code
        if self.response_excerpt:
            data["response"] = self.response_excerpt
        data.update(self.extra)
        return data


class Action(ABC):
    """Base class for action adapters."""

    type: ClassVar[str]
    label: ClassVar[str]
    description: ClassVar[str] = ""
    config_model: ClassVar[type[BaseModel]]
    #: Config keys encrypted at rest and never returned by the API.
    secret_fields: ClassVar[tuple[str, ...]] = ()

    @abstractmethod
    async def run(self, config: BaseModel, context: ActionContext) -> ActionOutcome:
        """Perform the action once. Retries are the engine's business."""

    @staticmethod
    def excerpt(text: str, limit: int = 300) -> str:
        """Responses go into the log; keep them short and one line."""
        collapsed = " ".join(text.split())
        return collapsed[:limit] + ("…" if len(collapsed) > limit else "")
