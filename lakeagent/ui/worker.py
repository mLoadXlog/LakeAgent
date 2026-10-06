"""Background worker: consumes a generator of events on a QThread."""
from PyQt5 import QtCore


class Job(QtCore.QThread):
    """Runs generator_fn(*args) and re-emits its events on the UI thread."""

    event = QtCore.pyqtSignal(str, object)
    finished = QtCore.pyqtSignal(dict)

    def __init__(self, generator_fn, args=(), parent=None, name="job"):
        super(Job, self).__init__(parent)
        self.setObjectName(name)
        self._fn = generator_fn
        self._args = args
        self._stop = False
        self.summary = {}

    def run(self):
        try:
            for kind, payload in self._fn(*self._args):
                if self._stop and kind != "done":
                    continue
                self.event.emit(kind, payload)
                if kind == "done":
                    self.summary = payload or {}
        except Exception as exc:  # noqa: BLE001
            self.event.emit("error", "{0}: {1}".format(
                type(exc).__name__, exc))
            self.summary = {"ok": False}
        finally:
            self.finished.emit(self.summary)

    def stop(self):
        self._stop = True
        self.requestInterruption()
        self.wait(1500)