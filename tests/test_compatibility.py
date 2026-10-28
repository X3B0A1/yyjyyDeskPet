import os
import queue
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

import main


class PlatformTests(unittest.TestCase):
    def test_mac_data_stays_outside_app_bundle(self):
        with patch.object(main, "IS_MAC", True), \
                patch.object(sys, "frozen", True, create=True), \
                patch.object(sys, "executable", "/Applications/Pet.app/Contents/MacOS/Pet"), \
                patch.object(sys, "_MEIPASS", "/Applications/Pet.app/Contents/Resources", create=True):
            expected = os.path.expanduser("~/Library/Application Support/SylaiDesk")
            self.assertEqual(main.data_dir(), expected)
            self.assertEqual(main.config_path(), os.path.join(expected, "pet_config.json"))
            self.assertEqual(main.char_dir(), os.path.join(expected, "characters"))
            self.assertEqual(main.manifest_path(), os.path.join(expected, "characters.json"))
            self.assertEqual(main.resource("0.png"),
                             os.path.join(sys._MEIPASS, "0.png"))

    def test_windows_keeps_portable_data(self):
        with patch.object(main, "IS_MAC", False), \
                patch.object(main, "base_dir", return_value="portable"):
            self.assertEqual(main.data_dir(), "portable")

    def test_mac_window_does_not_use_windows_attributes(self):
        root = Mock()
        with patch.object(main, "IS_MAC", True):
            self.assertEqual(main.configure_pet_window(root), "systemTransparent")
        attrs = dict(call.args for call in root.attributes.call_args_list)
        self.assertEqual(attrs, {"-topmost": True, "-transparent": True})
        root.configure.assert_called_once_with(bg="systemTransparent")

    def test_windows_keeps_color_key_and_tool_window(self):
        root = Mock()
        with patch.object(main, "IS_MAC", False), patch.object(main, "IS_WINDOWS", True):
            self.assertEqual(main.configure_pet_window(root), main.KEY)
        attrs = dict(call.args for call in root.attributes.call_args_list)
        self.assertEqual(attrs["-transparentcolor"], main.KEY)
        self.assertTrue(attrs["-toolwindow"])

    def test_mac_keeps_alpha_while_windows_flattens(self):
        image = Image.new("RGBA", (2, 1), (255, 0, 0, 0))
        image.putpixel((1, 0), (255, 0, 0, 255))
        for is_mac in (True, False):
            with self.subTest(is_mac=is_mac):
                app = main.PetApp.__new__(main.PetApp)
                app.scaled = {"c0": image}
                app.frame_photos = {}
                app.label = Mock()
                with patch.object(main, "IS_MAC", is_mac), \
                        patch.object(main.ImageTk, "PhotoImage") as photo:
                    main.PetApp._set_frame(app, "c0", mirrored=True)
                    rendered = photo.call_args.args[0]
                self.assertEqual(rendered.mode, "RGBA" if is_mac else "RGB")
                self.assertEqual(rendered.getpixel((0, 0))[:3], (255, 0, 0))
                self.assertEqual(rendered.getpixel((1, 0)),
                                 (255, 0, 0, 0) if is_mac else (1, 2, 3))

    def test_frozen_new_pet_uses_independent_process(self):
        app = main.PetApp.__new__(main.PetApp)
        with patch.object(sys, "frozen", True, create=True), \
                patch.object(main.subprocess, "Popen") as popen:
            app.launch_new_instance()
        self.assertEqual(popen.call_args.args[0], [sys.executable])
        self.assertEqual(popen.call_args.kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")

    def test_source_new_pet_uses_current_python(self):
        app = main.PetApp.__new__(main.PetApp)
        with patch.object(sys, "frozen", False, create=True), \
                patch.object(main.subprocess, "Popen") as popen:
            app.launch_new_instance()
        self.assertEqual(popen.call_args.args[0],
                         [sys.executable, os.path.abspath(main.__file__)])


class TrayTests(unittest.TestCase):
    def setUp(self):
        # Menu descriptors can be tested without creating a native status icon.
        import pystray
        self.pystray = pystray
        self.app = main.PetApp.__new__(main.PetApp)
        self.app.cmd_q = queue.Queue()
        self.app.crawl_frames = [Image.new("RGBA", (8, 8))]
        self.app.char_name = "A"
        self.app.cfg = {"follow_mouse": False}
        self.app.paused = False

    def test_mac_tray_uses_detached_loop_and_queues_ui_actions(self):
        icon = Mock()
        with patch.object(main, "IS_MAC", True), \
                patch.object(main, "list_characters", return_value=["A"]), \
                patch.object(self.pystray, "Icon", return_value=icon) as factory, \
                patch.object(main.threading, "Thread") as thread:
            self.app._setup_tray()
        icon.run_detached.assert_called_once()
        self.assertIn("setup", icon.run_detached.call_args.kwargs)
        icon.run.assert_not_called()
        thread.assert_not_called()
        self.assertTrue(icon.visible)
        menu = list(factory.call_args.kwargs["menu"])
        for item in menu[:3]:
            worker = threading.Thread(target=item, args=(icon,))
            worker.start()
            worker.join()
        self.assertEqual([self.app.cmd_q.get_nowait() for _ in range(3)],
                         ["pause", "follow", "new"])
        self.assertFalse(self.app.paused)
        self.assertFalse(self.app.cfg["follow_mouse"])

    def test_character_callbacks_capture_names_and_menu_is_dynamic(self):
        with patch.object(main, "list_characters", return_value=["A", "B"]):
            menu = self.app._tray_char_menu()
            items = list(menu)
            for item in items:
                item(Mock())
            self.assertEqual([self.app.cmd_q.get_nowait() for _ in items],
                             [("switch", "A"), ("switch", "B")])
            self.assertEqual([item.checked for item in items], [True, False])
        with patch.object(main, "list_characters", return_value=["C"]):
            self.assertEqual([item.text for item in menu], ["C"])

    def test_queue_executes_every_switch_in_order(self):
        self.app._switch_to = Mock()
        self.app.cmd_q.put(("switch", "A"))
        self.app.cmd_q.put(("switch", "B"))
        self.app._drain_queue()
        self.assertEqual([call.args[0] for call in self.app._switch_to.call_args_list],
                         ["A", "B"])

    def test_quit_does_not_schedule_another_tick(self):
        self.app.running = True
        self.app.root = Mock()
        self.app.last = main.time.monotonic()
        self.app._save_all = Mock()
        self.app.tray = None
        self.app.cmd_q.put("quit")
        self.app.tick()
        self.app.root.destroy.assert_called_once()
        self.app.root.after.assert_not_called()


class CharacterTests(unittest.TestCase):
    def test_first_launch_seeds_images_and_preserves_character_settings(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(main, "data_dir", return_value=folder):
            app = main.PetApp.__new__(main.PetApp)
            app._ensure_characters()
            self.assertEqual(main.list_characters(), ["美洲狮"])
            for filename in ("crawl_1.png", "scare_1.png", "scare_2.png"):
                self.assertTrue((Path(main.char_dir()) / "美洲狮" / filename).is_file())
            main.set_char_facing("美洲狮", "right")
            main.save_char_cfg("美洲狮", {**main.DEFAULTS, "scale": 75})
            main.save_global_cfg({"follow_mouse": True})
            app._ensure_characters()
            self.assertEqual(main.load_char_cfg("美洲狮")["scale"], 75)
            self.assertEqual(main.get_char_facing("美洲狮"), "right")
            self.assertTrue(main.load_global_cfg()["follow_mouse"])

    def test_switching_from_scare_to_shorter_character_resets_frame(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(main, "data_dir", return_value=folder), \
                patch.object(main.ImageTk, "PhotoImage"):
            target = Path(main.char_dir()) / "B"
            target.mkdir(parents=True)
            for name in ("crawl_1.png", "scare_1.png"):
                Image.new("RGBA", (8, 8)).save(target / name)
            app = main.PetApp.__new__(main.PetApp)
            app.label = Mock()
            app.cur_key = ("s9", True)
            app.face_mirror = True
            app.state = "scare"
            app._clamp = Mock()
            app._place = Mock()
            app.pos = [0, 0]
            app._load_character("B")
            self.assertEqual(app.state, "crawl")
            self.assertEqual(app.cur_key[0], "c0")

    def test_dragging_without_pause_stops_animation(self):
        app = main.PetApp.__new__(main.PetApp)
        app.root = Mock()
        app.root.winfo_x.return_value = 100
        app.root.winfo_y.return_value = 100
        app.paused = False
        app.cur_size = (20, 20)
        app.screen_w, app.screen_h = 1920, 1080
        app.pos = [100, 100]
        app.trigger_scare = Mock()
        event = SimpleNamespace(x_root=110, y_root=110)
        app._on_lbutton(event)
        event = SimpleNamespace(x_root=210, y_root=210)
        app._on_drag(event)
        self.assertTrue(app._dragging)
        self.assertEqual(app.pos, [200, 200])
        app._on_drag_end(event)
        self.assertFalse(app._dragging)
        app.trigger_scare.assert_not_called()


if __name__ == "__main__":
    unittest.main()
