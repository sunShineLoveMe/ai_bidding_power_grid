import io
import json
import logging
import unittest


class LoggingConfigTest(unittest.TestCase):
    def test_json_formatter_outputs_sls_context_fields(self):
        from backend.core.logging_config import ContextFilter, JsonLogFormatter, log_context

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(ContextFilter())
        handler.setFormatter(JsonLogFormatter())

        logger = logging.getLogger("tests.sls")
        original_handlers = list(logger.handlers)
        original_level = logger.level
        original_propagate = logger.propagate
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False
        try:
            with log_context(
                app_module="celery",
                stage="task",
                project_id="project-1",
                file_id="file-1",
                task_id="business-task-1",
                section_id="section-1",
                celery_task_id="celery-task-1",
                celery_task_name="bid.export.docx",
            ):
                logger.info("celery_task_completed", extra={"duration_ms": 123})
        finally:
            logger.handlers = original_handlers
            logger.setLevel(original_level)
            logger.propagate = original_propagate

        payload = json.loads(stream.getvalue())
        self.assertEqual("celery", payload["module"])
        self.assertEqual("task", payload["stage"])
        self.assertEqual("project-1", payload["project_id"])
        self.assertEqual("file-1", payload["file_id"])
        self.assertEqual("business-task-1", payload["task_id"])
        self.assertEqual("section-1", payload["section_id"])
        self.assertEqual("celery-task-1", payload["celery_task_id"])
        self.assertEqual("bid.export.docx", payload["celery_task_name"])
        self.assertEqual(123, payload["duration_ms"])


if __name__ == "__main__":
    unittest.main()
