import ctypes
import json
import math
import os
import queue
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
from PIL import Image, ImageTk

KEY = "#010203"
BG = "#1f2225"
CARD = "#262b30"
HOVER = "#2e343b"
ACCENT = "#7cc4ff"
DANGER = "#e06c6c"
NEUTRAL = "#39424e"
BTN_PRIMARY = "#2f6fb8"
BTN_PRIMARY_H = "#3b82cc"

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")

DEFAULTS = {
    "crawl_speed": 80,        # px/s 爬行速度
    "crawl_fps": 4.0,         # 帧/秒 爬行帧速率
    "wobble_amp": 12,         # px   摇摆幅度
    "wobble_freq": 2.0,       # Hz   摇摆频率
    "scale": 55,              # %    宠物显示大小
    "hover_radius": 150,      # px   鼠标感应半径
    "hover_time": 3.0,        # s    停留触发时间
    "pounce_chance": 30,      # %    扑向概率
    "pounce_speed": 480,      # px/s 扑向速度
    "scare_duration": 3.0,    # s    惊吓时长
    "frame_interval": 120,    # ms   惊吓帧交替间隔
    "shake": 6,               # px   惊吓抖动幅度
    "follow_mouse": False,    # 追随鼠标
}

PARAM_DEFS = [
    ("crawl_speed", "爬行速度", 10, 300, 5),
    ("crawl_fps", "爬行帧速率", 1.0, 30.0, 0.5),
    ("wobble_amp", "摇摆幅度", 0, 40, 1),
    ("wobble_freq", "摇摆频率", 0.5, 6.0, 0.1),
    ("scale", "宠物大小", 20, 200, 5),
    ("hover_radius", "鼠标感应半径", 30, 400, 5),
    ("hover_time", "停留触发时间", 0.5, 10.0, 0.1),
    ("pounce_chance", "扑向概率", 0, 100, 5),
    ("pounce_speed", "扑向速度", 100, 1200, 20),
    ("scare_duration", "惊吓时长", 0.5, 10.0, 0.1),
    ("frame_interval", "帧交替间隔", 40, 500, 10),
    ("shake", "惊吓抖动幅度", 0, 20, 1),
]

FONT = ("Microsoft YaHei UI", 9)
FONT_BOLD = ("Microsoft YaHei UI", 9, "bold")


def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def config_path():
    return os.path.join(base_dir(), "pet_config.json")


def char_dir():
    return os.path.join(base_dir(), "characters")


def manifest_path():
    return os.path.join(base_dir(), "characters.json")


def resource(name):
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, name)
    return os.path.join(base_dir(), name)


CHAR_KEYS = [k for k in DEFAULTS if k != "follow_mouse"]


def char_config_path(name):
    return os.path.join(char_dir(), name, "config.json")


def load_global_cfg():
    cfg = {"follow_mouse": False}
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            cfg.update({k: v for k, v in json.load(f).items() if k in cfg})
    except Exception:
        pass
    return cfg


def save_global_cfg(cfg):
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump({"follow_mouse": bool(cfg.get("follow_mouse", False))},
                      f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_char_cfg(name):
    cfg = {k: DEFAULTS[k] for k in CHAR_KEYS}
    try:
        with open(char_config_path(name), "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg.update({k: v for k, v in data.items() if k in cfg})
    except Exception:
        pass
    return cfg


def save_char_cfg(name, cfg):
    face = get_char_facing(name)
    try:
        with open(char_config_path(name), "w", encoding="utf-8") as f:
            data = {k: cfg.get(k, DEFAULTS[k]) for k in CHAR_KEYS}
            data["face_direction"] = face
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_char_facing(name):
    try:
        with open(char_config_path(name), "r", encoding="utf-8") as f:
            d = json.load(f)
        v = d.get("face_direction", "left")
        return v if v in ("left", "right") else "left"
    except Exception:
        return "left"


def set_char_facing(name, direction):
    if direction not in ("left", "right"):
        direction = "left"
    try:
        with open(char_config_path(name), "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    d["face_direction"] = direction
    try:
        with open(char_config_path(name), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def list_characters():
    if not os.path.isdir(char_dir()):
        return []
    return [d for d in os.listdir(char_dir())
            if os.path.isdir(os.path.join(char_dir(), d))]


def flatten_to_key(img):
    arr = np.asarray(img.convert("RGBA"), dtype=np.float32)
    a = arr[..., 3:4] / 255.0
    key = np.array([0x01, 0x02, 0x03, 255], dtype=np.float32)
    out = arr * a + key * (1.0 - a)
    return Image.fromarray(out[..., :3].astype(np.uint8), "RGB")


def natkey(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def merge_unique(a, b):
    seen = set()
    out = []
    for x in list(a) + list(b):
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def load_frames(folder, prefix):
    files = [f for f in os.listdir(folder)
             if f.startswith(prefix + "_")
             and os.path.splitext(f)[1].lower() in IMAGE_EXTS]
    files.sort(key=natkey)
    frames = []
    for f in files:
        try:
            frames.append(Image.open(os.path.join(folder, f)).convert("RGBA"))
        except Exception:
            pass
    if not frames:
        frames = [Image.new("RGBA", (64, 64), (30, 30, 30, 255))]
    return frames


def mk_button(parent, text, command, kind="neutral"):
    if kind == "primary":
        bg, ah, fg = BTN_PRIMARY, BTN_PRIMARY_H, "#ffffff"
    elif kind == "danger":
        bg, ah, fg = "#8c3b3b", DANGER, "#ffffff"
    else:
        bg, ah, fg = NEUTRAL, "#45505e", "#ffffff"
    return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                     activebackground=ah, activeforeground="#ffffff",
                     relief="flat", bd=0, padx=14, pady=5, cursor="hand2",
                     font=FONT)


class PetApp:
    def __init__(self):
        self.cmd_q = queue.Queue()
        self.state = "crawl"
        self.state_until = 0.0
        self.running = True
        self.paused = False
        self._dragging = False
        self._press_x = 0
        self._press_y = 0
        self._win_offset = (0, 0)
        self.settings_win = None
        self.char_mgr = None
        self.add_dlg = None
        self.edit_dlg = None
        self._styled = False
        self._thumbs = {}

        self._ensure_characters()
        self.char_name = self._load_current()
        self._load_character(self.char_name)

        self.angle = random.uniform(0, 2 * math.pi)
        self.phase = 0.0
        self.next_think = time.monotonic() + random.uniform(1.5, 3.5)
        self.idle_until = 0.0
        self.hover_since = None
        self.pounce_target = None
        self.next_frame = 0.0
        self.face_mirror = False
        self._drag_off = None

        self._build()
        self._setup_tray()
    def _ensure_characters(self):
        os.makedirs(char_dir(), exist_ok=True)
        if not list_characters():
            folder = os.path.join(char_dir(), "美洲狮")
            os.makedirs(folder, exist_ok=True)
            shutil.copy2(resource("0.png"), os.path.join(folder, "crawl_1.png"))
            shutil.copy2(resource("c1.png"), os.path.join(folder, "scare_1.png"))
            shutil.copy2(resource("c2.png"), os.path.join(folder, "scare_2.png"))

    def _load_current(self):
        try:
            with open(manifest_path(), "r", encoding="utf-8") as f:
                name = json.load(f).get("current")
            if name and os.path.isdir(os.path.join(char_dir(), name)):
                return name
        except Exception:
            pass
        chars = list_characters()
        return chars[0] if chars else "美洲狮"

    def _load_character(self, name):
        folder = os.path.join(char_dir(), name)
        self.char_name = name
        self.crawl_frames = load_frames(folder, "crawl")
        self.scare_frames = load_frames(folder, "scare")
        n_c = len(self.crawl_frames)
        all_frames = self.crawl_frames + self.scare_frames
        ref = max(max(f.width, f.height) for f in all_frames)
        resized = []
        for f in all_frames:
            if f.width >= f.height:
                nw, nh = ref, max(1, round(f.height * ref / f.width))
            else:
                nw, nh = max(1, round(f.width * ref / f.height)), ref
            resized.append(f.resize((nw, nh), Image.LANCZOS))
        canvas_w = max(r.width for r in resized)
        canvas_h = max(r.height for r in resized)

        def norm(r):
            canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            canvas.paste(r, ((canvas_w - r.width) // 2, canvas_h - r.height))
            return canvas

        self.crawl_frames = [norm(r) for r in resized[:n_c]]
        self.scare_frames = [norm(r) for r in resized[n_c:]]
        self.natural_size = (canvas_w, canvas_h)
        self.cfg = load_char_cfg(name)
        self.cfg["follow_mouse"] = load_global_cfg().get("follow_mouse", False)
        self.face_dir = get_char_facing(name)
        self.pounce_speed = self.cfg["pounce_speed"]
        if getattr(self, "follow_var", None):
            self.follow_var.set(self.cfg["follow_mouse"])
        self.crawl_idx = 0
        self.scare_idx = 0
        self.crawl_t = 0.0
        self._scale_images()
        try:
            with open(manifest_path(), "w", encoding="utf-8") as f:
                json.dump({"current": name}, f, ensure_ascii=False)
        except Exception:
            pass
        if hasattr(self, "label"):
            self._set_frame(f"c{self.crawl_idx}", mirrored=self.face_mirror)

    def _save_all(self):
        save_char_cfg(self.char_name, self.cfg)
        save_global_cfg(self.cfg)

    def add_character(self, name, crawl_files, scare_files, face_dir="left"):
        folder = os.path.join(char_dir(), name)
        os.makedirs(folder)
        for i, f in enumerate(crawl_files, 1):
            ext = os.path.splitext(f)[1].lower()
            shutil.copy2(f, os.path.join(folder, f"crawl_{i}{ext}"))
        for i, f in enumerate(scare_files, 1):
            ext = os.path.splitext(f)[1].lower()
            shutil.copy2(f, os.path.join(folder, f"scare_{i}{ext}"))
        set_char_facing(name, face_dir)
        self._load_character(name)

    def _thumb_photo(self, name):
        key = "th_" + name
        if key in self._thumbs:
            return self._thumbs[key]
        ph = None
        try:
            folder = os.path.join(char_dir(), name)
            files = [f for f in os.listdir(folder)
                     if f.startswith("crawl_")
                     and os.path.splitext(f)[1].lower() in IMAGE_EXTS]
            if files:
                img = Image.open(os.path.join(folder, files[0])).convert("RGBA")
                img.thumbnail((52, 52), Image.LANCZOS)
                ph = ImageTk.PhotoImage(flatten_to_key(img))
        except Exception:
            ph = None
        self._thumbs[key] = ph
        return ph

    # ---------- 窗口构建 ----------
    def _build(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", KEY)
        self.root.configure(bg=KEY)
        self.root.attributes("-toolwindow", True)
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

        self.label = tk.Label(self.root, bg=KEY, bd=0, cursor="hand2")
        self.label.pack()
        self.label.bind("<Button-1>", self._on_lbutton)
        self.label.bind("<B1-Motion>", self._on_drag)
        self.label.bind("<ButtonRelease-1>", self._on_drag_end)
        self.label.bind("<Button-3>", self._popup_menu)
        self.root.bind("<Configure>", self._on_configure)

        self.follow_var = tk.BooleanVar(value=self.cfg["follow_mouse"])
        self.pause_var = tk.BooleanVar(value=False)
        self.char_radio = tk.StringVar(value=self.char_name)
        self.char_menu = tk.Menu(self.root, tearoff=0)
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_checkbutton(label="暂停", variable=self.pause_var,
                                  command=self._toggle_pause)
        self.menu.add_separator()
        self.menu.add_checkbutton(label="追随鼠标", variable=self.follow_var,
                                  command=self._toggle_follow)
        self.menu.add_command(label="新建宠物", command=self.launch_new_instance)
        self.menu.add_cascade(label="角色", menu=self.char_menu)
        self.menu.add_command(label="角色管理", command=self.open_character_manager)
        self.menu.add_separator()
        self.menu.add_command(label="设置", command=self.open_settings)
        self.menu.add_command(label="退出", command=self.shutdown)
        self._rebuild_char_menu()

        w, h = self.size
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        self.pos = [random.uniform(0, self.screen_w - w),
                    random.uniform(0, self.screen_h - h)]
        self._set_frame("c0", mirrored=False)
        self.root.geometry(f"{w}x{h}+{int(self.pos[0])}+{int(self.pos[1])}")

        self.last = time.monotonic()
        self.root.after(0, self.tick)

    def _scale_images(self):
        s = self.cfg["scale"] / 100.0
        self.scaled = {}
        for i, img in enumerate(self.crawl_frames):
            self.scaled[f"c{i}"] = img.resize(
                (max(1, int(img.width * s)), max(1, int(img.height * s))),
                Image.LANCZOS)
        for i, img in enumerate(self.scare_frames):
            self.scaled[f"s{i}"] = img.resize(
                (max(1, int(img.width * s)), max(1, int(img.height * s))),
                Image.LANCZOS)
        self.size = self.scaled["c0"].size
        self.frame_photos = {}
        if hasattr(self, "label"):
            self._set_frame(self.cur_key[0], mirrored=self.cur_key[1])
            self._clamp()
            self._place(self.pos)

    def _set_frame(self, key, mirrored=False):
        ck = (key, mirrored)
        if ck not in self.frame_photos:
            img = self.scaled[key]
            if mirrored:
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            self.frame_photos[ck] = ImageTk.PhotoImage(flatten_to_key(img))
        self.label.configure(image=self.frame_photos[ck])
        self.cur_key = ck
        self.cur_size = (self.frame_photos[ck].width(),
                         self.frame_photos[ck].height())

    def _popup_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    # ---------- 暂停 / 拖动 ----------
    def _toggle_pause(self):
        self.paused = bool(self.pause_var.get())
        self.hover_since = None
        self._refresh_tray_menu()

    def _toggle_pause_tray(self):
        self.paused = not self.paused
        self.pause_var.set(self.paused)
        self.hover_since = None
        self._refresh_tray_menu()

    def _on_lbutton(self, event):
        self._press_x, self._press_y = event.x_root, event.y_root
        self._win_offset = (event.x_root - self.root.winfo_x(),
                            event.y_root - self.root.winfo_y())
        self._drag_off = self._win_offset
        self._dragging = self.paused

    def _on_drag(self, event):
        if not self._dragging:
            return
        w, h = self.cur_size
        nx = max(0, min(self.screen_w - w, event.x_root - self._win_offset[0]))
        ny = max(0, min(self.screen_h - h, event.y_root - self._win_offset[1]))
        self.pos[0], self.pos[1] = float(nx), float(ny)
        self.root.geometry(f"{w}x{h}+{int(nx)}+{int(ny)}")

    def _on_drag_end(self, event):
        moved = math.hypot(event.x_root - self._press_x,
                           event.y_root - self._press_y) > 5
        if not self.paused and not self._dragging and not moved:
            self.trigger_scare()
        self._dragging = False

    def _on_configure(self, event):
        if self.paused and self._dragging:
            self.pos[0] = float(self.root.winfo_x())
            self.pos[1] = float(self.root.winfo_y())

    # ---------- 托盘 ----------
    def _setup_tray(self):
        try:
            import pystray
            icon_img = self.crawl_frames[0].resize((64, 64), Image.LANCZOS)
            self.tray = pystray.Icon(
                "sylai_pet", icon_img, "美洲狮来了",
                menu=pystray.Menu(
                    pystray.MenuItem(
                        "暂停", lambda: self._toggle_pause_tray(),
                        checked=lambda item: self.paused),
                    pystray.MenuItem(
                        "追随鼠标", lambda: self._toggle_follow(),
                        checked=lambda item: self.cfg["follow_mouse"]),
                    pystray.MenuItem(
                        "新建宠物", lambda: self.launch_new_instance()),
                    pystray.MenuItem(
                        "角色",
                        self._tray_char_menu()),
                    pystray.MenuItem(
                        "角色管理", lambda: self.cmd_q.put("charmgr")),
                    pystray.MenuItem("设置", lambda: self.cmd_q.put("settings")),
                    pystray.MenuItem("退出", lambda: self.cmd_q.put("quit")),
                ),
            )
            self.tray.visible = True
            threading.Thread(target=self.tray.run, daemon=True).start()
        except Exception:
            self.tray = None

    def _refresh_tray_menu(self):
        if getattr(self, "tray", None):
            try:
                self.tray.update_menu()
            except Exception:
                pass

    def _rebuild_char_menu(self):
        if not getattr(self, "char_menu", None):
            return
        self.char_menu.delete(0, "end")
        self.char_radio.set(self.char_name)
        for name in sorted(list_characters()):
            self.char_menu.add_radiobutton(
                label=name, value=name, variable=self.char_radio,
                command=lambda n=name: self._switch_to(n))

    def _tray_char_menu(self):
        import pystray
        try:
            return pystray.Menu(*[
                pystray.MenuItem(
                    name,
                    lambda n=name: self.cmd_q.put(("switch", n)),
                    checked=lambda item, n=name: self.char_name == n,
                    radio=True)
                for name in sorted(list_characters())
            ])
        except Exception:
            return pystray.Menu()

    def _toggle_follow_tray(self):
        self.cfg["follow_mouse"] = not self.cfg["follow_mouse"]
        self.follow_var.set(self.cfg["follow_mouse"])
        save_global_cfg(self.cfg)
        self._refresh_tray_menu()

    def launch_new_instance(self):
        try:
            if getattr(sys, "frozen", False):
                os.startfile(sys.executable)
            else:
                subprocess.Popen([sys.executable, os.path.abspath(__file__)])
        except Exception:
            pass

    # ---------- 逻辑 ----------
    def tick(self):
        if not self.running:
            return
        now = time.monotonic()
        dt = min(now - self.last, 0.1)
        self.last = now
        self._drain_queue()

        if self.paused:
            self.hover_since = None
            self.root.after(33, self.tick)
            return

        if self.state == "crawl":
            self._tick_crawl(now, dt)
        elif self.state == "pounce":
            self._tick_pounce(now, dt)
        elif self.state == "scare":
            self._tick_scare(now)

        self._check_hover(now)
        self.root.after(33, self.tick)

    def _tick_crawl(self, now, dt):
        self.phase += 2 * math.pi * self.cfg["wobble_freq"] * dt
        if now >= self.idle_until:
            if self.cfg["follow_mouse"]:
                self._follow_mouse(now)
            elif now >= self.next_think:
                self.next_think = now + random.uniform(1.5, 3.5)
                if random.random() < 0.22:
                    self.idle_until = now + random.uniform(0.6, 1.3)
                else:
                    self.angle += random.uniform(-1.0, 1.0)
            if now >= self.idle_until:
                speed = self.cfg["crawl_speed"]
                self.pos[0] += math.cos(self.angle) * speed * dt
                self.pos[1] += math.sin(self.angle) * speed * dt
                self._clamp()

        if len(self.crawl_frames) > 1:
            interval = 1.0 / max(0.5, self.cfg["crawl_fps"])
            self.crawl_t += dt
            while self.crawl_t >= interval:
                self.crawl_t -= interval
                self.crawl_idx = (self.crawl_idx + 1) % len(self.crawl_frames)

        wob = math.sin(self.phase) * self.cfg["wobble_amp"]
        perp = self.angle + math.pi / 2
        off = (math.cos(perp) * wob, math.sin(perp) * wob)
        self._place(self.pos, off)
        self.face_mirror = (math.cos(self.angle) > 0) != (self.face_dir == "right")
        self._set_frame(f"c{self.crawl_idx}", mirrored=self.face_mirror)

    def _follow_mouse(self, now):
        try:
            mx, my = self.root.winfo_pointerxy()
        except Exception:
            return
        w, h = self.cur_size
        cx, cy = self.pos[0] + w / 2, self.pos[1] + h / 2
        dx, dy = mx - cx, my - cy
        d = math.hypot(dx, dy)
        if d < 50:
            self.idle_until = now + 0.3
            return
        ta = math.atan2(dy, dx)
        diff = (ta - self.angle + math.pi) % (2 * math.pi) - math.pi
        self.angle += max(-3.2, min(3.2, diff * 4 * 0.033))

    def _tick_pounce(self, now, dt):
        if not self.pounce_target:
            self.trigger_scare()
            return
        tx, ty = self.pounce_target
        w, h = self.cur_size
        cx, cy = self.pos[0] + w / 2, self.pos[1] + h / 2
        dx, dy = tx - cx, ty - cy
        dist = math.hypot(dx, dy)
        if dist < 14 or now >= self.state_until:
            self.trigger_scare()
            return
        v = self.pounce_speed * dt / dist
        self.pos[0] += dx * v
        self.pos[1] += dy * v
        self.angle = math.atan2(dy, dx)
        self._clamp()
        self._place(self.pos)
        self.face_mirror = (dx > 0) != (self.face_dir == "right")
        self._set_frame(f"c{self.crawl_idx}", mirrored=self.face_mirror)

    def _tick_scare(self, now):
        if now >= self.state_until:
            self.state = "crawl"
            self.next_think = now + random.uniform(0.5, 1.5)
            self._set_frame(f"c{self.crawl_idx}", mirrored=self.face_mirror)
            return
        if now >= self.next_frame:
            self.next_frame = now + self.cfg["frame_interval"] / 1000.0
            self.scare_idx = (self.scare_idx + 1) % len(self.scare_frames)
        shake = self.cfg["shake"]
        sx = random.uniform(-shake, shake) if shake else 0
        sy = random.uniform(-shake, shake) if shake else 0
        self._place(self.pos, (sx, sy))
        self._set_frame(f"s{self.scare_idx}")

    def _place(self, pos, offset=(0.0, 0.0)):
        w, h = self.cur_size
        x = max(0, min(self.screen_w - w, pos[0] + offset[0]))
        y = max(0, min(self.screen_h - h, pos[1] + offset[1]))
        self.root.geometry(f"{w}x{h}+{int(x)}+{int(y)}")

    def _clamp(self):
        w, h = self.cur_size
        self.pos[0] = max(0.0, min(self.screen_w - w, self.pos[0]))
        self.pos[1] = max(0.0, min(self.screen_h - h, self.pos[1]))

    def _check_hover(self, now):
        if self.cfg["follow_mouse"] or self.state != "crawl":
            self.hover_since = None
            return
        try:
            mx, my = self.root.winfo_pointerxy()
        except Exception:
            return
        w, h = self.cur_size
        cx, cy = self.pos[0] + w / 2, self.pos[1] + h / 2
        dist = math.hypot(mx - cx, my - cy)
        r = self.cfg["hover_radius"]
        if dist <= r:
            if self.hover_since is None:
                self.hover_since = now
            elif now - self.hover_since >= self.cfg["hover_time"]:
                self.hover_since = None
                if random.random() * 100 < self.cfg["pounce_chance"]:
                    self.trigger_pounce((mx, my))
        else:
            self.hover_since = None

    # ---------- 触发 ----------
    def trigger_scare(self):
        now = time.monotonic()
        self.state = "scare"
        self.state_until = now + self.cfg["scare_duration"]
        self.next_frame = now + self.cfg["frame_interval"] / 1000.0
        self.scare_idx = 0
        self.hover_since = None

    def trigger_pounce(self, target):
        self.pounce_target = target
        self.pounce_speed = self.cfg["pounce_speed"]
        self.state = "pounce"
        self.state_until = time.monotonic() + 2.0
        self.hover_since = None

    # ---------- 追随开关 ----------
    def _toggle_follow(self):
        self.cfg["follow_mouse"] = bool(self.follow_var.get())
        save_global_cfg(self.cfg)
        self._refresh_tray_menu()

    # ---------- 样式 ----------
    def _ensure_styles(self):
        if self._styled:
            return
        self._styled = True
        try:
            st = ttk.Style()
            try:
                st.theme_use("clam")
            except Exception:
                pass
            st.configure("Pet.Horizontal.TScale", background=BG,
                         troughcolor="#3a3f44", bordercolor=BG,
                         lightcolor=BG, darkcolor=BG,
                         sliderrelief="flat", sliderlength=14)
        except Exception:
            pass

    @staticmethod
    def _fmt(v):
        return f"{v:g}"

    # ---------- 设置窗口 ----------
    def open_settings(self):
        if self.settings_win and self.settings_win.winfo_exists():
            self.settings_win.lift()
            return
        self._ensure_styles()
        win = tk.Toplevel(self.root)
        win.title("美洲狮来了 · 设置")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.minsize(420, 460)
        win.attributes("-topmost", True)
        win.transient(self.root)
        self.settings_win = win
        self._sliders = {}

        header = tk.Frame(win, bg=BG)
        header.pack(fill="x", padx=18, pady=(16, 2))
        tk.Label(header, text="美洲狮来了", font=("Microsoft YaHei UI", 15, "bold"),
                 bg=BG, fg=ACCENT).pack(side="left")
        tk.Label(header, text="参数设置", font=("Microsoft YaHei UI", 9),
                 bg=BG, fg="#8a919a").pack(side="left", padx=(10, 0), pady=(5, 0))

        mid = tk.Frame(win, bg=BG)
        mid.pack(fill="both", expand=True, padx=18, pady=(8, 0))
        canvas = tk.Canvas(mid, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(mid, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas, bg=BG)
        body.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        item = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        body.columnconfigure(0, weight=1)

        max_hover = int((self.screen_w ** 2 + self.screen_h ** 2) ** 0.5)
        for i, (key, label, lo, hi, res) in enumerate(PARAM_DEFS):
            if key == "hover_radius":
                hi = max_hover
            row = tk.Frame(body, bg=BG)
            row.grid(row=i, column=0, sticky="ew", pady=3)
            tk.Label(row, text=label, bg=BG, fg="#d6dae0", width=13, anchor="w",
                     font=FONT).pack(side="left")
            var = tk.DoubleVar(value=self.cfg[key])
            val = tk.Label(row, text=self._fmt(self.cfg[key]), bg=BG, fg="#ffd479",
                           width=6, anchor="e", font=FONT_BOLD)
            val.pack(side="right", padx=(8, 0))
            ttk.Scale(row, from_=lo, to=hi, variable=var,
                      style="Pet.Horizontal.TScale",
                      command=lambda x, k=key, v=var, l=val, lo_=lo, hi_=hi,
                                     r=res: self._on_param(k, v, l, lo_, hi_, r)
                      ).pack(side="left", fill="x", expand=True, padx=(6, 6))
            self._sliders[key] = (var, val)

        tk.Frame(body, bg="#3a3f44", height=1).grid(
            row=len(PARAM_DEFS), column=0, sticky="ew", pady=10)
        foot = tk.Frame(body, bg=BG)
        foot.grid(row=len(PARAM_DEFS) + 1, column=0, sticky="ew", pady=(0, 6))
        self.follow_var.set(self.cfg["follow_mouse"])
        tk.Checkbutton(foot, text="追随鼠标（宠物爬向鼠标）", variable=self.follow_var,
                       bg=BG, fg="#d6dae0", activebackground=BG,
                       activeforeground="#d6dae0", selectcolor="#2b3136",
                       font=FONT, command=self._toggle_follow).pack(anchor="w")

        btns = tk.Frame(win, bg=BG)
        btns.pack(fill="x", padx=18, pady=(4, 16))

        mk_button(btns, "恢复默认", self.restore_defaults).pack(side="left")

        def on_save():
            self._save_all()
            win.destroy()

        def on_cancel():
            self.cfg = load_char_cfg(self.char_name)
            self.cfg["follow_mouse"] = load_global_cfg().get("follow_mouse", False)
            self.follow_var.set(self.cfg["follow_mouse"])
            self._apply_param_effects()
            win.destroy()

        mk_button(btns, "取消", on_cancel).pack(side="right")
        mk_button(btns, "保存", on_save, "primary").pack(side="right", padx=(0, 8))
        win.protocol("WM_DELETE_WINDOW", on_save)

    def _on_param(self, key, var, val_lbl, lo, hi, res):
        v = round(var.get() / res) * res
        v = max(lo, min(hi, v))
        var.set(v)
        val_lbl.configure(text=self._fmt(v))
        self.cfg[key] = v
        if key == "scale":
            self._scale_images()
        elif key == "pounce_speed":
            self.pounce_speed = v

    def _apply_param_effects(self):
        self._scale_images()
        self.pounce_speed = self.cfg["pounce_speed"]

    def restore_defaults(self):
        self.cfg = dict(DEFAULTS)
        self.cfg["follow_mouse"] = load_global_cfg().get("follow_mouse", False)
        for key, (var, val) in getattr(self, "_sliders", {}).items():
            var.set(self.cfg[key])
            val.configure(text=self._fmt(self.cfg[key]))
        self.follow_var.set(self.cfg["follow_mouse"])
        self._apply_param_effects()
        self._save_all()

    # ---------- 角色管理窗口 ----------
    def open_character_manager(self):
        if self.char_mgr and self.char_mgr.winfo_exists():
            self.char_mgr.lift()
            return
        win = tk.Toplevel(self.root)
        win.title("美洲狮来了 · 角色管理")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.minsize(340, 260)
        win.attributes("-topmost", True)
        win.transient(self.root)
        self.char_mgr = win

        header = tk.Frame(win, bg=BG)
        header.pack(fill="x", padx=18, pady=(16, 4))
        tk.Label(header, text="角色管理", font=("Microsoft YaHei UI", 15, "bold"),
                 bg=BG, fg=ACCENT).pack(side="left")
        self.mgr_cur = tk.Label(header, text="", font=FONT, bg=BG, fg="#ffd479")
        self.mgr_cur.pack(side="right")

        canvas = tk.Canvas(win, bg=BG, highlightthickness=0, width=380, height=320)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        item = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(18, 0))
        scrollbar.pack(side="left", fill="y", pady=6)
        self.mgr_canvas, self.mgr_inner = canvas, inner

        btns = tk.Frame(win, bg=BG)
        btns.pack(fill="x", padx=18, pady=(4, 16))
        mk_button(btns, "添加角色", self.open_add_dialog, "primary").pack(side="left")
        mk_button(btns, "关闭", win.destroy).pack(side="right")

        win.protocol("WM_DELETE_WINDOW", lambda: win.destroy())
        self._rebuild_char_cards()

    def _rebuild_char_cards(self):
        if not getattr(self, "mgr_inner", None) or \
                not self.mgr_inner.winfo_exists():
            return
        for w in self.mgr_inner.winfo_children():
            w.destroy()
        chars = sorted(list_characters())
        for name in chars:
            self._char_card(name)
        self.mgr_cur.configure(text="当前角色：" + self.char_name)
        self.mgr_inner.update_idletasks()
        self.mgr_canvas.configure(scrollregion=self.mgr_canvas.bbox("all"))

    def _char_card(self, name):
        is_cur = name == self.char_name
        bg = CARD if not is_cur else "#233649"
        card = tk.Frame(self.mgr_inner, bg=bg, padx=10, pady=8, highlightthickness=1,
                        highlightbackground="#3a3f44")
        card.pack(fill="x", padx=4, pady=5)

        thumb = self._thumb_photo(name)
        if thumb:
            tl = tk.Label(card, image=thumb, bg=bg, bd=0)
            tl.image = thumb
            tl.pack(side="left", padx=(0, 10))
        else:
            tk.Label(card, text="?", bg=bg, fg="#8a919a",
                     width=7, height=3).pack(side="left", padx=(0, 10))

        info = tk.Frame(card, bg=bg)
        info.pack(side="left", fill="x", expand=True)
        tk.Label(info, text=name, bg=bg, fg="#ffffff",
                 font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        n_c = len(self._frames_of(name, "crawl"))
        n_s = len(self._frames_of(name, "scare"))
        tk.Label(info, text=f"爬行 {n_c} 帧 · 惊吓 {n_s} 帧", bg=bg, fg="#8a919a",
                 font=FONT).pack(anchor="w")

        btns = tk.Frame(card, bg=bg)
        btns.pack(side="right")
        mk_button(btns, "编辑", lambda n=name: self.open_edit_dialog(n)).pack(side="left", padx=3)
        if is_cur:
            tk.Label(btns, text="当前", bg=ACCENT, fg="#0b1520", padx=10, pady=3,
                     font=FONT_BOLD).pack(side="left")
        else:
            mk_button(btns, "切换", lambda n=name: self._switch_to(n),
                      "primary").pack(side="left", padx=3)
            mk_button(btns, "删除", lambda n=name: self._delete_char(n),
                      "danger").pack(side="left", padx=3)

        if not is_cur:
            def on_enter(e):
                card.configure(bg=HOVER)
                for w in card.winfo_children():
                    w.configure(bg=HOVER)

            def on_leave(e):
                card.configure(bg=CARD)
                for w in card.winfo_children():
                    w.configure(bg=CARD)
            for w in (card, info):
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)

    def _frames_of(self, name, prefix):
        folder = os.path.join(char_dir(), name)
        return [f for f in os.listdir(folder)
                if f.startswith(prefix + "_")
                and os.path.splitext(f)[1].lower() in IMAGE_EXTS]

    def _switch_to(self, name):
        if name == self.char_name:
            return
        self._load_character(name)
        self._close_settings()
        self._rebuild_char_cards()
        self._rebuild_char_menu()
        self._refresh_tray_menu()

    def _close_settings(self):
        if self.settings_win and self.settings_win.winfo_exists():
            self.settings_win.destroy()
        self.settings_win = None

    def _delete_char(self, name):
        if not messagebox.askyesno(
                "删除角色", f"确定删除角色「{name}」吗？\n其图片将被永久删除，此操作不可恢复。",
                parent=self.char_mgr):
            return
        if name == self.char_name:
            others = [c for c in list_characters() if c != name]
            if others:
                self._load_character(others[0])
            else:
                self._ensure_characters()
                self._load_character("美洲狮")
        shutil.rmtree(os.path.join(char_dir(), name), ignore_errors=True)
        self._rebuild_char_cards()

    # ---------- 编辑角色窗口 ----------
    def open_edit_dialog(self, name):
        if self.edit_dlg and self.edit_dlg.winfo_exists():
            self.edit_dlg.lift()
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("编辑角色")
        dlg.configure(bg=BG)
        dlg.resizable(True, True)
        dlg.minsize(420, 420)
        dlg.attributes("-topmost", True)
        dlg.transient(self.root)
        self.edit_dlg = dlg
        self.edit_name = name
        self.edit_crawl_files = []
        self.edit_scare_files = []
        self.edit_face_var = tk.StringVar(value=get_char_facing(name))
        name_var = tk.StringVar(value=name)
        self.edit_hint = tk.Label(dlg, text="", bg=BG, fg=DANGER, font=FONT)

        tk.Label(dlg, text="编辑角色", font=("Microsoft YaHei UI", 15, "bold"),
                 bg=BG, fg=ACCENT).pack(fill="x", pady=(16, 8), padx=18)
        tk.Label(dlg, text="角色名", bg=BG, fg="#d6dae0", anchor="w",
                 font=FONT).pack(fill="x", padx=18, pady=(6, 0))
        tk.Entry(dlg, textvariable=name_var, bg="#2b3136", fg="#fff",
                 insertbackground="#fff", relief="flat", bd=0,
                 font=FONT).pack(fill="x", padx=18, pady=(4, 8), ipady=4)

        self._facing_row(dlg, self.edit_face_var).pack(fill="x", padx=18, pady=(2, 0))

        self._edit_picker_row(dlg, "爬行图片（重新选择将替换）", "crawl")
        self._edit_picker_row(dlg, "惊吓图片（重新选择将替换）", "scare")

        self.edit_hint.pack(fill="x", padx=18, pady=(2, 0))
        tk.Label(dlg, text="不重新选择则保留原图片；改名后角色管理同步更新。\n"
                 "可按住 Ctrl/Shift 一次多选，也可重复点击「重新选择」继续追加。",
                 bg=BG, fg="#8a919a", font=FONT, anchor="w", justify="left"
                 ).pack(fill="x", padx=18, pady=(6, 0))

        btns = tk.Frame(dlg, bg=BG)
        btns.pack(fill="x", padx=18, pady=(12, 16))
        mk_button(btns, "取消", lambda: dlg.destroy()).pack(side="right")
        mk_button(btns, "保存修改", lambda: self._confirm_edit(name_var, dlg),
                  "primary").pack(side="right", padx=(0, 8))

    def _edit_picker_row(self, parent, title, kind):
        cur = len(self._frames_of(self.edit_name, kind))
        tk.Label(parent, text=title, bg=BG, fg="#d6dae0", anchor="w",
                 font=FONT).pack(fill="x", padx=18, pady=(6, 0))
        line = tk.Frame(parent, bg=BG)
        line.pack(fill="x", padx=18, pady=(4, 0))
        mk_button(line, "重新选择...", lambda k=kind: self._pick_edit(k),
                  "primary").pack(side="left")
        lbl = tk.Label(line, text=f"当前 {cur} 帧", bg=BG, fg="#ffd479", font=FONT_BOLD)
        lbl.pack(side="right")
        if kind == "crawl":
            self.edit_crawl_lbl = lbl
        else:
            self.edit_scare_lbl = lbl
        prev = tk.Frame(parent, bg=BG, height=44)
        prev.pack(fill="x", padx=18, pady=(2, 0))
        folder = os.path.join(char_dir(), self.edit_name)
        existing = [os.path.join(folder, f)
                    for f in self._frames_of(self.edit_name, kind)]
        if existing:
            self._show_preview(prev, existing)
        if kind == "crawl":
            self.edit_crawl_prev = prev
        else:
            self.edit_scare_prev = prev

    def _pick_edit(self, kind):
        files = list(filedialog.askopenfilenames(
            title="选择爬行图片" if kind == "crawl" else "选择惊吓图片",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                       ("所有文件", "*.*")]))
        if not files:
            return
        if kind == "crawl":
            self.edit_crawl_files = merge_unique(self.edit_crawl_files, files)
            self.edit_crawl_lbl.configure(text=f"当前→{len(self.edit_crawl_files)} 张")
            self._show_preview(self.edit_crawl_prev, self.edit_crawl_files)
        else:
            self.edit_scare_files = merge_unique(self.edit_scare_files, files)
            self.edit_scare_lbl.configure(text=f"当前→{len(self.edit_scare_files)} 张")
            self._show_preview(self.edit_scare_prev, self.edit_scare_files)

    def _replace_frames(self, folder, prefix, files):
        for f in os.listdir(folder):
            if f.startswith(prefix + "_") and \
                    os.path.splitext(f)[1].lower() in IMAGE_EXTS:
                try:
                    os.remove(os.path.join(folder, f))
                except Exception:
                    pass
        for i, f in enumerate(files, 1):
            ext = os.path.splitext(f)[1].lower()
            shutil.copy2(f, os.path.join(folder, f"{prefix}_{i}{ext}"))

    def _confirm_edit(self, name_var, dlg):
        new_name = name_var.get().strip()
        old = self.edit_name
        err = None
        if not new_name:
            err = "请输入角色名"
        elif re.search(r'[\\/:*?"<>|]', new_name):
            err = "角色名不能包含 \\ / : * ? \" < > |"
        elif new_name != old and \
                os.path.isdir(os.path.join(char_dir(), new_name)):
            err = f"角色「{new_name}」已存在"
        if err:
            self.edit_hint.configure(text=err)
            return
        self.edit_hint.configure(text="")
        was_current = old == self.char_name
        if new_name != old:
            os.rename(os.path.join(char_dir(), old),
                      os.path.join(char_dir(), new_name))
        folder = os.path.join(char_dir(), new_name)
        if self.edit_crawl_files:
            self._replace_frames(folder, "crawl", self.edit_crawl_files)
        if self.edit_scare_files:
            self._replace_frames(folder, "scare", self.edit_scare_files)
        set_char_facing(new_name, self.edit_face_var.get())
        self._thumbs.pop("th_" + old, None)
        self._thumbs.pop("th_" + new_name, None)
        if was_current:
            self._load_character(new_name)
            self._close_settings()
        dlg.destroy()
        self.edit_dlg = None
        self._rebuild_char_cards()

    # ---------- 添加角色窗口 ----------
    def open_add_dialog(self):
        if self.add_dlg and self.add_dlg.winfo_exists():
            self.add_dlg.lift()
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("添加角色")
        dlg.configure(bg=BG)
        dlg.resizable(True, True)
        dlg.minsize(420, 400)
        dlg.attributes("-topmost", True)
        dlg.transient(self.root)
        self.add_dlg = dlg
        self.add_crawl_files = []
        self.add_scare_files = []
        self.add_face_var = tk.StringVar(value="left")
        name_var = tk.StringVar()
        self.add_hint = tk.Label(dlg, text="", bg=BG, fg=DANGER, font=FONT)

        pad = {"padx": 18, "pady": (6, 0)}
        tk.Label(dlg, text="添加角色", font=("Microsoft YaHei UI", 15, "bold"),
                 bg=BG, fg=ACCENT).pack(fill="x", pady=(16, 8), padx=18)
        tk.Label(dlg, text="角色名", bg=BG, fg="#d6dae0", anchor="w",
                 font=FONT).pack(fill="x", **pad)
        tk.Entry(dlg, textvariable=name_var, bg="#2b3136", fg="#fff",
                 insertbackground="#fff", relief="flat", bd=0,
                 font=FONT).pack(fill="x", padx=18, pady=(4, 8), ipady=4)

        self._facing_row(dlg, self.add_face_var).pack(fill="x", padx=18, pady=(2, 0))

        self.add_crawl_lbl = tk.Label(dlg, text="0 张", bg=BG, fg="#ffd479",
                                      font=FONT_BOLD)
        self.add_crawl_prev = tk.Frame(dlg, bg=BG, height=44)
        self._picker_row(dlg, "爬行图片（可多选，作为爬行帧）", "crawl", 0)
        self._picker_row(dlg, "惊吓图片（可多选，作为惊吓帧）", "scare", 1)

        self.add_hint.pack(fill="x", padx=18, pady=(2, 0))
        tk.Label(dlg, text="选择顺序即播放顺序；至少各 1 张；将复制到角色目录。\n"
                 "可按住 Ctrl/Shift 一次多选，也可重复点击「选择图片」继续追加。",
                 bg=BG, fg="#8a919a", font=FONT, anchor="w", justify="left"
                 ).pack(fill="x", padx=18, pady=(6, 0))

        btns = tk.Frame(dlg, bg=BG)
        btns.pack(fill="x", padx=18, pady=(12, 16))
        mk_button(btns, "取消", lambda: dlg.destroy()).pack(side="right")
        mk_button(btns, "添加并切换", lambda: self._confirm_add(name_var, dlg),
                  "primary").pack(side="right", padx=(0, 8))

    def _facing_row(self, parent, var):
        row = tk.Frame(parent, bg=BG)
        tk.Label(row, text="正面朝向", bg=BG, fg="#d6dae0", width=13, anchor="w",
                 font=FONT).pack(side="left")
        tk.Radiobutton(row, text="朝左", variable=var, value="left", bg=BG,
                       fg="#d6dae0", activebackground=BG, activeforeground="#d6dae0",
                       selectcolor="#2b3136", font=FONT).pack(side="left")
        tk.Radiobutton(row, text="朝右", variable=var, value="right", bg=BG,
                       fg="#d6dae0", activebackground=BG, activeforeground="#d6dae0",
                       selectcolor="#2b3136", font=FONT).pack(side="left")
        tk.Label(row, text="（图片正面/头部朝向）", bg=BG, fg="#8a919a",
                 font=FONT).pack(side="left", padx=(6, 0))
        return row

    def _picker_row(self, parent, title, kind, row):
        pad = {"padx": 18, "pady": (6, 0)}
        tk.Label(parent, text=title, bg=BG, fg="#d6dae0", anchor="w",
                 font=FONT).pack(fill="x", **pad)
        line = tk.Frame(parent, bg=BG)
        line.pack(fill="x", padx=18, pady=(4, 0))
        mk_button(line, "选择图片...", lambda k=kind: self._pick(k),
                  "primary").pack(side="left")
        lbl = tk.Label(line, text="0 张", bg=BG, fg="#ffd479", font=FONT_BOLD)
        lbl.pack(side="right")
        if kind == "crawl":
            self.add_crawl_lbl = lbl
        else:
            self.add_scare_lbl = lbl
        prev = tk.Frame(parent, bg=BG, height=44)
        prev.pack(fill="x", padx=18, pady=(2, 0))
        if kind == "crawl":
            self.add_crawl_prev = prev
        else:
            self.add_scare_prev = prev

    def _pick(self, kind):
        files = list(filedialog.askopenfilenames(
            title="选择爬行图片" if kind == "crawl" else "选择惊吓图片",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                       ("所有文件", "*.*")]))
        if not files:
            return
        if kind == "crawl":
            self.add_crawl_files = merge_unique(self.add_crawl_files, files)
            self.add_crawl_lbl.configure(text=f"{len(self.add_crawl_files)} 张")
            self._show_preview(self.add_crawl_prev, self.add_crawl_files)
        else:
            self.add_scare_files = merge_unique(self.add_scare_files, files)
            self.add_scare_lbl.configure(text=f"{len(self.add_scare_files)} 张")
            self._show_preview(self.add_scare_prev, self.add_scare_files)

    def _show_preview(self, frame, files):
        for w in frame.winfo_children():
            w.destroy()
        for f in files[:4]:
            try:
                img = Image.open(f)
                img.thumbnail((40, 40), Image.LANCZOS)
                ph = ImageTk.PhotoImage(flatten_to_key(img))
                lbl = tk.Label(frame, image=ph, bg=BG, bd=0)
                lbl.image = ph
                lbl.pack(side="left", padx=2)
            except Exception:
                pass
        if len(files) > 4:
            tk.Label(frame, text=f"+{len(files) - 4}", bg=BG, fg="#8a919a",
                     font=FONT).pack(side="left", padx=4)

    def _confirm_add(self, name_var, dlg):
        name = name_var.get().strip()
        err = None
        if not name:
            err = "请输入角色名"
        elif re.search(r'[\\/:*?"<>|]', name):
            err = "角色名不能包含 \\ / : * ? \" < > |"
        elif os.path.isdir(os.path.join(char_dir(), name)):
            err = f"角色「{name}」已存在"
        elif not self.add_crawl_files:
            err = "请选择至少 1 张爬行图片"
        elif not self.add_scare_files:
            err = "请选择至少 1 张惊吓图片"
        if err:
            self.add_hint.configure(text=err)
            return
        self.add_hint.configure(text="")
        self.add_character(name, self.add_crawl_files, self.add_scare_files,
                           self.add_face_var.get())
        dlg.destroy()
        self.add_dlg = None
        self._rebuild_char_cards()

    # ---------- 队列 / 退出 ----------
    def _drain_queue(self):
        try:
            while True:
                cmd = self.cmd_q.get_nowait()
                if cmd == "settings":
                    self.root.after(0, self.open_settings)
                elif cmd == "charmgr":
                    self.root.after(0, self.open_character_manager)
                elif cmd == "quit":
                    self.shutdown()
                elif isinstance(cmd, tuple) and cmd and cmd[0] == "switch":
                    self.root.after(0, lambda: self._switch_to(cmd[1]))
        except queue.Empty:
            pass

    def shutdown(self):
        self.running = False
        self._save_all()
        if getattr(self, "tray", None):
            try:
                self.tray.stop()
            except Exception:
                pass
        if self.root.winfo_exists():
            self.root.destroy()


def main():
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    app = PetApp()

    if "--selftest" in sys.argv:
        root = app.root
        for _ in range(30):
            root.update()
            time.sleep(0.03)
        print("SELFTEST OK state=%s char=%s crawl=%d scare=%d pos=%s" %
              (app.state, app.char_name, len(app.crawl_frames),
               len(app.scare_frames), [int(x) for x in app.pos]))
        app.shutdown()
        return 0

    app.root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
