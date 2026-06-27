import os
import unittest
from unittest.mock import ANY, MagicMock, patch


os.environ.setdefault("APP_AUTH_ENABLED", "false")
os.environ.setdefault("APP_LOGIN_ENABLED", "false")
os.environ.setdefault("APP_EXPOSE_DEBUG_ERRORS", "false")
os.environ.setdefault("REQUIRE_STRICT_CONFIG", "false")
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:16379/0")


class SectionGenerationAutoResumeTest(unittest.TestCase):
    def test_dispatch_requeues_partial_items_before_final_partial_failed(self):
        from backend.tasks import section_tasks

        project_id = "11111111-1111-1111-1111-111111111111"
        task_id = "22222222-2222-2222-2222-222222222222"
        section_id = "33333333-3333-3333-3333-333333333333"
        partial_task = {
            "id": task_id,
            "project_id": project_id,
            "status": "partial_failed",
            "metadata": {"autoResumePartial": True, "maxAutoResumeAttempts": 3},
            "items": [
                {
                    "section_id": section_id,
                    "status": "partial_generated",
                    "attempt": 1,
                    "target_words": 1000,
                    "chars": 120,
                    "draft_content": "## 章节\n\n已有草稿",
                }
            ],
        }
        queued_task = {
            **partial_task,
            "status": "running",
            "items": [{**partial_task["items"][0], "status": "queued"}],
        }
        leased_item = {
            "section_id": section_id,
            "attempt_id": "attempt-2",
            "worker_id": "worker-1",
        }
        apply_async = MagicMock()

        with (
            patch("backend.db.supabase_repo.get_bid_generation_task", side_effect=[partial_task, queued_task]),
            patch("backend.db.supabase_repo.expire_bid_generation_task_items", return_value=[]),
            patch("backend.db.supabase_repo.requeue_bid_generation_task_item", return_value=queued_task) as requeue_mock,
            patch("backend.db.supabase_repo.patch_bid_generation_task_metadata", return_value=queued_task),
            patch("backend.db.supabase_repo.lease_bid_generation_task_items", return_value=[leased_item]) as lease_mock,
            patch("backend.tasks.section_tasks.group", return_value=MagicMock(apply_async=apply_async)),
        ):
            result = section_tasks._dispatch_next_sections(project_id, task_id)

        requeue_mock.assert_called_once_with(
            project_id,
            task_id,
            section_id,
            reason="auto_resume_partial",
            preserve_draft=True,
            metadata_patch=ANY,
        )
        self.assertEqual(requeue_mock.call_args.kwargs["metadata_patch"]["partial_resume_action"], "auto_resume")
        lease_mock.assert_called_once()
        apply_async.assert_called_once()
        self.assertEqual(result["dispatched"], 1)

    def test_dispatch_marks_exhausted_partial_for_review_without_requeue(self):
        from backend.tasks import section_tasks

        project_id = "11111111-1111-1111-1111-111111111111"
        task_id = "22222222-2222-2222-2222-222222222222"
        section_id = "33333333-3333-3333-3333-333333333333"
        partial_task = {
            "id": task_id,
            "project_id": project_id,
            "status": "partial_failed",
            "metadata": {"autoResumePartial": True, "maxAutoResumeAttempts": 3, "partialMaxSlowAttempts": 2},
            "items": [
                {
                    "section_id": section_id,
                    "status": "partial_generated",
                    "attempt": 2,
                    "target_words": 1000,
                    "chars": 120,
                    "metadata": {"slow_stream": True, "timeout_code": "MODEL_STREAM_SLOW_TIMEOUT"},
                }
            ],
        }
        apply_async = MagicMock()

        with (
            patch("backend.db.supabase_repo.get_bid_generation_task", return_value=partial_task),
            patch("backend.db.supabase_repo.expire_bid_generation_task_items", return_value=[]),
            patch("backend.db.supabase_repo.requeue_bid_generation_task_item") as requeue_mock,
            patch("backend.db.supabase_repo.update_bid_generation_task_item", return_value=partial_task) as update_mock,
            patch("backend.db.supabase_repo.patch_bid_generation_task_metadata", return_value=partial_task) as metadata_mock,
            patch("backend.db.supabase_repo.lease_bid_generation_task_items", return_value=[]) as lease_mock,
            patch("backend.tasks.section_tasks.group", return_value=MagicMock(apply_async=apply_async)),
        ):
            result = section_tasks._dispatch_next_sections(project_id, task_id)

        requeue_mock.assert_not_called()
        update_mock.assert_called_once()
        item_patch = update_mock.call_args.args[3]
        self.assertEqual(item_patch["_event_type"], "partial_review_required")
        self.assertTrue(item_patch["metadata"]["partial_review_required"])
        self.assertEqual(item_patch["metadata"]["partial_resume_reason"], "slow_partial_limit_reached")
        metadata = next(call.args[2] for call in metadata_mock.call_args_list if "partial_review_required_count" in call.args[2])
        self.assertEqual(metadata["partial_review_required_count"], 1)
        lease_mock.assert_called_once()
        apply_async.assert_not_called()
        self.assertEqual(result["dispatched"], 0)

    def test_dispatch_uses_adaptive_policy_to_reduce_lease_window(self):
        from backend.tasks import section_tasks

        project_id = "11111111-1111-1111-1111-111111111111"
        task_id = "22222222-2222-2222-2222-222222222222"
        task = {
            "id": task_id,
            "project_id": project_id,
            "status": "running",
            "metadata": {"scheduler_policy": "adaptive_v1"},
            "items": [
                {
                    "section_id": "slow-1",
                    "status": "partial_generated",
                    "finished_at": "2026-06-25T08:00:01+00:00",
                    "metadata": {"slow_stream": True, "timeout_code": "MODEL_STREAM_SLOW_TIMEOUT"},
                },
                {
                    "section_id": "slow-2",
                    "status": "partial_generated",
                    "finished_at": "2026-06-25T08:00:02+00:00",
                    "metadata": {"timeout_code": "MODEL_STREAM_WALL_TIMEOUT"},
                },
                {"section_id": "queued-1", "status": "queued"},
                {"section_id": "queued-2", "status": "queued"},
            ],
        }
        leased_item = {
            "section_id": "queued-1",
            "attempt_id": "attempt-1",
            "worker_id": "worker-1",
        }
        apply_async = MagicMock()

        with (
            patch.dict("os.environ", {"SECTION_GEN_CONCURRENCY": "3"}, clear=False),
            patch("backend.db.supabase_repo.get_bid_generation_task", return_value=task),
            patch("backend.db.supabase_repo.expire_bid_generation_task_items", return_value=[]),
            patch("backend.db.supabase_repo.patch_bid_generation_task_metadata", return_value=task) as metadata_mock,
            patch("backend.db.supabase_repo.lease_bid_generation_task_items", return_value=[leased_item]) as lease_mock,
            patch("backend.tasks.section_tasks.group", return_value=MagicMock(apply_async=apply_async)),
        ):
            result = section_tasks._dispatch_next_sections(project_id, task_id)

        metadata = metadata_mock.call_args.args[2]
        self.assertEqual(metadata["current_concurrency"], 1)
        self.assertEqual(metadata["last_policy_change"], "reduce_concurrency")
        lease_mock.assert_called_once()
        self.assertEqual(lease_mock.call_args.kwargs["limit"], 1)
        apply_async.assert_called_once()
        self.assertEqual(result["concurrency"], 1)

    def test_coordinator_failure_marks_business_task_failed(self):
        from backend.tasks import section_tasks

        project_id = "11111111-1111-1111-1111-111111111111"
        task_id = "22222222-2222-2222-2222-222222222222"
        task = {
            "id": task_id,
            "project_id": project_id,
            "status": "queued",
            "items": [
                {
                    "section_id": "33333333-3333-3333-3333-333333333333",
                    "status": "queued",
                }
            ],
        }

        with (
            patch("backend.db.supabase_repo.get_bid_generation_task", return_value=task),
            patch("backend.tasks.section_tasks._dispatch_next_sections", side_effect=RuntimeError("missing rpc")),
            patch("backend.db.supabase_repo.fail_bid_generation_task", return_value={**task, "status": "failed"}) as fail_mock,
        ):
            result = section_tasks.run_bid_section_generation.run(project_id, task_id)

        fail_mock.assert_called_once()
        args, kwargs = fail_mock.call_args
        self.assertEqual(args[:2], (project_id, task_id))
        self.assertIn("调度失败", kwargs["message"])
        self.assertEqual(kwargs["error"], "missing rpc")
        self.assertEqual(result["status"], "failed")

    def test_coordinator_dispatches_partial_only_tasks_for_resume_policy(self):
        from backend.tasks import section_tasks

        project_id = "11111111-1111-1111-1111-111111111111"
        task_id = "22222222-2222-2222-2222-222222222222"
        task = {
            "id": task_id,
            "project_id": project_id,
            "status": "partial_failed",
            "items": [
                {
                    "section_id": "33333333-3333-3333-3333-333333333333",
                    "status": "partial_generated",
                }
            ],
        }

        with (
            patch("backend.db.supabase_repo.get_bid_generation_task", return_value=task),
            patch("backend.tasks.section_tasks._dispatch_next_sections", return_value={"task_id": task_id, "dispatched": 1}) as dispatch_mock,
        ):
            result = section_tasks.run_bid_section_generation.run(project_id, task_id)

        dispatch_mock.assert_called_once_with(project_id, task_id)
        self.assertEqual(result["dispatched"], 1)

    def test_reconciler_expires_new_style_items_and_fails_legacy_tasks(self):
        from backend.db import supabase_repo

        new_task = {
            "id": "22222222-2222-2222-2222-222222222222",
            "project_id": "11111111-1111-1111-1111-111111111111",
            "status": "running",
        }
        legacy_task = {
            "id": "44444444-4444-4444-4444-444444444444",
            "project_id": "11111111-1111-1111-1111-111111111111",
            "status": "queued",
        }

        with (
            patch("backend.db.supabase_repo.list_stale_bid_generation_tasks", return_value=[new_task, legacy_task]),
            patch("backend.db.supabase_repo._count_bid_generation_task_items", side_effect=[2, 0]),
            patch("backend.db.supabase_repo.expire_bid_generation_task_items", return_value=[{"section_id": "s1"}]) as expire_mock,
            patch("backend.db.supabase_repo.fail_bid_generation_task", return_value={**legacy_task, "status": "failed"}) as fail_mock,
        ):
            result = supabase_repo.reconcile_stale_bid_generation_tasks(max_age_seconds=600, limit=10)

        expire_mock.assert_called_once_with(new_task["project_id"], new_task["id"], requeue=True)
        fail_mock.assert_called_once()
        self.assertEqual(result["scanned"], 2)
        self.assertEqual(result["expired_items"], 1)
        self.assertEqual(result["failed_legacy_tasks"], 1)

    def test_reconciler_celery_task_delegates_to_repo(self):
        from backend.tasks import section_tasks

        with patch(
            "backend.db.supabase_repo.reconcile_stale_bid_generation_tasks",
            return_value={"scanned": 1, "expired_items": 0, "failed_legacy_tasks": 1, "skipped": 0, "tasks": []},
        ) as reconcile_mock:
            result = section_tasks.reconcile_stale_section_generation_tasks.run(max_age_seconds=600, limit=5)

        reconcile_mock.assert_called_once_with(max_age_seconds=600, limit=5)
        self.assertEqual(result["failed_legacy_tasks"], 1)

    def test_stream_bid_section_uses_continuation_prompt_when_draft_exists(self):
        from backend.ai import section_writer

        chapter = {
            "id": "33333333-3333-3333-3333-333333333333",
            "title": "施工组织设计",
            "metadata": {
                "generation_options": {
                    "continuationDraft": "## 施工组织设计\n\n已有草稿",
                }
            },
        }

        with (
            patch("backend.ai.section_writer.build_section_prompt", return_value="normal prompt") as normal_prompt,
            patch("backend.ai.section_writer.build_section_continuation_prompt", return_value="continue prompt") as continuation_prompt,
            patch("backend.ai.section_writer.stream_dashscope_api", return_value=iter(["续写内容"])),
            patch("backend.ai.section_writer.get_stage_model", return_value="test-model"),
            patch("backend.ai.section_writer._needs_length_supplement", return_value=False),
        ):
            events = list(section_writer.stream_bid_section("11111111-1111-1111-1111-111111111111", chapter))

        normal_prompt.assert_not_called()
        continuation_prompt.assert_called_once()
        self.assertEqual(events[0]["type"], "start")
        self.assertEqual(events[1]["content"], "续写内容")

    def test_stream_bid_section_stops_when_hard_length_cap_is_reached(self):
        from backend.ai import section_writer

        chapter = {
            "id": "33333333-3333-3333-3333-333333333333",
            "title": "类似项目业绩 - 资料清单",
            "metadata": {
                "writing_plan": {
                    "target_words": 10,
                }
            },
        }

        with (
            patch.dict(
                "os.environ",
                {
                    "BID_SECTION_HARD_LENGTH_CAP_ENABLED": "true",
                    "BID_SECTION_HARD_LENGTH_CAP_RATIO": "1.0",
                    "BID_SECTION_HARD_LENGTH_CAP_MIN_EXTRA_WORDS": "0",
                },
                clear=False,
            ),
            patch("backend.ai.section_writer.build_section_prompt", return_value="prompt"),
            patch("backend.ai.section_writer.stream_dashscope_api", return_value=iter(["一二三四五", "六七八九十", "不应继续输出"])),
            patch("backend.ai.section_writer.get_stage_model", return_value="test-model"),
            patch("backend.ai.section_writer._needs_length_supplement", return_value=False),
        ):
            events = list(section_writer.stream_bid_section("11111111-1111-1111-1111-111111111111", chapter))

        chunk_text = "".join(event.get("content", "") for event in events if event.get("type") == "chunk")
        self.assertEqual(chunk_text, "一二三四五六七八九十")
        self.assertTrue(any(event.get("type") == "length_cap_reached" for event in events))
        self.assertEqual(events[-1]["type"], "done")

    def test_stream_bid_section_raises_slow_timeout_with_metrics(self):
        from backend.ai import section_writer
        from backend.ai.qwen_client import LLMStreamTimeoutError

        chapter = {
            "id": "33333333-3333-3333-3333-333333333333",
            "title": "编制依据",
            "metadata": {"volume_type": "technical"},
        }
        events = []
        with (
            patch.dict(
                "os.environ",
                {
                    "SECTION_STREAM_SLOW_CHECK_SECONDS": "2",
                    "SECTION_STREAM_MIN_CHARS_AT_SLOW_CHECK": "10",
                    "SECTION_STREAM_FIRST_TOKEN_SLOW_SECONDS": "1",
                },
                clear=False,
            ),
            patch("backend.ai.section_writer.time.monotonic", side_effect=[0.0, 1.5, 2.5]),
            patch("backend.ai.section_writer.build_section_prompt", return_value="prompt"),
            patch("backend.ai.section_writer.stream_dashscope_api", return_value=iter(["少", "量"])),
            patch("backend.ai.section_writer.get_stage_model", return_value="test-model"),
            patch("backend.ai.section_writer._needs_length_supplement", return_value=False),
        ):
            with self.assertRaises(LLMStreamTimeoutError) as raised:
                for event in section_writer.stream_bid_section("11111111-1111-1111-1111-111111111111", chapter):
                    events.append(event)

        self.assertEqual(raised.exception.code, "MODEL_STREAM_SLOW_TIMEOUT")
        self.assertTrue(raised.exception.metadata["slow_stream"])
        self.assertEqual(raised.exception.metadata["stream_chars"], 2)
        self.assertEqual(raised.exception.metadata["min_chars_at_slow_check"], 10)
        self.assertTrue(any(event.get("type") == "stream_metric" and event.get("first_token_slow") for event in events))
        self.assertTrue(any(event.get("type") == "stream_metric" and event.get("slow_stream") for event in events))

    def test_generate_and_save_bid_section_preserves_timeout_metadata(self):
        from backend.ai.qwen_client import LLMStreamTimeoutError
        from backend.services.section_generation import SectionGenerationTimeout, generate_and_save_bid_section

        def slow_stream(*_args, **_kwargs):
            yield {"type": "start", "prompt_profile": "simple_plan", "prompt_chars": 1000}
            yield {
                "type": "stream_metric",
                "first_token_latency_ms": 1500,
                "stream_chars": 2,
                "slow_stream": True,
                "slow_stream_reason": "elapsed_2s_chars_2_below_10",
            }
            raise LLMStreamTimeoutError(
                "MODEL_STREAM_SLOW_TIMEOUT",
                "slow stream",
                metadata={"slow_stream": True, "timeout_code": "MODEL_STREAM_SLOW_TIMEOUT"},
            )

        events = []
        with (
            patch("backend.services.section_generation.stream_bid_section", side_effect=slow_stream),
            patch("backend.services.section_generation.mark_section_generation_partial") as partial_mock,
        ):
            with self.assertRaises(SectionGenerationTimeout) as raised:
                generate_and_save_bid_section(
                    "11111111-1111-1111-1111-111111111111",
                    {"id": "33333333-3333-3333-3333-333333333333", "title": "编制依据"},
                    on_event=events.append,
                )

        self.assertEqual(raised.exception.code, "MODEL_STREAM_SLOW_TIMEOUT")
        self.assertTrue(raised.exception.metadata["slow_stream"])
        self.assertEqual(raised.exception.metadata["timeout_code"], "MODEL_STREAM_SLOW_TIMEOUT")
        self.assertTrue(any(event.get("type") == "timeout" and event.get("metadata", {}).get("slow_stream") for event in events))
        partial_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
