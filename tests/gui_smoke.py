"""Explicit opt-in desktop checks; all mutable data stays in a temporary folder."""
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import main


class DesktopSmokeTest(unittest.TestCase):
    def test_desktop_lifecycle(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(main, "data_dir", return_value=folder):
            app = main.PetApp()
            errors = []
            app.root.report_callback_exception = lambda *error: errors.append(error)
            try:
                self.assertEqual(app.char_name, "tjm")
                self.assertEqual(len(app.crawl_frames), 2)
                self.assertEqual(len(app.scare_frames), 2)
                self.assertEqual(app.face_dir, "right")
                self.assertEqual(app.cfg["scale"], 50)
                # Use the real mainloop so macOS Cocoa events are also serviced.
                app.root.after(500, app.root.quit)
                app.root.mainloop()
                self.assertIsNotNone(app.tray, "Native tray initialization failed")
                self.assertTrue(app.tray.visible)
                app.cmd_q.put("pause")
                app.cmd_q.put("follow")
                app._drain_queue()
                self.assertTrue(app.paused)
                self.assertTrue(app.cfg["follow_mouse"])
                app.open_settings()
                app.root.update()
                app._close_settings()
                app.open_character_manager()
                app.root.update()
                app.char_mgr.destroy()
                app.char_mgr = None
                x, y = app.pet_window.winfo_x(), app.pet_window.winfo_y()
                app._on_lbutton(SimpleNamespace(x_root=x + 5, y_root=y + 5))
                app._on_drag(SimpleNamespace(x_root=x + 25, y_root=y + 25))
                app._on_drag_end(SimpleNamespace(x_root=x + 25, y_root=y + 25))
                app.trigger_scare()
                app._tick_scare(time.monotonic())
                app._load_character(app.char_name)
                app.root.update()
                self.assertEqual(app.cur_key[0], "c0")
                app._save_all()
                self.assertTrue(main.load_global_cfg()["follow_mouse"])
                self.assertEqual(errors, [])
                self.assertGreater(app.cur_size[0], 0)
            finally:
                app.shutdown()

    def test_pet_moves_while_settings_stay_in_place(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(main, "data_dir", return_value=folder):
            app = main.PetApp()
            errors = []
            app.root.report_callback_exception = lambda *error: errors.append(error)
            try:
                app.cfg.update(follow_mouse=False, wobble_amp=0, crawl_speed=80)
                app.root.after(300, app.root.quit)
                app.root.mainloop()
                app.open_settings()
                app.settings_win.geometry("460x600+50+50")
                app.root.update()
                settings_position = (app.settings_win.winfo_x(), app.settings_win.winfo_y())
                app.pos = [100.0, 100.0]
                app._place(app.pos)
                app.root.update_idletasks()
                before = (app.pet_window.winfo_x(), app.pet_window.winfo_y())
                app.angle = 0.0
                app.idle_until = 0.0
                app.next_think = main.time.monotonic() + 100
                app._tick_crawl(main.time.monotonic(), 0.2)
                app.root.update()
                after = (app.pet_window.winfo_x(), app.pet_window.winfo_y())
                self.assertGreater(after[0], before[0])
                self.assertEqual(settings_position,
                                 (app.settings_win.winfo_x(), app.settings_win.winfo_y()))
                if main.IS_MAC:
                    self.assertEqual(app.root.state(), "withdrawn")
                    self.assertTrue(app.pet_window.is_visible())
                    self.assertTrue(app.pet_window.view.image().isValid())
                    self.assertIsNone(app.pet_window.window.parentWindow())
                    preview = main.os.path.join(folder, "pet-render.png")
                    app.pet_window.save_preview(preview)
                    with main.Image.open(preview) as image:
                        self.assertIsNotNone(image.convert("RGBA").getchannel("A").getbbox())
                self.assertEqual(errors, [])
            finally:
                app.shutdown()


if __name__ == "__main__":
    unittest.main()
