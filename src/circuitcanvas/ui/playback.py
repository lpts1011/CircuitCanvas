"""One shared timer for transient playback and current-arrow animation."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal


class PlaybackController(QObject):
    """Plays the simulated time span like a video.

    The whole span takes ``PLAY_SECONDS`` at 1× speed whether it lasts 25 ms or 50 s,
    so every circuit is watchable. Playback stops at the end; playing again restarts.
    """

    PLAY_SECONDS = 6.0

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

    def seek(self, index: int) -> None:
        """Continue playback from a sample the user picked."""
        self.index = max(0, min(index, self.samples - 1))
        self._elapsed = 0.0

    def set_playing(self, playing: bool) -> None:
        if playing and self.samples > 1:
            if self.index >= self.samples - 1:
                self.index = 0
                self._elapsed = 0.0
                self.time_index_changed.emit(self.index)
            self.timer.start()
        else:
            self.timer.stop()
        self.playing_changed.emit(self.timer.isActive())

    def _tick(self) -> None:
        frame_seconds = self.timer.interval() / 1000.0
        self.animation_tick.emit(frame_seconds)
        if self.samples < 2:
            return
        self._elapsed += frame_seconds * self.speed
        seconds_per_sample = self.PLAY_SECONDS / (self.samples - 1)
        steps = int(self._elapsed / seconds_per_sample)
        if steps <= 0:
            return
        self._elapsed -= steps * seconds_per_sample
        self.index = min(self.index + steps, self.samples - 1)
        self.time_index_changed.emit(self.index)
        if self.index >= self.samples - 1:
            self.set_playing(False)
