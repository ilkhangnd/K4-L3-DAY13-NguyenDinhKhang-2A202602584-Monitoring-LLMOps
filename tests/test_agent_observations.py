from __future__ import annotations

from contextlib import contextmanager

from app import agent as agent_module


class Observation:
    def __init__(self) -> None:
        self.updates: list[dict] = []

    def update(self, **kwargs) -> None:
        self.updates.append(kwargs)


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.observations: list[Observation] = []

    @contextmanager
    def start_as_current_observation(self, **kwargs):
        observation = Observation()
        self.calls.append(kwargs)
        self.observations.append(observation)
        yield observation

    def get_prompt(self, *_args, **_kwargs):
        raise RuntimeError("Prompt service disabled in this unit test")

    def update_current_span(self, **_kwargs) -> None:
        return None


def test_agent_creates_safe_retrieval_and_generation_children(monkeypatch) -> None:
    client = RecordingClient()
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(agent_module, "tracing_enabled", lambda: True)

    agent_module.LabAgent.run.__wrapped__(
        agent_module.LabAgent(),
        user_id="student-01",
        feature="qa",
        session_id="session-01",
        message="Email demo@vinuni.edu.vn about monitoring",
        correlation_id="req-12345678",
    )

    retrieval, generation = client.calls
    assert retrieval["as_type"] == "retriever"
    assert retrieval["input"]["query_preview"] == "Email [REDACTED_EMAIL] about monitoring"
    assert client.observations[0].updates[-1]["output"] == {"document_count": 1}

    assert generation["as_type"] == "generation"
    assert generation["model"] == "claude-sonnet-4-5"
    assert "demo@vinuni.edu.vn" not in str(generation)
    generation_update = client.observations[1].updates[-1]
    assert generation_update["usage_details"]["total"] > 0
    assert generation_update["cost_details"]["total"] > 0
    assert generation_update["output"]["answer_length"] > 0
