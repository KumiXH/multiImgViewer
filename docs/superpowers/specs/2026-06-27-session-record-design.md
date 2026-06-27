# Session Record Design

## Summary

This iteration adds a lightweight manual session record workflow to the remote image comparison tool. The user wants to preserve only meaningful comparison setups, not every intermediate adjustment. A saved record should capture the current comparison context, support local history inside the app, and allow export/import as JSON so the same setup can be restored later.

The feature is intentionally manual. The app must not auto-create history entries when the user changes panes, switches layout, or moves through images. A record only exists when the user explicitly saves one.

## Goals

- Add a manual `保存记录` workflow for the current comparison setup.
- Keep a local in-app list of saved records for later reuse.
- Support exporting a single record as JSON text or a `.json` file.
- Support importing a record from pasted JSON text or a `.json` file.
- Restore the saved layout mode, compare mode, and pane bindings from an imported or saved record.
- For remote pane bindings, store only `服务器名称 + 远端路径`.

## Non-Goals

- Auto-generated browsing history
- Saving current image index
- Saving pane swap state
- Saving zoom or pan state
- Exporting SSH passwords, private key passphrases, or other secrets
- Creating or editing SSH server profiles from imported records

## Product Decisions

### History creation

- Records are created only by explicit user action.
- The app does not save records automatically in the background.
- The app does not create a history item when a record is merely imported or applied.

### Saved state scope

Each record stores:

- user-provided record name
- save timestamp
- layout mode: `1 x 2`, `2 x 2`, or `2 x 3`
- compare mode: `共有文件` or `主目录基准`
- pane bindings for all bound panes

Each pane binding stores:

- pane index
- source type: local, UNC, or SFTP
- display name
- local or UNC root path for local-style bindings
- server profile name and remote path for SFTP bindings

The record does not store:

- current image filename or index
- pane swap pairing
- synchronized zoom/pan state
- server credentials

### Remote reference policy

Remote bindings are portable only when the target machine already has a matching saved server profile.

- Exported/imported records store only the server profile name and selected remote path.
- On import or apply, the app looks up the saved server profile by name.
- If a referenced server profile is missing locally, the app shows a clear error naming the missing profile and does not silently bind that pane.

## User Experience

### Toolbar entry point

Add a `记录` button to the top toolbar. It opens a small record workflow entry point with these actions:

- `保存当前记录`
- `查看记录`
- `导入记录`
- `导出当前记录`

The exact widget can be a dialog-first flow or a small menu, but the actions above must remain stable.

### Save current record

When the user chooses `保存当前记录`:

1. The app opens a small dialog.
2. The user enters a record name.
3. The app captures the current session snapshot.
4. The record is written to local storage.
5. The user sees lightweight confirmation.

If nothing is currently bound, saving is still allowed only if the resulting empty record is considered useful by the implementation. The recommended default is to block empty saves and ask the user to bind at least one pane first.

### View records

When the user chooses `查看记录`:

- The app shows a list of saved records.
- Each row displays:
  - record name
  - saved time
  - layout mode
  - compare mode
  - count of bound panes

Each record supports these actions:

- `应用`
- `复制 JSON`
- `导出文件`
- `删除`

### Apply record

Applying a record restores:

- layout mode
- compare mode
- pane bindings described by the record

Any panes not present in the record are cleared back to the unbound state.

If one or more remote server profiles are missing:

- the app keeps the apply flow visible
- the app lists which server names are missing
- already valid local bindings may still be applied, but this behavior must be explicit and consistent

The recommended behavior is partial apply with a warning, because it preserves useful local panes while clearly surfacing missing remote prerequisites.

### Export current record

The user can export:

- the current session as JSON
- or an existing saved record as JSON

Export options:

- copy JSON text to clipboard
- save JSON to a file

The exported payload should be formatted for readability with stable field names and indentation.

### Import record

The user can import a record by:

- pasting JSON text into a dialog
- choosing a `.json` file from disk

After validation succeeds:

- the app shows the parsed record summary
- the user confirms apply
- the app restores the saved state

If validation fails:

- the dialog stays open
- the app shows a short readable error

## Data Design

### Record schema

The record payload should be JSON with an explicit top-level version field for forward compatibility.

Recommended top-level shape:

- `version`
- `name`
- `saved_at`
- `layout_mode`
- `compare_mode`
- `panes`

Each pane entry should include:

- `pane_index`
- `source_kind`
- `display_name`
- `root_path` for local or UNC bindings
- `server_name` and `remote_path` for SFTP bindings

### Storage location

Use the same project-local hidden application directory pattern already used by server profile storage:

- `.remote_image_compare/session_records.json`

This keeps the persistence model consistent and easy to inspect or back up.

### Storage behavior

- Records are stored as a list under one JSON document.
- Records are sorted by saved time descending or by explicit insertion order, with newest first recommended for usability.
- Record names do not need to be globally unique, but each stored record should have a stable internal identifier.

## Architecture

### Domain layer

Add small immutable models for:

- session record
- pane binding snapshot

These models should be serialization-friendly and explicit about optional remote-only fields.

### Service layer

Add a new record store service responsible for:

- listing records
- saving a record
- deleting a record
- serializing a record to JSON text
- parsing JSON text into a record

This service should mirror the responsibilities and style of `ServerProfileStore`.

### Main window responsibilities

`MainWindow` should:

- capture the current session into a record snapshot
- apply a record snapshot back into the live UI
- coordinate toolbar actions and dialogs
- validate remote server availability during apply

`MainWindow` should not own raw JSON parsing or persistence details directly.

### Dialog layer

Add focused dialogs for:

- naming and saving a record
- browsing and acting on saved records
- importing JSON text or file content
- previewing export JSON when needed

These dialogs should stay lightweight and action-oriented, consistent with the current app style.

## Binding And Restore Semantics

### Local and UNC panes

When restoring a local or UNC pane:

- bind the saved path back to the original pane index
- restore the pane title from current source binding rules

### Remote panes

When restoring a remote pane:

- resolve the saved server name against locally saved server profiles
- if found, bind the saved remote path with that profile
- if missing, report the missing server name

### Compare mode and layout timing

Restore order should be:

1. set layout mode
2. set compare mode
3. clear panes not present in the record
4. bind panes from the record
5. refresh catalog
6. load the first available catalog item if any

This avoids mismatches between active pane count and restored bindings.

## Error Handling

### Save errors

- disk write failures show a concise error
- the save dialog remains open when appropriate

### Import errors

- invalid JSON shows a readable parsing message
- unsupported record version shows a version error
- missing required fields show a validation error

### Apply errors

- missing server profiles are reported by name
- missing local directories should produce a readable warning instead of crashing
- partially restorable records should not leave the app in an inconsistent half-reset state

## Testing Strategy

### Unit tests

- record store round-trips saved records
- record store exports stable JSON
- record store parses valid imported JSON
- record store rejects invalid or incomplete payloads
- record store preserves remote bindings without credentials

### Integration tests

- saving a record captures layout, compare mode, and bound panes
- applying a saved record restores pane bindings and toolbar state
- importing JSON restores a valid record
- applying a record with a missing server profile surfaces a readable error
- deleting a saved record removes it from the local record list

## Risks And Mitigations

### Risk: record format becomes brittle

Mitigation:

- add a top-level schema version
- keep field names explicit and stable
- centralize serialization in one service

### Risk: restore flow leaves stale panes behind

Mitigation:

- define a strict restore order
- clear panes not represented in the record
- test mixed local/remote restore cases

### Risk: import becomes unsafe or confusing

Mitigation:

- never import credentials
- validate before apply
- show missing server names clearly

## Delivery Scope

This iteration is complete when the user can:

- manually save the current comparison setup as a named record
- reopen and apply a saved record from inside the app
- export one record as JSON text or a `.json` file
- import a record from JSON text or file content
- restore layout mode, compare mode, and pane bindings
- receive a clear error when an imported record references a missing saved server profile
