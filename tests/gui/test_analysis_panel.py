import numpy as np
from PySide6.QtCore import Qt

from circuitcanvas.solver.results import BranchResult
from circuitcanvas.ui.analysis_panel import AnalysisPanel


def test_plot_and_table_use_the_same_samples(qtbot) -> None:
    panel = AnalysisPanel()
    qtbot.addWidget(panel)
    time = np.linspace(0.0, 0.01, 5)
    branch = BranchResult(
        voltage=np.linspace(0.0, 5.0, 5),
        current=np.linspace(0.1, 0.0, 5),
        power=np.linspace(0.0, 0.2, 5),
        energy=np.linspace(0.0, 1e-3, 5),
    )

    panel.set_branch("C1", time, branch)
    x, voltage = panel.voltage_curve.getData()
    current_x, current = panel.current_curve.getData()

    np.testing.assert_allclose(x, time)
    np.testing.assert_allclose(voltage, branch.voltage)
    np.testing.assert_allclose(current_x, time)
    np.testing.assert_allclose(current, branch.current)
    assert (
        panel.table_model.data(panel.table_model.index(3, 1), Qt.ItemDataRole.DisplayRole) == "3.75"
    )


def test_time_slider_emits_selected_index(qtbot) -> None:
    panel = AnalysisPanel()
    qtbot.addWidget(panel)
    time = np.linspace(0.0, 0.01, 5)
    zeros = np.zeros(5)
    panel.set_branch("R1", time, BranchResult(zeros, zeros, zeros, zeros))

    with qtbot.waitSignal(panel.time_index_changed) as signal:
        panel.time_slider.setValue(2)

    assert signal.args == [2]


def test_current_curve_uses_independent_right_axis(qtbot) -> None:
    panel = AnalysisPanel()
    qtbot.addWidget(panel)

    assert panel.plot.getPlotItem().getAxis("right").isVisible()
    assert panel.current_curve in panel.current_view.addedItems


def test_typed_time_span_requests_a_manual_span(qtbot) -> None:
    import pytest

    from circuitcanvas.ui.analysis_panel import AnalysisPanel

    panel = AnalysisPanel()
    qtbot.addWidget(panel)
    panel.show_time_span(0.025, auto=True)
    assert panel.span_edit.text() == "25 ms"

    panel.span_edit.setText("200 ms")
    with qtbot.waitSignal(panel.manual_span_requested) as signal:
        panel.span_edit.editingFinished.emit()

    assert signal.args == [pytest.approx(0.2)]
    assert not panel.span_auto.isChecked()

    # A bare number keeps the unit on screen: "50" after "200 ms" is 50 ms.
    panel.span_edit.setText("50")
    with qtbot.waitSignal(panel.manual_span_requested) as signal:
        panel.span_edit.editingFinished.emit()
    assert signal.args == [pytest.approx(0.05)]


def test_unreadable_time_span_is_flagged_not_sent(qtbot) -> None:
    from circuitcanvas.ui.analysis_panel import AnalysisPanel

    panel = AnalysisPanel()
    qtbot.addWidget(panel)
    received: list[float] = []
    panel.manual_span_requested.connect(received.append)

    panel.span_edit.setText("soon")
    panel.span_edit.editingFinished.emit()

    assert received == []
    assert "dc2626" in panel.span_edit.styleSheet()
