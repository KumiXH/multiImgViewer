# Remote Image Compare

## Development

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m pytest
python -m ruff check .
```

## Try It With The Local SR Dataset

If these folders exist:

- `D:\SR数据集\livePhoto_out\HR`
- `D:\SR数据集\livePhoto_out\LR`
- `D:\SR数据集\livePhoto_out\LR_aligned_adaptive_3d_lut`
- `D:\SR数据集\livePhoto_out\LR_color_adaptive_3d_lut`

run:

```powershell
.\tools\run_local_dataset.ps1 -Root "D:\SR数据集\livePhoto_out"
```

You can also launch the viewer manually with explicit folders:

```powershell
.\.venv\Scripts\python.exe -m remote_image_compare.app `
  --source "D:\SR数据集\livePhoto_out\HR" `
  --source "D:\SR数据集\livePhoto_out\LR" `
  --source "D:\SR数据集\livePhoto_out\LR_aligned_adaptive_3d_lut" `
  --source "D:\SR数据集\livePhoto_out\LR_color_adaptive_3d_lut"
```

## Interactive Binding

You can also launch the app without any `--source` arguments:

```powershell
.\.venv\Scripts\python.exe -m remote_image_compare.app
```

Then use the current UI flow:

- Click `服务器` to add, edit, test, and save SSH/SFTP server profiles.
- In an unbound pane, click `选择本地目录` or `选择服务器目录`.
- In a bound pane, click `清空` to unbind that pane.
- Dragging a local or UNC folder onto an image pane still works for quick binding.

For SSH testing in WSL, a working local test target can use:

- host: `127.0.0.1`
- port: `2222`
- username: `kumi`

Saved server profiles are written to `.remote_image_compare\server_profiles.json`.

## Build A Windows Release Folder

To produce a redistributable folder with `RemoteImageCompare.exe`:

```powershell
.\tools\build_release.ps1
```

The output will be created at:

- `dist\RemoteImageCompare\RemoteImageCompare.exe`

Runtime data is stored next to the executable:

- `dist\RemoteImageCompare\.remote_image_compare\server_profiles.json`
- `dist\RemoteImageCompare\.remote_image_compare\session_records.json`
- `dist\RemoteImageCompare\.remote_image_compare\window_state.json`

For release distribution, zip the whole `dist\RemoteImageCompare\` folder.
