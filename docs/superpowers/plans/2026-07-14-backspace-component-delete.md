# Backspace Component Deletion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete a selected component with either Backspace or Delete while preserving the existing deletion command path.

**Architecture:** Extend the existing `QAction` shortcut list instead of adding a second key-event handler. A GUI test drives real key presses through the main window, and release metadata documents the patch.

**Tech Stack:** Python 3.12, PySide6, pytest-qt, Ruff, mypy, PyInstaller.

## Global Constraints

- Both `Backspace` and `Delete` invoke the existing `_delete_selected` behavior.
- Text fields retain Qt's normal Backspace editing behavior.
- No component selection remains a no-op.
- Release version becomes `0.3.1`.

---

### Task 1: Keyboard deletion behavior

**Files:**
- Modify: `tests/gui/test_main_window.py`
- Modify: `src/circuitcanvas/ui/main_window.py`

**Interfaces:**
- Consumes: `MainWindow.delete_action` and `MainWindow._delete_selected()`.
- Produces: one action with `Delete` and `Backspace` shortcuts.

- [ ] **Step 1: Write the failing GUI test**

```python
@pytest.mark.parametrize("key", [Qt.Key.Key_Backspace, Qt.Key.Key_Delete])
def test_keyboard_delete_keys_remove_selected_component(qtbot, key) -> None:
    window = MainWindow(debounce_ms=0)
    qtbot.addWidget(window)
    component_id = window.add_component("resistor")
    window.scene.component_items[component_id].setSelected(True)

    qtbot.keyClick(window, key)

    assert component_id not in window.circuit.components
```

- [ ] **Step 2: Run the Backspace case and verify RED**

Run: `QT_QPA_PLATFORM=offscreen pytest -q tests/gui/test_main_window.py -k keyboard_delete`

Expected: the Backspace parameter fails because the current action only registers `Delete`.

- [ ] **Step 3: Register both shortcuts**

```python
self.delete_action.setShortcuts(
    [QKeySequence(Qt.Key.Key_Delete), QKeySequence(Qt.Key.Key_Backspace)]
)
```

- [ ] **Step 4: Run the GUI test and verify GREEN**

Run: `QT_QPA_PLATFORM=offscreen pytest -q tests/gui/test_main_window.py -k keyboard_delete`

Expected: both parameter cases pass.

- [ ] **Step 5: Commit the behavior**

```bash
git add src/circuitcanvas/ui/main_window.py tests/gui/test_main_window.py
git commit -m "feat: delete components with backspace"
```

### Task 2: Release documentation and verification

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`
- Modify: `src/circuitcanvas/__init__.py`
- Modify: `circuitcanvas.spec`

**Interfaces:**
- Consumes: existing package and application version metadata.
- Produces: documented `0.3.1` release metadata.

- [ ] **Step 1: Document both keys and bump patch versions**

Use this README wording:

```markdown
6. Select a component and use **Rotate** (or `R`), **Delete**/**Backspace**, the value field, or the logarithmic slider.
```

Set the package and bundle versions exactly as follows:

```toml
version = "0.3.1"
```

```python
__version__ = "0.3.1"
```

```python
"CFBundleShortVersionString": "0.3.1",
```

- [ ] **Step 2: Run complete verification**

```bash
ruff format --check .
ruff check .
mypy src
QT_QPA_PLATFORM=offscreen pytest -q
python -m build
python -m PyInstaller --clean --noconfirm circuitcanvas.spec
```

Expected: all commands exit successfully and the packaged app launches.

- [ ] **Step 3: Commit the release update**

```bash
git add README.md pyproject.toml src/circuitcanvas/__init__.py circuitcanvas.spec
git commit -m "docs: release CircuitCanvas 0.3.1"
```
