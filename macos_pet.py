"""Native Cocoa pet rendering, independent of Tk's stationary dialog windows."""
import io
import re
from types import SimpleNamespace

import AppKit
import Foundation
import objc


def desktop_top():
    frame = AppKit.NSScreen.screens()[0].frame()
    return frame.origin.y + frame.size.height


def pointer_event():
    point = AppKit.NSEvent.mouseLocation()
    return SimpleNamespace(x_root=round(point.x),
                           y_root=round(desktop_top() - point.y))


class PetPanel(AppKit.NSPanel):
    def canBecomeKeyWindow(self):
        return False

    def canBecomeMainWindow(self):
        return False


class PetImageView(AppKit.NSImageView):
    def acceptsFirstMouse_(self, event):
        return True

    def isFlipped(self):
        return True

    def mouseDown_(self, event):
        self.context_click = bool(event.modifierFlags() & AppKit.NSEventModifierFlagControl)
        if self.context_click:
            self.show_menu()
        else:
            self.pet_app._on_lbutton(pointer_event())

    def mouseDragged_(self, event):
        if not getattr(self, "context_click", False):
            self.pet_app._on_drag(pointer_event())

    def mouseUp_(self, event):
        if not getattr(self, "context_click", False):
            self.pet_app._on_drag_end(pointer_event())
        self.context_click = False

    def rightMouseDown_(self, event):
        self.show_menu()

    def otherMouseDown_(self, event):
        self.show_menu()

    @objc.python_method
    def show_menu(self):
        point = pointer_event()
        # Schedule Tk's popup after Cocoa finishes dispatching the mouse event.
        self.pet_app.root.after(0, lambda: self.pet_app._popup_menu(point))


class NativePhoto:
    def __init__(self, image):
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        data = Foundation.NSData.dataWithBytes_length_(stream.getvalue(), stream.tell())
        self.image = AppKit.NSImage.alloc().initWithData_(data)
        if self.image is None or not self.image.isValid():
            raise ValueError("无法创建宠物图片")
        self._size = image.size
        self.image.setSize_(self._size)

    def width(self):
        return self._size[0]

    def height(self):
        return self._size[1]


class MacPetWindow:
    """A borderless NSPanel: never a Tk transient or an owner of dialogs."""
    def __init__(self, app):
        self.window = PetPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (1, 1)),
            AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel,
            AppKit.NSBackingStoreBuffered, False,
        )
        self.window.setReleasedWhenClosed_(False)
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(AppKit.NSColor.clearColor())
        self.window.setHasShadow_(False)
        self.window.setLevel_(AppKit.NSFloatingWindowLevel)
        self.window.setHidesOnDeactivate_(False)
        self.window.setIgnoresMouseEvents_(False)
        self.window.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        self.view = PetImageView.alloc().initWithFrame_(((0, 0), (1, 1)))
        self.view.pet_app = app
        self.view.context_click = False
        self.view.setImageScaling_(AppKit.NSImageScaleAxesIndependently)
        self.view.setImageAlignment_(AppKit.NSImageAlignCenter)
        self.window.setContentView_(self.view)
        self._photo = None

    @staticmethod
    def make_photo(image):
        return NativePhoto(image)

    def configure(self, *, image):
        self._photo = image
        self.view.setImage_(image.image)
        self.view.setNeedsDisplay_(True)

    def geometry(self, value):
        match = re.fullmatch(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", value)
        if not match:
            raise ValueError("Invalid pet geometry: " + value)
        width, height, x, y = map(int, match.groups())
        self.window.setFrame_display_(
            ((x, desktop_top() - y - height), (width, height)), True)
        self.view.setFrame_(((0, 0), (width, height)))
        if not self.window.isVisible():
            self.window.orderFrontRegardless()

    def winfo_x(self):
        return round(self.window.frame().origin.x)

    def winfo_y(self):
        frame = self.window.frame()
        return round(desktop_top() - frame.origin.y - frame.size.height)

    def is_visible(self):
        return bool(self.window.isVisible())

    def save_preview(self, path):
        """Capture our own view without screen recording permissions."""
        self.view.displayIfNeeded()
        bounds = self.view.bounds()
        bitmap = self.view.bitmapImageRepForCachingDisplayInRect_(bounds)
        self.view.cacheDisplayInRect_toBitmapImageRep_(bounds, bitmap)
        data = bitmap.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, {})
        if data is None or not data.writeToFile_atomically_(str(path), True):
            raise RuntimeError("无法保存宠物显示检查图片")

    def destroy(self):
        self.window.orderOut_(None)
        self.window.close()
        self.view.pet_app = None
        self._photo = None
