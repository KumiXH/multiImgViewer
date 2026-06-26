# Remote Image Compare Tool Design

## Summary

Build a Windows-native image comparison desktop application based on the existing multi-pane prototype. The new project keeps the core synchronized comparison workflow while replacing eager file and image loading with a source-agnostic, lazy-loading architecture that works with local folders, UNC network paths, and SSH/SFTP directories.

The primary user problem is poor responsiveness when viewing photos from Linux-hosted directories mounted over SMB on Windows. The first version should make directory browsing and file switching feel fast by separating filename discovery from image loading, moving all IO and decoding off the UI thread, and loading images only when the user selects a file.

## Goals

- Preserve the existing value of side-by-side comparison across 2 to 6 panes.
- Run as a Windows desktop application using a local GUI.
- Support three source types behind one consistent interface:
  - Local Windows folders
  - UNC network paths
  - Remote Linux folders accessed through SSH/SFTP
- Improve perceived performance by:
  - Listing filenames without reading full image content
  - Loading images only for the currently selected filename
  - Performing network IO and decode work in background workers
  - Caching only a small working set around the current file
- Support two file list modes:
  - Common files across all active panes
  - Primary pane as the master list, with missing files shown as empty/error in other panes
- Support SSH key and password authentication.
- Keep the project structured so it can be packaged for Windows later without major refactoring.

## Non-Goals For V1

- Thumbnail database generation for entire directories
- Persistent metadata or indexing database
- Photo editing or annotation features
- Tagging, favorites, or library management
- Cross-device sync of saved connections
- Smart content-based image matching

## User Experience

### Core workflow

1. The user opens the Windows desktop app.
2. The user configures 2 to 6 panes, each bound to a source:
   - local folder
   - UNC path
   - SSH/SFTP directory
3. The app scans active sources for supported image filenames and builds the file list using the selected comparison mode.
4. The right-side file list becomes browsable as soon as filename discovery completes.
5. When the user clicks a filename, each pane requests only that image from its own source.
6. Images load independently in the background. A pane can succeed, fail, or show a missing-file state without blocking other panes.
7. Zoom, pan, reset, previous/next navigation, and layout switching stay synchronized across visible panes.

### Performance expectations

- Opening a source should prioritize making the file list available quickly rather than eagerly decoding images.
- Selecting the next or previous filename should not freeze the UI.
- Loading should degrade gracefully when some sources are slow or unavailable.
- Re-visiting the current, previous, or next image should usually hit memory cache when recently viewed.

## Architecture

The application is split into clear layers so the GUI does not directly handle network or filesystem details.

### GUI layer

Responsible for:

- main window
- toolbars, file list, status bar
- pane widgets and synchronized view state
- user actions such as connect, select file, switch layout, and change comparison mode

The GUI layer must not perform blocking IO or image decode work.

### Session layer

Responsible for active application state:

- current layout
- active pane count
- pane-to-source bindings
- selected filename
- comparison mode
- shared zoom and pan state
- scan/load progress and error summaries

This layer coordinates GUI actions with background services.

### Source adapter layer

Provides a common contract for all source types. V1 includes:

- `LocalPathSource`
- `SftpSource`

Each adapter is responsible for:

- validating configuration
- listing candidate image paths
- reading a single file on demand
- reporting source display information
- translating source-specific failures into app-level errors

### Service layer

Contains the background work:

- catalog service for filename discovery
- image load service for on-demand image fetch and decode
- cache service for small in-memory reuse

## Source Model

Each pane binds to a configured source definition with these conceptual fields:

- `id`
- `kind` (`local`, `unc`, `sftp`)
- `display_name`
- `root_path`
- `recursive`
- `auth` for SFTP sources

### Local and UNC behavior

- Local drive paths and UNC paths both use the local adapter path implementation.
- UNC paths are treated as filesystem paths, not as separate protocol-level connections.
- Recursive scan is optional and follows the same path-relative filename rules as the original prototype.

### SFTP behavior

SFTP sources include:

- host
- port
- username
- remote root path
- authentication mode (`key` or `password`)
- optional private key path
- optional passphrase

V1 must support both authentication methods. Passwords must remain in memory only for the current running session unless the user explicitly requests persistence in a later version.

## Comparison Semantics

The app compares files by normalized relative path beneath each configured source root.

Example:

- Pane A root: `D:\photos\set1`
- Pane B root: `\\nas\photos\set2`
- Pane C root: `/srv/photos/set3` over SFTP

If all three contain `trip/day1/img_0012.jpg`, they are treated as the same comparison item.

### Comparison modes

#### Common files

Only filenames present in every active pane are shown.

#### Primary pane mode

The first active pane acts as the source of truth for the file list. Other panes try to resolve the same relative path. Missing files are shown as missing states inside the pane instead of being removed from the list.

## Loading Strategy

### Filename discovery

Filename discovery is separate from image loading.

- The catalog service enumerates candidate image paths using the active source adapters.
- No image bytes are loaded during filename discovery.
- The result is a normalized list of relative paths sorted by natural order.

### On-demand image loading

When the current filename changes:

1. The session layer issues one load request per visible pane.
2. The image load service cancels any stale request for that pane.
3. The service checks memory cache first.
4. On cache miss, it reads bytes from the source in a worker thread.
5. The bytes are decoded into a displayable image object off the UI thread when practical, then handed back to the GUI for final presentation.

Each pane updates independently, so one slow or failed source does not block the others.

### Caching

V1 uses a small in-memory LRU cache keyed by:

- source id
- relative path

Cache scope is intentionally small and optimized for sequential browsing. It should comfortably hold:

- current item
- previous item
- next item

Optional low-risk enhancement inside V1 if straightforward:

- prefetch previous and next filenames after the current image finishes loading

Prefetch must stay conservative and never flood the network with broad speculative reads.

## Concurrency Model

All slow work runs outside the GUI thread.

### Background tasks

- source scan tasks
- image read tasks
- image decode tasks when supported by the implementation path

### Task cancellation

If the user changes the selected filename before a pane finishes loading:

- the old pane request is marked stale
- stale results are discarded when they complete
- the pane only renders the most recent request result

This prevents out-of-order image flashes during rapid navigation.

### Connection reuse

The SFTP adapter should reuse active SSH/SFTP connections within a session when possible so repeated navigation does not reconnect for every file.

## Error Handling

Errors must be visible but non-disruptive during browsing.

### Error classes

- connection errors: unreachable host, refused port, timeout
- authentication errors: bad password, key rejected, passphrase failure
- path errors: root not found, file missing, permission denied
- content errors: unsupported image, corrupt file, decode failure
- lifecycle errors: request cancelled, source removed, session closed

### UI behavior

- Pane-local failures appear inside the affected pane.
- The status bar shows short summaries for the latest action.
- Modal dialogs are reserved for explicit user-triggered configuration failures, not routine per-file load issues.

Examples:

- Bad SSH credentials while adding a source can use a dialog or inline form error.
- One missing file during browsing should render a missing state in that pane and keep navigation working.

## Image Presentation

The new project keeps the comparison-friendly behavior from the prototype:

- synchronized zoom
- synchronized pan
- synchronized reset
- previous/next navigation
- multiple layouts: `1x2`, `1x3`, `2x2`, `2x3`

If same-name images differ in dimensions, the viewer should continue to present them in a consistent comparison frame. The initial implementation may preserve the existing behavior of scaling images to a shared canvas size for visual alignment, provided it does not add blocking work to the UI thread.

## Packaging And Runtime

### Development

The project should be created as a standard Python application with a clean dependency definition so it can be run locally through a virtual environment during development.

Recommended baseline:

- Python 3.11+
- `PySide6` for GUI
- a Python SSH/SFTP library with native support for password and key-based auth
- `pytest` for tests

### Distribution

The codebase should be organized so later Windows packaging through a tool such as `PyInstaller` is straightforward. This affects project structure but does not require packaging work in V1 implementation.

## Proposed Project Structure

This is the intended shape of the new project, not a strict final file list:

```text
app/
  main.py
  ui/
  controllers/
  models/
domain/
  sources.py
  session.py
  errors.py
services/
  catalog.py
  image_loader.py
  cache.py
sources/
  local_source.py
  sftp_source.py
tests/
  unit/
  integration/
docs/
  superpowers/
    specs/
```

The exact filenames may shift during implementation, but the responsibility boundaries should remain stable.

## Testing Strategy

### Unit tests

Focus on logic that can be exercised without a running GUI:

- natural sorting
- filename intersection and primary-pane list generation
- relative path normalization
- cache hit and eviction behavior
- stale request suppression
- source error mapping

### Adapter tests

- local and UNC behavior tested with temporary directories
- SFTP adapter behavior tested against a controlled SSH target

WSL can be used to simulate the SSH target during development and integration testing while still shipping the app as a native Windows GUI application.

### GUI and integration tests

Cover a small but meaningful set of flows:

- switching layouts
- selecting a filename triggers pane refresh
- UI remains responsive while a slow image load is in progress
- pane error states render correctly

## V1 Delivery Scope

V1 is complete when the user can:

- launch the app on Windows
- configure multiple panes with a mix of local, UNC, and SFTP sources
- choose between common-files mode and primary-pane mode
- browse the generated file list
- click or navigate through filenames without UI freezing
- compare loaded images with synchronized zoom and pan
- see clear per-pane feedback for missing files or source failures

V1 does not need to include:

- persistent connection profiles
- disk-backed thumbnail cache
- background full-library indexing
- metadata sidebars
- image manipulation tools

## Risks And Mitigations

### Risk: slow remote directory scans

Mitigation:

- keep discovery separate from image decode
- provide progress feedback
- support non-recursive mode by default if needed during implementation

### Risk: SSH library integration complexity on Windows

Mitigation:

- isolate SSH behavior behind the source adapter interface
- keep adapter tests focused and explicit
- validate against WSL-hosted SSH early during implementation

### Risk: UI thread stalls from image decode or oversized images

Mitigation:

- keep file reads off the UI thread
- minimize work in widget update paths
- verify responsiveness during integration testing with large images

### Risk: stale images appearing after rapid navigation

Mitigation:

- assign request identities
- discard old task completions
- test rapid next/previous navigation explicitly

## Implementation Direction

The first implementation phase should begin by scaffolding the new Python project and encoding the shared source interface, catalog logic, and pane request lifecycle in tests before building the full GUI around them.
