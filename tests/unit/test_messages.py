from circuitcanvas.solver.validation import Diagnostic
from circuitcanvas.ui.messages import describe


def test_empty_starter_loop_is_a_friendly_hint_not_an_error() -> None:
    problem = describe(Diagnostic("source-short", "short"), has_components=False)

    assert problem.kind == "info"
    assert not problem.show_on_canvas
    assert "Add a component" in problem.text


def test_loose_terminal_names_the_components_and_says_what_to_do() -> None:
    problem = describe(Diagnostic("dangling-terminal", "raw", ("L1", "C2")), has_components=True)

    assert problem.kind == "problem"
    assert problem.component_ids == ("L1", "C2")
    assert problem.text.startswith("L1 and C2 have ends")
    assert "orange dot" in problem.text


def test_battery_id_is_never_outlined_as_a_problem_component() -> None:
    problem = describe(Diagnostic("open-circuit", "raw", ("V1", "R1")), has_components=True)

    assert problem.component_ids == ("R1",)


def test_unknown_diagnostics_fall_back_to_the_solver_message() -> None:
    problem = describe(Diagnostic("simulation-error", "Matrix is singular."), has_components=True)

    assert problem.text == "Matrix is singular."
