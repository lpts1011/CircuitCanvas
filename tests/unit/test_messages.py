from circuitcanvas.solver.validation import Diagnostic
from circuitcanvas.ui.messages import describe, describe_bypassed


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


def test_loose_wire_end_message_points_at_the_orange_dot() -> None:
    problem = describe(Diagnostic("dangling-wire", "raw"), has_components=True)

    assert "orange end" in problem.text
    assert "Delete" in problem.text


def test_bypassed_components_are_named_with_a_way_to_fix_it() -> None:
    assert describe_bypassed(("C1",)).startswith("C1 is bypassed")
    assert "drag C1 onto it" in describe_bypassed(("C1",))
    assert describe_bypassed(("R1", "C2")).startswith("R1 and C2 are bypassed")
