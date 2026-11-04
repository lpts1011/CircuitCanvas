"""Plain-language explanations of why a circuit cannot be solved (no Qt dependency)."""

from __future__ import annotations

from dataclasses import dataclass

from circuitcanvas.solver.validation import Diagnostic


@dataclass(frozen=True, slots=True)
class Problem:
    #: "info" for the normal empty starting state, "problem" for something to fix.
    kind: str
    text: str
    #: Components to outline on the canvas.
    component_ids: tuple[str, ...] = ()
    #: False when the canvas already explains it (the "Start here" card).
    show_on_canvas: bool = True


def _names(ids: tuple[str, ...]) -> str:
    if len(ids) <= 1:
        return "".join(ids)
    return ", ".join(ids[:-1]) + " and " + ids[-1]


def describe(diagnostic: Diagnostic, *, has_components: bool) -> Problem:
    """Turn a solver diagnostic into a sentence that says what to do next."""
    ids = tuple(item for item in diagnostic.component_ids if item != "V1")
    code = diagnostic.code
    if code == "source-short" and not has_components:
        return Problem(
            "info",
            "Add a component to the loop to complete the circuit: "
            "click Resistor on the left to start.",
            show_on_canvas=False,
        )
    if code == "source-short":
        return Problem(
            "problem",
            "A bare wire joins the battery's + and − ends, which is a short circuit. "
            "Delete that wire, or drop a component onto it.",
        )
    if code == "dangling-terminal":
        verb = "has an end" if len(ids) == 1 else "have ends"
        pronoun = "it" if len(ids) == 1 else "them"
        return Problem(
            "problem",
            f"{_names(ids)} {verb} that isn't connected. Drag {pronoun} onto a wire to "
            f"put {pronoun} in the circuit, or drag from an orange dot to another dot.",
            ids,
        )
    if code == "dangling-wire":
        return Problem(
            "problem",
            "A wire ends in empty space. Connect its loose end to a dot or a wire, or delete it.",
        )
    if code == "open-circuit":
        return Problem(
            "problem",
            "The circuit isn't closed: no path through the components leads from the "
            "battery's + end back to its − end.",
            ids,
        )
    if code == "floating-subcircuit":
        verb = "isn't" if len(ids) == 1 else "aren't"
        return Problem(
            "problem",
            f"{_names(ids)} {verb} connected to the battery, so nothing flows through "
            f"{'it' if len(ids) == 1 else 'them'}.",
            ids,
        )
    return Problem("problem", diagnostic.message, ids)
