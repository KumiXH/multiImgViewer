# Pane Binding And Remote Tree Design

## Summary

This iteration improves day-to-day usability for the remote image comparison tool by moving pane binding closer to the pane itself, adding SSH connection testing, supporting remote directory tree selection, and making unbinding explicit and lightweight.

The current workflow works functionally but still feels too configuration-heavy for repeated use. The user should be able to look at an empty pane and immediately understand how to bind it, test a server before saving it, browse a remote folder tree instead of manually typing paths, and clear a pane without affecting the rest of the session.

## Goals

- Add a `Test Connection` action to the SSH server profile dialog.
- Make unbound panes self-service by showing centered bind actions inside the pane.
- Support remote directory tree browsing over SSH/SFTP instead of manual remote path typing.
- Add a per-pane `Clear` action to remove a binding quickly.
- Keep local drag-and-drop binding working.
- Preserve the existing synchronized viewing behavior for panes that remain bound.

## Non-Goals

- Remote file thumbnail browsing
- Remote image preview before binding
- Background crawling of entire remote directory trees
- Auto-reconnect or connection pooling redesign
- Replacing the top toolbar server management flow

## User Experience

### Unbound pane state

When a pane has no bound source:

- The pane shows a neutral empty state instead of an image.
- The center of the pane contains two primary actions:
  - `选择本地目录`
  - `选择服务器目录`
- The bottom status line reads `未绑定目录`.
- The pane still accepts direct local or UNC directory drag-and-drop.

### Bound pane state

When a pane is bound:

- The pane title continues to show the source display name.
- A `清空` button appears at the top-right of the pane header row.
- Clicking `清空` removes the pane binding immediately and returns the pane to the unbound state.

### Server profile workflow

In the server profile dialog:

- The existing save flow remains.
- A new `测试连接` button appears beside `保存`.
- Clicking `测试连接` attempts an SSH connection using the current form values.
- The result is shown inline in the dialog:
  - success: short success message
  - failure: short, readable error message

The connection test validates host, port, username, and authentication. It does not require the default remote directory to exist.

### Remote directory selection

When the user chooses `选择服务器目录` from an unbound pane:

1. The user selects one saved server profile.
2. The app opens a remote directory picker dialog.
3. The dialog shows a directory tree for the selected server.
4. The tree loads children lazily when a directory is expanded.
5. The dialog displays the currently selected remote path.
6. The user clicks `绑定` to bind the selected directory to the pane.

The directory picker only shows directories, not image files. This keeps the tree focused and responsive.

## Binding Semantics

### Local binding

- Selecting `选择本地目录` opens the native directory picker.
- Choosing a directory binds that path to the pane immediately.
- The pane title is derived from the local path as it is today.

### Remote binding

- Binding uses a saved `SftpServerProfile` plus a chosen remote directory path.
- The pane title becomes `server_name:remote_path`.
- Successful binding triggers catalog refresh and first-item load if any images exist.

### Unbinding

- Clearing a pane removes its source object and source config from the active session.
- The pane image, title state, and status are reset to the unbound state.
- The file catalog is rebuilt from the remaining bound panes only.

If all panes become unbound:

- the file list is cleared
- the top filename label is cleared
- the current index resets to no selection

## Comparison Mode Behavior

### Common mode

Only currently bound panes participate in the intersection.

### Primary mode

The first currently bound visible pane becomes the effective primary pane.

If the original primary pane is cleared:

- the app automatically promotes the next bound pane in visible order
- the file list is rebuilt using that pane as the primary source

If no panes remain bound, the catalog becomes empty.

## Remote Directory Tree Design

### Data model

The remote tree dialog works with directory nodes only. Each node needs:

- display name
- full remote path
- whether children may exist
- whether children are already loaded

### Loading strategy

The dialog does not fetch the entire tree upfront.

- The root directory starts from:
  - the profile default root when present
  - otherwise `/`
- Expanding a node triggers a single SSH/SFTP directory listing for that path.
- Only subdirectories are added to the tree.
- Failures are attached to the dialog state and can be retried with `刷新`.

This keeps remote browsing usable for very large directory structures.

## Connection Testing Design

### Scope

Connection testing is a lightweight live probe:

- create SSH client
- attempt authentication
- optionally open SFTP session
- close cleanly

It should not mutate the saved profile or bind a pane.

### Result handling

The dialog should surface a short result label near the action buttons:

- success: `连接成功`
- failure examples:
  - `认证失败`
  - `主机不可达`
  - `连接超时`
  - `SFTP 初始化失败`

Detailed tracebacks are not shown in the UI.

## Error Handling

### Server profile dialog

- Validation errors keep the dialog open.
- Test failures keep the dialog open and show the message inline.
- Save should still work even if the user did not run a connection test.

### Remote tree dialog

- Tree load failures do not close the dialog.
- The dialog shows a short error and allows retry.
- An empty directory is valid and can still be bound.

### Pane binding outcomes

- Binding a directory with no supported images is allowed.
- Pane-local image load failures continue using the existing missing/error rendering behavior.

## Architecture

### UI layer

`ImagePaneWidget`

- owns the empty-state presentation
- exposes pane-local actions for:
  - local bind request
  - remote bind request
  - clear request

`ServerProfileDialog`

- adds connection test action and status feedback

`RemoteDirectoryDialog`

- owns server selection handoff result and remote tree picking UX

`MainWindow`

- responds to pane action signals
- orchestrates local bind, remote bind, clear, and catalog rebuild

### Service layer

Add a small SSH directory browsing / connection test service that:

- tests profile connectivity
- lists remote child directories for a given server and path

This should sit above the raw `SftpSource` path-reading implementation so the tree dialog can reuse connection logic without pretending to be an image source.

### Source layer

The SFTP adapter should expose a way to list subdirectories for arbitrary remote paths, or share a lower-level helper with the new tree service.

## Proposed File Changes

- Modify `src/remote_image_compare/ui/pane_widgets.py`
  - add empty-state actions
  - add clear button support
  - add reset-to-unbound behavior
- Modify `src/remote_image_compare/ui/main_window.py`
  - connect pane-local actions
  - support pane unbinding
  - rebuild catalog after bind/unbind
- Modify `src/remote_image_compare/ui/dialogs.py`
  - extend server profile dialog with connection test
  - add remote directory picker dialog
- Create `src/remote_image_compare/services/remote_browser_service.py`
  - SSH connectivity test
  - remote child directory listing
- Modify `src/remote_image_compare/domain/models.py`
  - add any small remote-tree node model only if needed
- Modify `src/remote_image_compare/sources/sftp_source.py`
  - expose reusable remote directory listing behavior if needed

## Testing Strategy

### Unit tests

- connection test service returns success for valid fake SSH setup
- connection test service maps failures to short messages
- remote browser service returns only subdirectories
- unbound/clear behavior resets pane state

### Integration tests

- unbound pane shows local and remote bind actions
- clearing a bound pane removes it from active catalog computation
- primary mode promotes the next bound pane after clear
- server profile dialog enables connection test feedback path
- remote directory picker loads tree nodes lazily from a fake service

## Risks And Mitigations

### Risk: remote tree browsing blocks the UI

Mitigation:

- load directory children on demand only
- keep each fetch scoped to a single expanded node
- show lightweight failure feedback instead of freezing

### Risk: pane widget becomes overloaded

Mitigation:

- keep pane signals narrow and action-oriented
- let `MainWindow` orchestrate binding logic
- avoid pushing network knowledge into pane widgets

### Risk: clearing panes breaks compare modes

Mitigation:

- explicitly define active-pane participation rules
- test common and primary mode rebuild behavior after clear

## Delivery Scope

This iteration is complete when the user can:

- save a server profile and test connectivity from the same dialog
- bind an empty pane directly from the pane itself
- browse and select remote directories from a tree
- clear any pane binding with a visible per-pane action
- continue using local drag-and-drop and synchronized viewing as before
