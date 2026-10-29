# 美洲狮来了

一只会在你电脑桌面上散步的 Q 版美洲狮桌面宠物。它在屏幕上慢慢爬行、偶尔扑向鼠标、被点到会吓一跳。支持多角色、每个角色独立调节动作参数，还能自己添加喜欢的宠物。

当前版本内置 **tjm**，首次启动默认使用 tjm（两张爬行图、两张惊吓图，默认朝右、大小 50%）。美洲狮仍可在「角色」菜单中选择。升级时会添加 tjm，并保留已有的角色选择及自定义设置；已使用过旧版本的用户可在「角色」菜单切换到 tjm。

1.2.1 修复 Mac 上宠物不可见、设置窗口跟着移动的问题：宠物使用独立的 Cocoa 透明窗口，设置和角色管理窗口保持静止。打包检查会实际打开设置、移动宠物，并验证宠物显示及设置窗口位置。

程序运行时完全离线。支持 Windows 和 macOS；源码运行需要先安装 Python 和依赖。

![美洲狮来了](0.png)

---

## Windows 快速开始（下载即可玩）

1. 到仓库页面点击绿色 **Code** → **Download ZIP** 下载并解压；
2. 也可以直接下载打包好的程序：`dist/美洲狮来了.exe`；
3. **双击 `美洲狮来了.exe`** —— 一只美洲狮就会出现在你的桌面上。

> 如果你下载的是源码（`main.py` 等文件），运行方法见下文「源码运行」。

仓库中现有的 `.exe` 是旧的 Windows 版本，本次源码修改不会更新它。要使用更新后的功能，请从源码运行或重新打包。

## macOS 快速开始

安装 [python.org 的 Python 3.10+](https://www.python.org/downloads/macos/)（包含 Tk），下载并解压源码，然后在项目目录打开终端运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

宠物会显示在桌面上，屏幕顶部菜单栏提供操作入口。右键、触控板双指点击或 **Control＋点击** 宠物也能打开菜单。退出可选菜单中的「退出」，或使用 Command＋Q。

如果使用 Homebrew Python，需要安装与 Python 版本一致的 `python-tk`；可先用 `python3 -m tkinter` 检查窗口能否打开。建议使用新版 Tk 8.6 或更高版本。

macOS 的设置和角色保存在 `~/Library/Application Support/SylaiDesk/`，应用放入「应用程序」目录后仍可正常保存数据。要迁移已有角色，请先退出程序，再将原来的 `characters/`、`characters.json` 和 `pet_config.json` 复制到该目录。

---

## 怎么玩

| 操作 | 效果 |
|---|---|
| 点击宠物 | 它会吓一跳（播放惊吓动画） |
| 鼠标在宠物附近停留 | 有概率扑向你，再吓一跳 |
| 按住左键拖动 | 拖到屏幕任何位置放下，拖动时暂停移动 |
| 右键点击 / macOS Control＋点击 | 打开宠物菜单 |
| Windows 托盘 / macOS 顶部菜单栏图标 | 同样有完整菜单 |

### 右键菜单 / 托盘菜单

- **暂停** —— 宠物完全静止，方便拖动或挂机；
- **追随鼠标** —— 开启后宠物会一路爬向你；
- **新建宠物** —— 再开一只，可同时养多只；
- **角色** —— 直接切换已有角色（勾选当前角色）；
- **角色管理** —— 添加、编辑、删除角色；
- **设置** —— 调节当前宠物的动作参数；
- **退出** —— 关闭宠物。

---

## 添加你自己的宠物角色

想换只别的宠物？非常自由——**任何一组图片**都可以当角色。

1. 右键宠物 → **角色管理** → **添加宠物**；
2. 填写宠物名字；
3. 选择**爬行图片**（走路/爬行的几帧图）和**惊吓图片**（被吓到的几帧图）；
   - 可以一次多选（Windows 按住 `Ctrl`，macOS 按住 `Command`，连续选择用 `Shift`），也可以分多次追加；
   - 图片支持 png / jpg / bmp / gif / webp；
   - 帧图按文件名数字顺序播放，例如 `crawl_1.png`、`crawl_2.png`……
4. 选择它的**正面朝向**（朝左还是朝右），保存后自动切换过去。

之后就能在右键菜单 → **角色** 里随时切换。

> **小提示**：爬行图、惊吓图不一定要一样大。程序会自动把所有帧等比缩放到相同大小并对齐，所以混用不同尺寸的图也不会忽大忽小。

### 手动放图片（可选）

不想用「角色管理」界面的话，也可以直接放文件夹：

```
characters/
└── 我的宠物/           ← 文件夹名 = 角色名
    ├── crawl_1.png     ← 爬行帧（crawl_开头的数字）
    ├── crawl_2.png
    ├── scare_1.png     ← 惊吓帧（scare_开头的数字）
    └── config.json     ← 可选，角色参数
```

重启后新角色就会出现在菜单里。

Windows 的 `characters/` 在程序旁边；macOS 在 `~/Library/Application Support/SylaiDesk/characters/`。

---

## 设置项说明（设置窗口里可调）

| 参数 | 含义 |
|---|---|
| 爬行速度 | 爬得多快（像素/秒） |
| 爬行帧速率 | 走路动画每秒播放几帧 |
| 摇摆幅度 / 频率 | 走路时摇摆抖动的幅度和快慢 |
| 宠物大小 | 显示尺寸百分比 |
| 鼠标感应半径 | 鼠标离它多近会被发现 |
| 停留触发时间 | 鼠标停在附近多久会扑过来 |
| 扑向概率 | 触发扑向动作的概率 |
| 扑向速度 | 扑过来的速度 |
| 惊吓时长 | 吓一跳持续多久 |
| 帧交替间隔 | 惊吓动画两帧切换的快慢 |
| 惊吓抖动幅度 | 被吓到时抖得多厉害 |

每个角色独立保存自己的参数，改完只影响当前宠物。

---

## 源码运行

想从源码跑（比如自己改代码）：

1. 安装 [Python 3.10+](https://www.python.org/downloads/)；
2. 安装依赖：
   ```
   python -m pip install -r requirements.txt
   ```
3. 运行：
   ```
   python main.py
   ```

> 首次启动会自动创建角色目录，复制内置的 tjm 预设并生成美洲狮角色，默认选择 tjm。macOS 建议使用上面的虚拟环境运行方式。透明图片处理由 Pillow 完成，无需 NumPy。

## 打包应用

必须在目标系统上打包：在 Mac 上生成 `.app`，在 Windows 上生成 `.exe`，不能在 Windows 上直接生成 Mac 应用。

在已激活的虚拟环境中运行：

```bash
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm sylai.spec
```

- macOS：生成 `dist/美洲狮来了.app`，可以移到「应用程序」目录后双击启动。
- Windows：生成 `dist/美洲狮来了.exe`。
- Mac 构建默认匹配所用 Python 的架构；Apple Silicon 和 Intel 版本请分别在相应环境中构建验证。
- 本地构建不会配置 Developer ID 签名或 Apple 公证；公开分发前需自行完成签名和公证。

仓库还提供 GitHub Actions 工作流「Test and build desktop app」，可在 Actions 页面手动运行。它分别在 Windows 和 macOS 上测试并打包，完成后可下载对应系统和架构的构建产物；Mac 应用以 ZIP 保存，保留可执行权限。这需要先将修改推送到 GitHub，本地修改不会自动触发远程构建。

自动检查：`python -m unittest discover -s tests -v`。桌面自检：`python -m unittest discover -s tests -p gui_smoke.py -v`（会短暂显示宠物和设置窗口，使用临时角色目录）。

Mac 实机验收时请检查：透明背景无色块、菜单栏和 Control＋点击菜单可用、暂停/追随/角色切换有效、拖动后位置正常、新建宠物后退出原宠物不影响新宠物，以及重新启动后设置仍保留。

---

## 常见问题

**双击 exe 没反应？**
- 检查系统安全提示或杀毒软件是否拦截；
- 试试点右下角托盘图标，看看宠物是否躲在屏幕边角。

**想在多台电脑玩？** 直接把 `dist/美洲狮来了.exe` 拷过去就能用，不用装任何东西。

**Mac 上没有菜单栏图标？** 先用宠物右键菜单操作。确认已安装 `requirements.txt` 中的依赖；从终端启动可以查看托盘初始化错误。

**系统要求：** Windows 10 / 11（64 位）；macOS 版本要求取决于所用 Python、Tk 和打包环境。Mac 的窗口显示和菜单栏行为需要在目标系统上实测。

---

## 目录结构

```
├── main.py                # 程序源码
├── macos_pet.py           # Mac 原生宠物窗口和鼠标交互
├── 0.png / c1.png / c2.png # 内置默认角色素材
├── requirements.txt       # 运行依赖
├── requirements-build.txt # 打包依赖
├── sylai.spec             # Windows / macOS 打包配置
├── presets/tjm/           # 内置 tjm 图片和初始参数，打包时一并包含
├── tests/                 # 兼容性测试和桌面自检
├── dist/                  # 打包产物（exe 或 app）
└── characters/            # Windows 角色数据；Mac 角色数据在用户目录
```

---

Made with ❤️ · 祝玩得开心！
