"""Debounced, revision-safe background simulation."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal, Slot

from circuitcanvas.domain.circuit import CircuitSnapshot
from circuitcanvas.solver.results import SimulationResult
from circuitcanvas.solver.transient import CircuitSimulationError, simulate
from circuitcanvas.solver.validation import Diagnostic, validate


class _WorkerSignals(QObject):
    succeeded = Signal(int, object)
    failed = Signal(int, str)


class _SimulationWorker(QRunnable):
    def __init__(
        self,
        revision: int,
        snapshot: CircuitSnapshot,
        solver_fn: Callable[[CircuitSnapshot], SimulationResult],
    ) -> None:
        super().__init__()
        self.revision = revision
        self.snapshot = snapshot
        self.solver_fn = solver_fn
        self.signals = _WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.solver_fn(self.snapshot)
        except (CircuitSimulationError, ValueError) as exc:
            self.signals.failed.emit(self.revision, str(exc))
            return
        self.signals.succeeded.emit(self.revision, result)


class SimulationController(QObject):
    result_ready = Signal(int, object)
    diagnostics_ready = Signal(int, object)

    def __init__(
        self,
        *,
        solver_fn: Callable[[CircuitSnapshot], SimulationResult] = simulate,
        debounce_ms: int = 150,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.solver_fn = solver_fn
        self.current_revision = -1
        self._pending: tuple[int, CircuitSnapshot] | None = None
        self._workers: set[_SimulationWorker] = set()
        self.pool = QThreadPool(self)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(debounce_ms)
        self.timer.timeout.connect(self._launch)

    def request(self, revision: int, snapshot: CircuitSnapshot) -> None:
        self.current_revision = revision
        self._pending = (revision, snapshot)
        self.timer.start()

    def _launch(self) -> None:
        if self._pending is None:
            return
        revision, snapshot = self._pending
        self._pending = None
        diagnostics = validate(snapshot)
        if diagnostics:
            self.diagnostics_ready.emit(revision, diagnostics)
            return
        worker = _SimulationWorker(revision, snapshot, self.solver_fn)
        self._workers.add(worker)
        worker.signals.succeeded.connect(self._deliver_result)
        worker.signals.failed.connect(self._deliver_error)
        self.pool.start(worker)

    @Slot(int, object)
    def _deliver_result(self, revision: int, result: SimulationResult) -> None:
        if revision == self.current_revision:
            self.result_ready.emit(revision, result)
        self._discard_finished_workers(revision)

    @Slot(int, str)
    def _deliver_error(self, revision: int, message: str) -> None:
        if revision == self.current_revision:
            diagnostic = Diagnostic("simulation-error", message)
            self.diagnostics_ready.emit(revision, (diagnostic,))
        self._discard_finished_workers(revision)

    def _discard_finished_workers(self, revision: int) -> None:
        self._workers = {worker for worker in self._workers if worker.revision != revision}

