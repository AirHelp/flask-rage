import json
import logging
import time
from datetime import datetime
from urllib.parse import parse_qs

from flask import _app_ctx_stack as stack
from flask import request, Response

try:
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    has_sql_alchemy = True
except ImportError:
    has_sql_alchemy = False


def current_millis():
    return time.time() * 1000


class FlaskRageFormatter(logging.Formatter):
    keys = {'method', 'path', 'format', 'duration', 'controller', 'action',
            'status', 'view', 'db', 'params',
            'exception', 'exception_object', 'host'}

    def format(self, record):
        output = {}
        for key in self.keys:
            if hasattr(record, key):
                output[key] = getattr(record, key)

        output['@timestamp'] = datetime.fromtimestamp(record.created).astimezone().isoformat()
        output['severity'] = record.levelname
        output['message'] = record.getMessage()

        return json.dumps(output)


class FlaskRage:
    """
    Mimic RoR's lograge 'access log' formatting

    Setup by initializing the logger with your Flask application, e.g.:

        from flask import Flask
        from flask_rage import FlaskRage

        app = Flask(__name__)

        rage = FlaskRage()
        rage.init_app(app)

    """
    logger = None

    def init_app(self, flask_app):
        """
        Initialize logging for Flask application

        :param flask_app: Flask application
        """
        self.logger = logging.getLogger(flask_app.logger_name)
        self._setup_db_timer()
        self._register_handlers(flask_app)

    def log_request(self, response):
        """
        Log a regular HTTP request in lograge-ish format

        :param response: flask.Response
        :return: response
        """
        if response.status_code >= 400:
            return response

        message, extra = self._parse(request, response)
        self.logger.info(message, extra=extra)
        return response

    def log_exception(self, exception):
        """
        Log an exception in lograge-ish format

        This can be called e.g. from flask's errorhandlers

        :param exception: Exception
        """
        message, extra = self._parse(request, exception)
        self.logger.error(message, extra=extra)

    def _setup_db_timer(self):
        if not has_sql_alchemy:
            return
        event.listen(Engine, 'before_cursor_execute', self._before_cursor_execute)
        event.listen(Engine, 'after_cursor_execute', self._after_cursor_execute)

    def _register_handlers(self, flask_app):
        flask_app.before_request(self._add_request_start_time)
        flask_app.after_request(self.log_request)

    def _add_request_start_time(self):
        ctx = stack.top
        if not ctx:
            return
        ctx.request_start = current_millis()

    def _parse(self, req, resp):
        is_response = isinstance(resp, Response)
        if req.url_rule is not None:
            controller, action = req.url_rule.endpoint.partition('.')[::2]
        else:
            controller, action = None, None
        status = resp.status_code if hasattr(resp, 'status_code') else 500

        message = f"[{status}] " \
                  f"{req.environ.get('REQUEST_METHOD')} " \
                  f"{req.environ.get('PATH_INFO')} " \
                  f"({controller}#{action})"

        extra = {
            'method': req.environ.get('REQUEST_METHOD'),
            'path': req.environ.get('PATH_INFO'),
            'format': resp.headers.get('Content-Type') if is_response else None,
            'controller': controller,
            'action': action,
            'status': status,
            'view': self._view_time(),
            'duration': self._duration(),
            'db': self._db_time(),
            'params': parse_qs(req.environ.get('QUERY_STRING')),
            'exception': None if is_response else str(resp),
            'exception_object': None if is_response else resp.__class__.__name__,
            'host': req.environ['SERVER_NAME'],
        }

        return message, extra

    def _db_time(self):
        ctx = stack.top
        if not ctx:
            return None

        if hasattr(ctx, 'db_time'):
            return ctx.db_time

        return None

    def _duration(self):
        ctx = stack.top
        if not ctx:
            return None

        if hasattr(ctx, 'request_start') and ctx.request_start is not None:
            request_duration = current_millis() - ctx.request_start
            return request_duration

        return None

    def _view_time(self):
        duration = self._duration()
        db_time = self._db_time()
        if duration and db_time:
            return duration - db_time
        return None

    def _before_cursor_execute(self, conn, _cur, _stmt, _params, _ctx, _exec_many):
        if not conn:
            return
        conn.info.setdefault('query_start_time', []).append(current_millis())

    def _after_cursor_execute(self, conn, _cur, _stmt, _params, _ctx, _exec_many):
        if not conn:
            return

        ctx = stack.top
        if not ctx:
            return

        query_start_time = conn.info.get('query_start_time', [None]).pop(-1)
        if query_start_time is not None:
            total = current_millis() - query_start_time
            ctx.db_time = total
