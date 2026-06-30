# mulitImgViewer / 多图远程对比查看器

`mulitImgViewer` 是一个面向 Windows 的多图对比查看工具，重点解决“在 Windows 上通过 Samba/网络盘查看 Linux 图片非常卡”的问题。它支持本地目录、UNC 网络路径、SSH/SFTP 远端目录，并提供多窗口同步缩放、平移、交换对比、容差图、会话记录等能力，适合图像数据集浏览、模型输出比对、超分结果检查和大图细节观察。

mulitImgViewer is a Windows-first multi-image comparison viewer for local folders, UNC shares, and SSH/SFTP remote folders. It is designed for fast visual comparison of image datasets, model outputs, and image-processing variants.

## 下载使用 / Download

推荐直接从 GitHub Releases 下载 Windows 发布包：

Download the Windows release package from GitHub Releases:

- [V1.1 Release](https://github.com/KumiXH/multiImgViewer/releases/tag/V1.1)

下载 `mulitImgViewer-V1.1-windows.zip` 后解压，运行：

After extracting `mulitImgViewer-V1.1-windows.zip`, run:

```text
mulitImgViewer.exe
```

注意：不要只拷贝单个 `EXE`。请保留整个解压目录，程序运行配置会保存在 `EXE` 同目录的 `.remote_image_compare` 文件夹中。

Keep the whole extracted folder together. Runtime settings are stored beside the executable in `.remote_image_compare`.

## 当前版本 / Current Version

当前版本：`V1.1`

Current version: `V1.1`

`V1.1` 重点更新：

- 容差图改为“灰度底图 + 红蓝叠加”，更容易观察差异落在原图的什么细节位置
- 容差图支持以较大尺寸图像作为底图，改善不同分辨率比较时的可读性
- 容差图同步查看性能优化：`NumPy`、后台线程、ROI、先低清后高清
- 修复同步查看时容差图与背景图不同步放大的问题

See [CHANGELOG.md](./CHANGELOG.md) for release history.

## 主要功能 / Features

- 支持本地目录、UNC 网络路径、SSH/SFTP 远端目录
- 支持把 Windows 文件夹直接拖到某个图片面板，快速绑定目录
- 支持 `1x2`、`1x3`、`2x2`、`2x3` 多种布局
- 支持鼠标滚轮缩放、鼠标位置为中心缩放、拖动平移
- 支持多面板同步缩放和平移，方便对齐观察细节
- 支持任意两个面板配对交换，并保持高亮状态，适合高频来回对比
- 支持上一张 / 下一张按钮，以及键盘左右方向键切换
- 支持手动保存浏览记录，并导出 / 导入对比配置，方便快速复现
- 支持浮动容差图窗口，可选择两个面板、设置阈值、切换算法，并显示对应坐标 RGB 值
- 支持窗口尺寸记忆，下次打开保持上次关闭时的大小

English summary: local/UNC/SFTP sources, drag-and-drop pane binding, multiple layouts, synchronized zoom/pan, paired pane swapping, keyboard navigation, manual session records, tolerance-map comparison, and persisted window sizes.

## 适合场景 / Use Cases

- 在 Windows 上查看 Linux 服务器中的图片，但不想通过 Samba 逐张慢慢打开
- 对比 HR / LR、模型输出、不同后处理版本、不同参数生成的图片
- 在多组目录里按同名文件同步浏览，快速观察差异
- 对 4K 或更大图片进行局部放大、同步移动和反复交换对比

Typical use cases include remote Linux image browsing from Windows, HR/LR dataset comparison, model-output QA, image-processing regression checks, and large-image detail inspection.

## 快速开始 / Quick Start

启动程序后，可以直接在空白面板中选择：

After launching the app, bind a pane by choosing:

- `选择本地目录`
- `选择服务器目录`

也可以把 Windows 文件夹直接拖到某个图片面板中进行绑定。

You can also drag a Windows folder directly onto an image pane.

SSH / SFTP 服务器信息可以在程序内保存，下次打开会自动读取。保存的配置文件位于：

SSH/SFTP profiles are saved locally and reloaded on next launch:

```text
.remote_image_compare\server_profiles.json
```

## 本地开发 / Development

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .[dev]
python -m pytest
python -m ruff check .
```

如果你有本地测试数据集，可以使用辅助脚本：

If you have a local dataset, use the helper script:

```powershell
.\tools\run_local_dataset.ps1 -Root "D:\SR数据集\livePhoto_out"
```

脚本会尝试绑定以下子目录：

The script binds these subfolders when they exist:

- `HR`
- `LR`
- `LR_aligned_adaptive_3d_lut`
- `LR_color_adaptive_3d_lut`

也可以手动传入多个目录：

You can also pass folders manually:

```powershell
.\.venv\Scripts\python.exe -m remote_image_compare.app `
  --source "D:\path\to\set_a" `
  --source "D:\path\to\set_b"
```

## 构建发布包 / Build Release

生成 Windows 目录版发布包：

Build a redistributable Windows folder:

```powershell
.\tools\build_release.ps1
```

输出目录：

Output folder:

```text
dist\mulitImgViewer\mulitImgViewer.exe
```

发布时请压缩整个 `dist\mulitImgViewer` 目录，而不是只发布单个 `EXE`。

When distributing, zip the whole `dist\mulitImgViewer` folder instead of shipping only the EXE.

## 技术栈 / Tech Stack

- Python 3.12
- PySide6 / Qt
- Paramiko SSH / SFTP
- NumPy
- PyInstaller
- pytest
- Ruff

## 项目状态 / Status

项目仍在持续迭代中，欢迎提交 Issue 或 PR。

This project is still evolving. Issues and pull requests are welcome.
