# Backspace Component Deletion Design

## Goal

Allow a selected circuit component to be removed with either the keyboard's `Backspace` key or its `Delete` key.

## Design

The existing `MainWindow.delete_action` remains the single deletion entry point. Its shortcut list will contain both `Delete` and `Backspace`, and both shortcuts will call the existing `_delete_selected` method. This avoids a second deletion implementation and preserves the command stack, topology cleanup, selection handling, simulation refresh, and undo behavior already used by the toolbar action.

Qt's normal shortcut-override behavior remains in charge when a text field is actively editing a value, so Backspace can continue editing text instead of deleting the selected component.

If no component is selected, the existing deletion method remains a no-op.

## Verification

- A GUI regression test selects a component, sends `Backspace`, and confirms that the component is removed.
- The same test confirms that `Delete` still removes a selected component.
- Existing deletion, undo, topology, solver, and GUI tests run unchanged.

## Release

Update the user instructions to name both keys and bump the application patch version from `0.3.0` to `0.3.1`.
