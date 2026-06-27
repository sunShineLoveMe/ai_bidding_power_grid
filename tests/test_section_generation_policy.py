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


def test_partial_resume_policy_auto_resumes_short_slow_draft():
    from backend.services.section_generation_policy import resolve_partial_resume_policy

    task = {"metadata": {"autoResumePartial": True, "maxAutoResumeAttempts": 2}}
    item = {
        "section_id": "partial-1",
        "status": "partial_generated",
        "attempt": 1,
        "target_words": 1000,
        "chars": 180,
        "metadata": {"slow_stream": True, "timeout_code": "MODEL_STREAM_SLOW_TIMEOUT"},
    }

    decision = resolve_partial_resume_policy(task, item)

    assert decision["action"] == "auto_resume"
    assert decision["metadata"]["partial_resume_policy"] == "partial_resume_v1"
    assert decision["metadata"]["next_action"] == "auto_resume_with_slim_prompt"
    assert decision["metadata"]["retry_policy"]["next_profile"] == "continuation_slim"


def test_partial_resume_policy_needs_review_when_draft_is_near_target():
    from backend.services.section_generation_policy import resolve_partial_resume_policy

    task = {"metadata": {"autoResumePartial": True, "maxAutoResumeAttempts": 2}}
    item = {
        "section_id": "partial-2",
        "status": "partial_generated",
        "attempt": 1,
        "target_words": 1000,
        "chars": 760,
        "metadata": {"slow_stream": True, "timeout_code": "MODEL_STREAM_SLOW_TIMEOUT"},
    }

    decision = resolve_partial_resume_policy(task, item)

    assert decision["action"] == "needs_review"
    assert decision["metadata"]["partial_review_required"] is True
    assert decision["metadata"]["partial_resume_reason"] == "draft_near_target"


def test_partial_resume_policy_stops_after_two_slow_partials():
    from backend.services.section_generation_policy import resolve_partial_resume_policy

    task = {"metadata": {"autoResumePartial": True, "maxAutoResumeAttempts": 3, "partialMaxSlowAttempts": 2}}
    item = {
        "section_id": "partial-3",
        "status": "partial_generated",
        "attempt": 2,
        "target_words": 1000,
        "chars": 180,
        "metadata": {"slow_stream": True, "timeout_code": "MODEL_STREAM_SLOW_TIMEOUT"},
    }

    decision = resolve_partial_resume_policy(task, item)

    assert decision["action"] == "needs_review"
    assert decision["metadata"]["partial_resume_reason"] == "slow_partial_limit_reached"
    assert decision["metadata"]["retry_policy"]["exhausted"] is True


def test_partial_resume_policy_keeps_price_sensitive_profile_manual():
    from backend.services.section_generation_policy import resolve_partial_resume_policy

    task = {"metadata": {"autoResumePartial": True}}
    item = {
        "section_id": "partial-4",
        "title": "单价分析表",
        "status": "partial_generated",
        "attempt": 0,
        "target_words": 1000,
        "chars": 80,
        "metadata": {"prompt_profile": "price_sensitive"},
    }

    decision = resolve_partial_resume_policy(task, item)

    assert decision["action"] == "needs_review"
    assert decision["metadata"]["partial_resume_reason"] == "manual_only_profile"
