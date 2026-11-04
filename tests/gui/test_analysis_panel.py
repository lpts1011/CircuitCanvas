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


def test_dragging_the_time_cursor_emits_the_nearest_sample(qtbot) -> None:
    panel = AnalysisPanel()
    qtbot.addWidget(panel)
    time = np.linspace(0.0, 0.01, 5)
    zeros = np.zeros(5)
    panel.set_branch("R1", time, BranchResult(zeros, zeros, zeros, zeros))

    with qtbot.waitSignal(panel.cursor_index_changed) as signal:
        panel.cursors[0].setValue(0.0049)

    assert signal.args == [2]
    assert panel.cursors[1].value() == time[2]


def test_voltage_and_current_have_their_own_plots_on_one_time_axis(qtbot) -> None:
    panel = AnalysisPanel()
    qtbot.addWidget(panel)

    assert panel.voltage_curve in panel.voltage_plot.items
    assert panel.current_curve in panel.current_plot.items
    linked = panel.current_plot.getViewBox().linkedView(panel.current_plot.getViewBox().XAxis)
    assert linked is panel.voltage_plot.getViewBox()


def test_placeholder_replaces_stale_graphs(qtbot) -> None:
    panel = AnalysisPanel()
    qtbot.addWidget(panel)
    time = np.linspace(0.0, 0.01, 5)
    ones = np.ones(5)
    panel.set_branch("R1", time, BranchResult(ones, ones, ones, ones))
    assert not panel.showing_placeholder

    panel.show_placeholder("Graphs appear here once the circuit is complete.")

    assert panel.showing_placeholder
    assert panel.voltage_curve.getData()[0] is None or len(panel.voltage_curve.getData()[0]) == 0
