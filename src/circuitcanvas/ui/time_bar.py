"""Play button, time scrubber, and the "t = … of …" readout in the main toolbar."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QSlider, QToolButton, QWidget

from .formatting import format_si
from .icons import icon
from .theme import TEXT_MUTED

_SPEEDS = (("0.25×", 0.25), ("0.5×", 0.5), ("1×", 1.0), ("2×", 2.0), ("4×", 4.0))


class TimeBar(QWidget):
    play_toggled = Signal(bool)
    #: The user moved the scrubber to this sample.
    time_index_changed = Signal(int)
    speed_changed = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._time = np.array([], dtype=float)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.play_button = QToolButton()
        self.play_button.setObjectName("playButton")
        self.play_button.setCheckable(True)
        self.play_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.play_button.setIconSize(QSize(16, 16))
        self.play_button.setToolTip(
            "Play the response from the moment the battery is connected (Space)"
        )
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimumWidth(160)
        self.slider.setToolTip("Drag to see the circuit at any moment")
        self.time_label = QLabel()
        self.time_label.setMinimumWidth(150)
        self.speed = QComboBox()
        self.speed.addItems([label for label, _ in _SPEEDS])
        self.speed.setCurrentIndex(2)
        self.speed.setToolTip("Playback speed (1× plays the whole time span in 6 seconds)")

        layout.addWidget(self.play_button)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.time_label)
        layout.addWidget(self.speed)

        self.play_button.toggled.connect(self._play_toggled)
        self.slider.valueChanged.connect(self._slider_moved)
        self.speed.currentIndexChanged.connect(
            lambda index: self.speed_changed.emit(_SPEEDS[index][1])
        )
        self.set_playing(False)
        self.clear()

    @property
    def index(self) -> int:
        return self.slider.value()

    def set_timeline(self, time: np.ndarray) -> None:
        """Show a new result, positioned at its last sample."""
        self._time = time
        self.setEnabled(len(time) > 0)
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(0, len(time) - 1))
        self.slider.blockSignals(False)
        self.set_index(len(time) - 1)

    def set_index(self, index: int) -> None:
        """Move the scrubber without emitting ``time_index_changed``."""
        self.slider.blockSignals(True)
        self.slider.setValue(index)
        self.slider.blockSignals(False)
        self._update_label()

    def clear(self) -> None:
        self._time = np.array([], dtype=float)
        self.slider.blockSignals(True)
        self.slider.setRange(0, 0)
        self.slider.blockSignals(False)
        self.time_label.setText(f"<span style='color:{TEXT_MUTED}'>No result yet</span>")
        self.set_playing(False)
        self.setEnabled(False)

    def set_playing(self, playing: bool) -> None:
        self.play_button.blockSignals(True)
        self.play_button.setChecked(playing)
        self.play_button.blockSignals(False)
        self.play_button.setText("Pause" if playing else "Play")
        self.play_button.setIcon(icon("pause" if playing else "play", "#ffffff", 16))

    def time_text(self) -> str:
        if not len(self._time):
            return ""
        index = max(0, min(self.slider.value(), len(self._time) - 1))
        now = format_si(float(self._time[index]), "s", digits=3)
        end = format_si(float(self._time[-1]), "s", digits=3)
        return f"t = {now} of {end}"

    def _update_label(self) -> None:
        text = self.time_text()
        if text:
            now, _, end = text.partition(" of ")
            muted = f"<span style='color:{TEXT_MUTED}'>of {end}</span>"
            self.time_label.setText(f"<b>{now}</b> {muted}")

    def _play_toggled(self, playing: bool) -> None:
        self.set_playing(playing)
        self.play_toggled.emit(playing)

    def _slider_moved(self, index: int) -> None:
        self._update_label()
        self.time_index_changed.emit(index)
