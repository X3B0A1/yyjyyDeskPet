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
                x, y = app.root.winfo_x(), app.root.winfo_y()
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


if __name__ == "__main__":
    unittest.main()
