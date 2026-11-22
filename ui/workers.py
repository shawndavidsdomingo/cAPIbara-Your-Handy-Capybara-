"""One small helper that runs a function on a background thread.

Network calls must never run on the UI thread (guide rule). Usage:

    task = Task(message_service.send_email, to, subject, body,
                safe=(SendError,), reply_to=(email, name))
    task.succeeded.connect(self.on_ok)       # gets the function's return value
    task.failed.connect(self.on_error)       # gets a message safe to show
    task.start()

Errors listed in `safe` carry a readable message and are passed on as it is.
Any other error is logged and replaced by a generic message.
"""
import logging

from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)

GENERIC_ERROR = "Something went wrong. Please try again."


class Task(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    _running = set()      # keeps a running task alive even if its window closes

    def __init__(self, fn, *args, safe=(), **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs, self.safe = fn, args, kwargs, tuple(safe)

    def start(self, *priority):
        Task._running.add(self)
        self.finished.connect(self._release)
        super().start(*priority)

    def _release(self):
        self.wait()                       # the thread is ending; let it fully stop
        Task._running.discard(self)

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except self.safe as error:
            self.failed.emit(str(error))
        except Exception:
            log.exception("Background task failed")
            self.failed.emit(GENERIC_ERROR)
        else:
            self.succeeded.emit(result)
