"""Android entry point for Ma:Vi."""

from __future__ import annotations

import os

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_GL_BACKEND", "sdl2")

from kivy.config import Config

Config.set("graphics", "multisamples", "0")
Config.set("graphics", "maxfps", "30")
Config.set("graphics", "verify_gl_main_thread", "0")

from client.main import MaviApp


if __name__ == "__main__":
    MaviApp().run()
