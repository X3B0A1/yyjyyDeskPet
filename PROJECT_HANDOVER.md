# 项目交接文档 · 「美洲狮来了」桌面宠物

> 此文档是给下一位接手该项目的 AI 助手 / 开发者看的完整交接说明。
> 请先通读本文，再操作代码。所有关键逻辑都在 `main.py` 单文件内。

---

## 1. 项目是什么

Windows 桌面宠物应用（单文件 exe）。宠物（默认角色「美洲狮」）在屏幕范围内
缓慢爬行并带摇摆抖动；点击它或鼠标在它周围停留超时（有概率扑向鼠标）会触发
惊吓动画（循环播放惊吓帧）；支持多角色、每角色独立参数、托盘菜单、设置、
追随鼠标、暂停拖动、多开实例。

## 2. 文件结构

```
E:\sylaidesk\
├── main.py                 # 全部程序代码（唯一源码）
├── 0.png  c1.png  c2.png   # 内置默认角色素材（爬行1帧 + 惊吓2帧）
├── 美洲狮来了.spec          # PyInstaller 打包配置（可重新生成）
├── pet_config.json         # 全局配置（目前只有 follow_mouse）
├── characters.json         # 记录当前角色名 {"current": "..."}
├── characters\             # 角色数据目录（运行时生成/用户添加）
│   └── 美洲狮\             # 每个角色一个文件夹
│       ├── crawl_1.png…    # 爬行帧（crawl_N.ext）
│       ├── scare_1.png…    # 惊吓帧（scare_N.ext）
│       └── config.json     # 该角色数值参数 + face_direction
├── dist\美洲狮来了.exe      # 已打包成品（约 33MB，免 Python 运行）
├── 图片生成提示词.md         # 给图片生成 AI 的宣传图提示词
└── PROJECT_HANDOVER 文档    # 本文件
```

## 3. 依赖（打包进了 exe，运行端无需安装）

- 运行端：**无需任何安装**（PyInstaller onefile 已内置解释器+库+图片）。
- 开发端（仅构建需要）：Python 3.14 + `numpy` + `Pillow` + `pystray` +
  `pyinstaller`。全部为系统已装库，**不要重新下载**（用户网络慢）。
  注意：`pystray` 无 `__version__` 属性，别用该属性判断。

## 4. 构建命令

```
python -m PyInstaller --onefile --windowed --name "美洲狮来了" --add-data "0.png;." --add-data "c1.png;." --add-data "c2.png;." main.py
```

- `--add-data` 的 3 张图只用于首次启动时引导生成默认角色（bootstrap）。
- 打包前若 exe 被占用会失败，先结束进程 `Stop-Process -Name "美洲狮来了" -Force`。
- 测试运行：`python main.py --selftest`（构建后清 `build\`、`__pycache__\`）。

## 5. 配置系统（重要）

- **每角色数值配置**：`characters\<角色>\config.json`，含全部数值参数
  （见 PARAM_DEFS）以及 `face_direction`（"left"/"right"）。
  读取：`load_char_cfg(name)`；写入：`save_char_cfg(name, cfg)`。
  **`save_char_cfg` 会保留 `face_direction`，别弄丢它。**
- **全局配置**：`pet_config.json`，目前只有 `follow_mouse`。
  读取/写入：`load_global_cfg()` / `save_global_cfg(cfg)`。
- **当前角色**：`characters.json` 的 `current` 字段。
- 切换角色 = `_load_character(name)`，会重载 cfg、朝向、帧图、尺寸，并立即生效。
- 设置窗口的「保存/取消/恢复默认」都只作用于**当前角色**的数值。

## 6. 角色系统

- 角色 = `characters\<名字>\` 文件夹；帧文件命名 `crawl_N.ext` / `scare_N.ext`，
  按文件名自然排序（`natkey`）作为播放顺序，支持 png/jpg/bmp/gif/webp。
- 首次启动若 `characters\` 为空，自动从打包图片引导出「美洲狮」
  （1 爬行帧 + 2 惊吓帧）。
- 增：`add_character(name, crawl_files, scare_files, face_dir)`（复制文件并自动切换）。
- 改：`_confirm_edit`（改名=文件夹重命名；重新选图=`_replace_frames` 整组替换；
  朝向=`set_char_facing`）。
- 删：`_delete_char`（带二次确认；删除当前角色则自动切到第一个角色或重建美洲狮）。
- 缩略图缓存：`self._thumbs`，改名/换图后要 `pop` 掉对应 key。

## 7. 行为逻辑（main.py 内的状态机）

- `state`：`"crawl"` / `"pounce"` / `"scare"`，由 `tick()`（33ms after 循环）驱动。
- **爬行 crawl**：慢速直线 + 正弦摇摆（`wobble_amp/freq`）+ 随机转向 + 偶尔停顿；
  多爬行帧按 `crawl_fps` 循环。
- **镜像朝向**：`face_mirror = (向右移动) != (face_dir=="right")`。
  即图片正面默认朝左，朝右角色反过来。见 `_tick_crawl` / `_tick_pounce`。
- **惊吓 scare**：循环惊吓帧 + 随机抖动 `shake`，持续 `scare_duration`。
- **扑击 pounce**：鼠标在 `hover_radius` 内停留 `hover_time` 秒后按
  `pounce_chance`% 概率触发，快速冲向鼠标再惊吓。**之前修过一个 bug：不要调用
  不存在的 `_start_scare`，统一用 `trigger_scare()`。**
- **追随鼠标**：`follow_mouse=True` 时爬向鼠标，且关闭 hover 触发。
- **暂停 + 拖动**：暂停时 `tick` 直接 return（完全静止），按住左键拖动窗口；
  未暂停时单击（移动<5px）触发惊吓。处理在 `_on_lbutton/_on_drag/_on_drag_end`。
- **多开**：菜单「新建宠物」= 启动新进程（frozen 用 `os.startfile(sys.executable)`，
  否则 `subprocess.Popen([sys.executable, __file__])`）。

## 8. 参数（DEFAULTS，数值型在设置界面可调）

| key | 含义 | 默认 |
|---|---|---|
| crawl_speed | 爬行速度 px/s | 80 |
| crawl_fps | 爬行帧速率 帧/秒 | 4.0 |
| wobble_amp | 摇摆幅度 px | 12 |
| wobble_freq | 摇摆频率 Hz | 2.0 |
| scale | 显示大小 % | 55 |
| hover_radius | 鼠标感应半径 px | 150（上限=屏幕对角线，即全屏） |
| hover_time | 停留触发时间 s | 3.0 |
| pounce_chance | 扑向概率 % | 30 |
| pounce_speed | 扑向速度 px/s | 480 |
| scare_duration | 惊吓时长 s | 3.0 |
| frame_interval | 惊吓帧交替间隔 ms | 120 |
| shake | 惊吓抖动 px | 6 |
| follow_mouse | 追随鼠标（全局） | False |

## 9. UI 窗口

- 宠物主窗口：无边框、置顶、`-transparentcolor`（KEY=#010203）透明背景；
  透明像素用 `flatten_to_key` 与 KEY 预混合去黑边。**窗口尺寸跟随当前帧**
  （crawl/scare 帧大小不同），用 `cur_size` 而非固定 `size`。
- 右键菜单：暂停 / 追随鼠标 / 新建宠物 / 角色管理 / 设置 / 退出。
- 托盘（pystray）：同名菜单；图标=当前角色首帧。
- 设置窗口：深色主题、可调大小、内部滚动（canvas+scrollbar），滑块实时生效。
- 角色管理窗口：可调大小、卡片列表（缩略图+编辑/切换/删除）、添加按钮。
- 添加/编辑角色对话框：可调大小，含朝向单选（`_facing_row`）。
- 全局主题色：BG #1f2225、ACCENT #7cc4ff、琥珀值 #ffd479 等，见文件顶部常量。

## 10. 已知坑 / 注意事项

1. **缩放缓存**：改 scale 或换角色后必须清 `frame_photos`/`photo` 缓存并重设
   `cur_size`（`_scale_images` 已处理）。曾因不清缓存导致"缩图变裁切"。
2. **帧大小不同**：c1/c2 比 0.png 大，切换帧时窗口要跟着当前帧 resize，否则裁切。
3. **`_place` 会按 `cur_size` 做屏幕边缘 clamp**，晃动/抖动不会跑出屏幕。
4. **`_rebuild_char_cards` 在角色管理窗口未打开时**会直接 return（有守卫），
   测试/无 UI 场景别依赖它。
5. **DpiAwareness**：main() 开头 `SetProcessDpiAwareness(1)`，避免高分屏坐标错位。
6. **多实例写文件**：多个 exe 同跑时字符配置共享，切换角色会互相改 manifest，
   属预期行为。
7. `natural_size` 字段当前未使用，可留作后续。
8. 打包是 Windows-only（win32），别承诺跨平台。
9. `__pycache__`、`build\`、`dist\` 不要提交到 git。

## 11. 测试方法

- 快速自检：`python main.py --selftest`（30 帧后打印角色/帧数并退出）。
- 逻辑测试：直接 import main，构造 PetApp，用 `root.update()`+`sleep` 驱动事件循环，
  再调用内部方法（`add_character`、`_confirm_edit`、`trigger_scare` 等）断言状态。
- 注意：单进程内创建第二个 Tk/PetApp 会因前一个 `after` 回调残留报
  "invalid command name"，真实应用不会出现，仅测试脚本干扰。

## 12. 待办 / 可能的方向

- 宠物间同进程多窗口（目前是多进程多开）。
- 托盘图标随角色切换动态更新。
- 字符/角色配置加"全局锁"避免多实例写冲突。
- 更多惊吓触发方式、音效。
