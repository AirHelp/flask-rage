import json
import logging
import unittest
from unittest import mock
from unittest.mock import Mock

from flask import Response, request, Flask

from flask_rage import FlaskRageFormatter, FlaskRage, current_millis


class TestFlaskRageFormatter(unittest.TestCase):
    def setUp(self):
        self.formatter = FlaskRageFormatter()

    @mock.patch.object(json, "dumps")
    def test_dumps_json(self, json_dumps):
        self.formatter.format(self._log_record())
        json_dumps.assert_called()

    def test_adds_basic_info(self):
        record = self._log_record()
        formatted = json.loads(self.formatter.format(record))
        self.assertIn("@timestamp", formatted)
        self.assertEqual(formatted["severity"], "NOTSET")
        self.assertEqual(formatted["message"], "message")

    def test_extracts_request_info_from_logrecord(self):
        extra = {
            "method": "POST",
            "path": "/url/path",
            "format": "application/json",
            "duration": 0.1,
            "controller": "controller",
            "action": "action",
            "status": 200,
            "view": "view",
            "db": 0.1,
            "params": "?some=parameters",
            "exception": None,
            "exception_object": None,
            "host": "localhost"
        }
        record = self._log_record(extra)
        formatted = json.loads(self.formatter.format(record))
        for key, value in extra.items():
            self.assertEqual(formatted[key], value)

    def _log_record(self, extra=None):
        logger = logging.getLogger()
        return logger.makeRecord("logger", logging.NOTSET, "func", 0, "message", None, None, extra=extra)


class TestFlaskRage(unittest.TestCase):
    def setUp(self):
        self.app = Flask("test-app")
        self.rage = FlaskRage()
        self.rage.init_app(self.app)

    @mock.patch.object(Flask, "after_request")
    @mock.patch.object(Flask, "before_request")
    def test_initializes_new_flask_application(self, before_request, after_request):
        self.rage.init_app(self.app)

        before_request.assert_called_with(self.rage._add_request_start_time)
        after_request.assert_called_with(self.rage.log_request)

    @mock.patch("flask.Flask", autospec=True)
    def test_initializes_legacy_flask_application(self, flask_app):
        flask_app.logger_name = "test-logger"
        self.rage.init_app(flask_app)

        flask_app.before_request.assert_called_with(self.rage._add_request_start_time)
        flask_app.after_request.assert_called_with(self.rage.log_request)

    def test_logs_request(self):
        logger = Mock()
        self.rage.logger = logger
        with self.app.test_request_context("/test"):
            resp = Response(status=200)
            self.rage.log_request(resp)
        logger.info.assert_called()
        logger.error.assert_not_called()

    def test_logs_error_for_request_with_code_gteq_400_and_neq_404(self):
        logger = Mock()
        self.rage.logger = logger
        with self.app.test_request_context("/test"):
            resp = Response(status=400)
            self.rage.log_request(resp)
        logger.info.assert_not_called()
        logger.error.assert_called_once()

    def test_logs_info_for_request_with_code_eq_404(self):
        logger = Mock()
        self.rage.logger = logger
        with self.app.test_request_context("/test"):
            resp = Response(status=404)
            self.rage.log_request(resp)
        logger.info.assert_called_once()
        logger.error.assert_not_called()

    def test_does_not_log_request_for_exceptions(self):
        logger = Mock()
        self.rage.logger = logger
        with self.app.test_request_context("/test"):
            resp = Response(status=500)
            self.rage.log_request(resp)
        logger.info.assert_not_called()

    def test_logs_exception(self):
        logger = Mock()
        self.rage.logger = logger
        with self.app.test_request_context("/test"):
            exc = Exception()
            self.rage.log_exception(exc)
        logger.error.assert_called()

    @mock.patch("flask_rage.stack")
    @mock.patch("flask_rage.current_millis")
    def test_adds_request_start_time_to_stack(self, current, stack):
        current.return_value = 1
        self.rage._add_request_start_time()
        self.assertEqual(stack.top.request_start, 1)

        stack.top = None
        self.rage._add_request_start_time()
        self.assertIsNone(stack.top)

    def test_parses_request_and_response(self):
        with self.app.test_request_context("/test"):
            resp = Response(status=200)
            message, extra = self.rage._parse(request, resp)
        self.assertIn("[200] GET /test", message)
        self.assertIsInstance(extra, dict)
        self.assertEqual(extra["status"], 200)
        self.assertEqual(extra["path"], "/test")

    def test_parses_request_and_exception(self):
        with self.app.test_request_context("/test"):
            exc = Exception()
            message, extra = self.rage._parse(request, exc)
        self.assertIn("[500] GET /test", message)
        self.assertIsInstance(extra, dict)
        self.assertEqual(extra["status"], 500)
        self.assertEqual(extra["path"], "/test")

    def test_parses_url_query_into_dict(self):
        with self.app.test_request_context("/test?this=is&quite=interesting"):
            resp = Response(status=200)
            _message, extra = self.rage._parse(request, resp)
        self.assertDictEqual({"this": ["is"], "quite": ["interesting"]}, extra["params"])

    @mock.patch("flask_rage.stack")
    def test_takes_db_time_from_stack(self, stack):
        stack.top.db_time = None
        self.assertIsNone(self.rage._db_time())

        stack.top.db_time = 1
        self.assertEqual(self.rage._db_time(), 1)

        stack.top = None
        self.assertIsNone(self.rage._db_time())

    @mock.patch("flask_rage.stack")
    def test_takes_request_duration_from_stack(self, stack):
        stack.top.request_start = None
        self.assertIsNone(self.rage._duration())

        stack.top.request_start = current_millis()
        self.assertGreater(self.rage._duration(), 0)

        stack.top = None
        self.assertIsNone(self.rage._duration())

    @mock.patch.object(FlaskRage, "_db_time")
    @mock.patch.object(FlaskRage, "_duration")
    def test_calculates_view_time(self, duration, db_time):
        duration.return_value = 1
        db_time.return_value = 0.1
        self.assertEqual(self.rage._view_time(), 0.9)
