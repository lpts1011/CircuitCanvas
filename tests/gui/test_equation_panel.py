from circuitcanvas.solver.equations import EquationLine, EquationReport
from circuitcanvas.ui.equation_panel import EquationPanel


def sample_report() -> EquationReport:
    kcl = EquationLine(
        "KCL1",
        "kcl",
        "I_R1 - I_R2 = 0",
        "0.1 - 0.1 = 0",
        "residual = 0 A",
        0.0,
        ("R1", "R2"),
        ("n1",),
    )
    kvl = EquationLine(
        "KVL1",
        "kvl",
        "V_V1 - V_R1 = 0",
        "12 - 12 = 0",
        "residual = 0 V",
        0.0,
        ("V1", "R1"),
        ("n_pos", "n_neg"),
    )
    return EquationReport(
        (kcl,),
        (kvl,),
        (),
        "i_C1(t) = C1·dv_C1/dt",
        "Differential-algebraic MNA system\nC x_dot(t) + G x(t) = b(t)",
    )


def test_panel_switches_between_ordinary_and_differential(qtbot) -> None:
    panel = EquationPanel()
    qtbot.addWidget(panel)
    panel.set_report(sample_report())

    assert "I_R1 - I_R2" in panel.visible_text()

    panel.differential_button.click()

    assert "C x_dot(t) + G x(t) = b(t)" in panel.visible_text()


def test_selecting_equation_emits_the_equation(qtbot) -> None:
    panel = EquationPanel()
    qtbot.addWidget(panel)
    panel.set_report(sample_report())

    with qtbot.waitSignal(panel.equation_selected) as signal:
        panel.select_equation("KVL1")

    assert signal.args[0].id == "KVL1"


def test_report_refresh_preserves_selected_equation(qtbot) -> None:
    panel = EquationPanel()
    qtbot.addWidget(panel)
    panel.set_report(sample_report())
    panel.select_equation("KVL1")

    panel.set_report(sample_report())

    assert "V_V1 - V_R1" in panel.visible_text()
