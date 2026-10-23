"""Take the window screenshot used in the README, with generic example paths (no personal data) and a plausible state.

  python tools/make_screenshot.py [OUT.png]
"""
import os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'builder'))
import tkinter as tk
from PIL import ImageGrab
import capital_builder as cb

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'docs', 'images', 'window.png')
FACTS = {'fo4': r'C:\Program Files (x86)\Steam\steamapps\common\Fallout 4', 'fo4_version': '1.11.240.0', 'Archive2': True, 'Elrich': True, 'Creation Kit': True,
         'Papyrus compiler': True, 'fo4_writable': True, 'fo3_data': r'D:\Games\Fallout 3 GOTY\Data', 'fo3_dlc': ['Anchorage', 'ThePitt', 'BrokenSteel', 'PointLookout', 'Zeta'],
         'workdir': r'D:\FalloutEver\work', 'free_gb': 412.0, 'ram_gb': 32.0}
cb.resolve_config = lambda args, st: {'fo4': FACTS['fo4'], 'fo3_data': FACTS['fo3_data'], 'workdir': FACTS['workdir']}
cb.preflight = lambda cfg: (dict(FACTS), [])
cb.load_state = lambda wd: {'done': {s: {} for s in ('01-prepare', '02-assets', '03-plugins', '04-worldfix', '05-lod')}, 'config': {}}


def grab(self, n=0):
    self.geometry('+10+10')
    for _ in range(40):
        self.update()
        time.sleep(0.05)
    x, y, w, h = self.winfo_rootx(), self.winfo_rooty(), self.winfo_width(), self.winfo_height()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(OUT)
    self.destroy()


tk.Tk.mainloop = grab
import gui
gui.run_gui()
print('wrote', OUT)
