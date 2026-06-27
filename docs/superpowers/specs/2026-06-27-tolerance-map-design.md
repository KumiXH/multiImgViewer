# Tolerance Map Floating Window Design

## Summary

This iteration adds a dedicated floating tolerance map tool for per-image visual difference analysis. The user wants a workflow similar to Beyond Compare picture comparison, but integrated into the existing multi-pane image viewer. The main window remains the primary viewing surface, while a separate always-on-top, non-modal floating window provides difference visualization, tolerance control, algorithm switching, and pixel-level RGB inspection.

The first version focuses on the currently selected image only. It compares exactly two chosen panes, builds a tolerance map, and keeps the analysis lightweight and interactive.

## Goals

- Add a non-modal, always-on-top floating tolerance window launched from the top toolbar.
- Allow choosing up to two image panes as comparison inputs.
- Show a tolerance map for the currently selected image only.
- Add a tolerance slider to recompute the map interactively.
- Support multiple difference calculation algorithms selectable in the floating window.
- Show synchronized coordinate and RGB inspection for both compared images.
- Support mouse interaction from both the main image panes and the floating tolerance map.
- Support zooming and panning inside the floating tolerance map window.

## Non-Goals

- Batch tolerance analysis across all files
- Exporting tolerance maps as image files
- Bidirectional zoom/pan synchronization back into the main panes
- More than two compared panes at once
- Persistent tolerance presets
- Remote server-side diff computation

## Product Decisions

### Window model

- The tolerance tool lives in a separate floating window.
- The window is always on top.
- The window is non-modal and does not block interaction with the main window.
- Closing the floating window does not affect the main compare session.

### Comparison scope

- The tolerance map is generated only for the current image selected in the main session.
- The user can choose exactly two panes for comparison.
- The UI may expose selection as checkboxes, but at most two panes can be active at once.
- If fewer than two panes are selected, the tolerance map area shows an instructional empty state.

### Size mismatch behavior

- If the two source images do not share the same dimensions, the app automatically scales them to the same comparison size before computing the tolerance map.
- The comparison is based on the scaled results, not cropped overlap.

### Difference calculation modes

The floating window exposes a calculation mode selector with these options:

- maximum single-channel difference
- average RGB difference
- Euclidean RGB distance

The implementation does not try to mimic Beyond Compare's undocumented internal formula exactly. Instead, it makes the calculation explicit and user-selectable.

### Tolerance coloring rule

Given the scalar difference value for each pixel:

- if difference `>` tolerance: color the pixel red
- if difference `<` tolerance: color the pixel blue
- if difference `=` tolerance: color the pixel gray

This rule is fixed for the first version.

### RGB and coordinate inspection

The floating window shows:

- current comparison coordinate
- left image RGB at that coordinate
- right image RGB at that coordinate
- computed scalar difference at that coordinate

Inspection updates when the mouse moves over:

- either of the two selected main-window panes
- the tolerance map image itself

If the hovered position falls outside valid source bounds after coordinate mapping, the status area shows a short out-of-range or unavailable state.

## User Experience

### Toolbar entry point

Add a `容差图` button to the main toolbar.

When clicked:

- if the floating window is closed, create and show it
- if it is already open, bring it to front and focus it

### Floating window layout

The floating window contains:

- pane selection controls
- difference algorithm selector
- tolerance slider
- tolerance numeric label
- image viewport for the tolerance map
- coordinate and RGB readout area

The tolerance map viewport should visually feel similar to the existing pane viewing surface, with room for zoom and pan.

### Pane selection

- Each available pane is represented by a selectable control.
- The user can select at most two panes.
- If the user tries to select a third pane, the UI should reject it predictably.
- The recommended behavior is to leave the previous two selections unchanged and show lightweight feedback.

Only panes that currently have an image loaded should be treated as valid analysis sources.

### Empty and error states

When the tolerance window cannot produce a map, it should show a short clear message:

- select two panes
- image missing
- current file not available in one pane
- tolerance map unavailable

Errors should stay inside the floating window and must not break the main viewer.

## Tolerance Map Behavior

### Data source

The tolerance map is derived from the currently loaded image content of the selected panes, not by reloading files from disk or SSH.

This keeps pane swapping and navigation behavior consistent with the rest of the app and avoids unnecessary network fetches.

### Refresh triggers

The tolerance map recomputes when any of these change:

- current file changes
- selected comparison panes change
- difference algorithm changes
- tolerance value changes
- one of the compared panes loads a different image

### Coordinate mapping

The tolerance viewport tracks its own zoom and pan state.

When the user hovers the tolerance map:

- convert viewport coordinates into tolerance-image coordinates
- map those coordinates to the normalized comparison space
- sample both resized comparison images at that location

When the user hovers a main pane:

- convert the pane hover point into source image coordinates
- normalize relative location within the displayed image
- map that normalized location into the resized comparison space
- update the floating window readout

This keeps RGB inspection meaningful even when image sizes differ and the tolerance map uses resized comparisons.

### Zoom and pan inside the floating window

The tolerance map supports:

- wheel zoom
- drag pan when zoomed in

This interaction affects only the floating window.

The main image panes keep their own existing synchronized zoom/pan behavior unchanged.

## Architecture

### UI layer

Add a dedicated floating tolerance window widget or dialog class that owns:

- pane selection controls
- tolerance slider
- algorithm selector
- tolerance map viewport
- RGB readout labels

Add a tolerance-map viewport widget with behavior parallel to the existing image pane viewport where practical, but specialized for analysis output and hover reporting.

### Main window responsibilities

`MainWindow` should:

- open and reuse the floating tolerance window
- provide current pane/image state to it
- notify it when navigation or pane image content changes
- forward or expose hover information from selected panes

The main window should not contain pixel-difference computation logic directly.

### Service layer

Add a focused tolerance computation service responsible for:

- resizing two source images to a common comparison size
- computing scalar difference values using the selected algorithm
- converting results to a colored tolerance map image
- sampling RGB and scalar difference values at normalized coordinates

This service should be deterministic and easily unit-testable without Qt window machinery.

### Domain layer

Add small explicit models for:

- tolerance algorithm mode
- tolerance comparison result metadata if needed
- sampled pixel inspection data if a structured object improves clarity

## Proposed File Changes

- Modify `src/remote_image_compare/ui/main_window.py`
  - add toolbar button
  - create and coordinate floating tolerance window
  - notify tolerance tool on image/navigation changes
- Modify `src/remote_image_compare/ui/pane_widgets.py`
  - expose hover or coordinate reporting hooks from loaded image panes
- Modify `src/remote_image_compare/domain/models.py`
  - add tolerance-mode enum and any lightweight analysis models
- Create `src/remote_image_compare/services/tolerance_map_service.py`
  - resize, compare, colorize, and sample tolerance data
- Modify `src/remote_image_compare/ui/dialogs.py` or create a new UI module if separation is cleaner
  - add floating tolerance window implementation
- Add tests in `tests/unit/test_tolerance_map_service.py`
  - algorithm, threshold coloring, resize, and sampling coverage
- Modify `tests/integration/test_main_window.py`
  - toolbar, floating window, selection, refresh, and keyboard-safe integration coverage

## Error Handling

### Invalid selection

- fewer than two selected panes: show empty-state message
- more than two requested: refuse the extra selection with clear UI behavior

### Missing images

- if one selected pane has no currently loaded image, the floating window shows a short unavailable message
- if the current file is missing in one selected pane, the map is not rendered for that state

### Resize or rendering failure

- failures stay contained in the floating window
- the window shows a short readable message instead of crashing

## Testing Strategy

### Unit tests

- maximum-channel mode computes expected scalar difference
- average mode computes expected scalar difference
- Euclidean mode computes expected scalar difference
- tolerance coloring uses red for greater than, blue for less than, gray for equal
- differently sized input images are resized to a common comparison size
- sampled coordinate returns both RGB tuples and the scalar difference

### Integration tests

- main toolbar exposes the tolerance button
- clicking the button opens a non-modal floating window
- selecting two panes produces a tolerance map for the current file
- changing tolerance value refreshes the analysis result
- changing algorithm refreshes the analysis result
- left/right navigation in the main window updates the floating analysis
- hovering a selected main pane updates RGB readout
- hovering the tolerance map updates RGB readout

## Risks And Mitigations

### Risk: image resize introduces confusing diff results

Mitigation:

- make algorithm and tolerance rules explicit
- surface the chosen mode clearly in the floating window
- keep the first version simple and deterministic

### Risk: hover coordinate mapping becomes inconsistent

Mitigation:

- normalize coordinates through one common mapping path
- keep sampling logic in a dedicated service helper
- cover mapping behavior with targeted tests

### Risk: floating window duplicates too much viewport logic

Mitigation:

- reuse existing interaction concepts where practical
- keep tolerance viewport responsibilities narrow
- avoid pushing tolerance-specific behavior into generic pane widgets unless needed

## Delivery Scope

This iteration is complete when the user can:

- click `容差图` to open a floating always-on-top analysis window
- choose two currently loaded panes
- adjust tolerance and switch algorithms
- see a colored tolerance map for the current image
- inspect coordinates and RGB values from either main panes or the tolerance map
- zoom and pan inside the tolerance map window without disturbing the main viewer
