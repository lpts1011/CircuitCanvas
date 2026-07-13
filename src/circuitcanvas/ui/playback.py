"""One shared timer for transient playback and current-arrow animation."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal


class PlaybackController(QObject):
    time_index_changed = Signal(int)
    animation_tick = Signal(float)
    playing_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self.samples = 0
        self.duration = 0.0
        self.speed = 1.0
        self.index = 0
        self._elapsed = 0.0

    def set_timeline(self, *, samples: int, duration: float) -> None:
        self.samples = samples
        self.duration = duration
        self.index = max(0, samples - 1)
        self._elapsed = 0.0

    def set_speed(self, speed: float) -> None:
        self.speed = max(0.1, min(float(speed), 10.0))

    def set_playing(self, playing: bool) -> None:
        if playing and self.samples > 1:
            self.index = 0 if self.index >= self.samples - 1 else self.index
            self.timer.start()
        else:
            self.timer.stop()
        self.playing_changed.emit(self.timer.isActive())

    def _tick(self) -> None:
        frame_seconds = self.timer.interval() / 1000.0
        self.animation_tick.emit(frame_seconds)
        if self.samples < 2 or self.duration <= 0:
            return
        self._elapsed += frame_seconds * self.speed
        sample_period = self.duration / (self.samples - 1)
        steps = int(self._elapsed / sample_period)
        if steps <= 0:
            return
        self._elapsed -= steps * sample_period
        self.index = (self.index + steps) % self.samples
        self.time_index_changed.emit(self.index)
