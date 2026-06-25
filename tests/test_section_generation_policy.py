from datetime import datetime, timedelta, timezone


def _done(section_id: str, index: int):
    return {
        "section_id": section_id,
        "status": "done",
        "finished_at": f"2026-06-25T08:00:{index:02d}+00:00",
        "metadata": {"slow_stream": False},
    }


def _slow(section_id: str, index: int):
    return {
        "section_id": section_id,
        "status": "partial_generated",
        "finished_at": f"2026-06-25T08:00:{index:02d}+00:00",
        "metadata": {
            "slow_stream": True,
            "timeout_code": "MODEL_STREAM_SLOW_TIMEOUT",
        },
    }


def test_adaptive_policy_starts_with_two_lanes_by_default():
    from backend.services.section_generation_policy import resolve_section_generation_concurrency

    decision = resolve_section_generation_concurrency({"items": [], "metadata": {}}, max_concurrency=3)

    assert decision["current_concurrency"] == 2
    assert decision["metadata"]["scheduler_policy"] == "adaptive_v1"
    assert "自适应初始并发" in decision["policy_message"]


def test_adaptive_policy_reduces_to_one_after_recent_slow_streams():
    from backend.services.section_generation_policy import resolve_section_generation_concurrency

    task = {
        "items": [
            _done("ok-1", 1),
            _slow("slow-1", 2),
            _slow("slow-2", 3),
            {"section_id": "queued", "status": "queued"},
        ],
        "metadata": {"current_concurrency": 3},
    }

    decision = resolve_section_generation_concurrency(task, max_concurrency=3)

    assert decision["current_concurrency"] == 1
    assert decision["metadata"]["last_policy_change"] == "reduce_concurrency"
    assert decision["metadata"]["slow_stream_count"] == 2
    assert decision["metadata"]["timeout_count"] == 2


def test_adaptive_policy_restores_max_after_stable_window():
    from backend.services.section_generation_policy import resolve_section_generation_concurrency

    old_change = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    task = {
        "items": [_done(f"ok-{index}", index) for index in range(1, 6)],
        "metadata": {"current_concurrency": 1, "last_policy_change_at": old_change},
    }

    decision = resolve_section_generation_concurrency(task, max_concurrency=3)

    assert decision["current_concurrency"] == 3
    assert decision["metadata"]["last_policy_change"] == "increase_concurrency"


def test_adaptive_policy_holds_recent_increase_to_avoid_jitter():
    from backend.services.section_generation_policy import resolve_section_generation_concurrency

    recent_change = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    task = {
        "items": [_done(f"ok-{index}", index) for index in range(1, 6)],
        "metadata": {"current_concurrency": 1, "last_policy_change_at": recent_change},
    }

    decision = resolve_section_generation_concurrency(task, max_concurrency=3)

    assert decision["current_concurrency"] == 1
    assert decision["metadata"]["last_policy_change"] == "hold_concurrency"
