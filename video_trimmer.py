"""Trim a video between a start and end point picked visually.

Usage: video_trimmer.bat (or drag a video onto it)
Shortcuts: Space play/pause | Left/Right 1 frame | Shift+Left/Right 1 s | I start | O end | Ctrl+S save
"""
import subprocess, sys, threading
from pathlib import Path
from tkinter import Tk, Frame, Label, Button, Canvas, filedialog, messagebox

import cv2
import imageio_ffmpeg
from PIL import Image, ImageTk

BG, PANEL, FG, MUTED = "#16181d", "#20232a", "#e6e6e6", "#8a8f98"
ACCENT, START, END = "#4f8cff", "#3ecf8e", "#ff6b6b"
FONT = ("Segoe UI", 10)


def fmt(s):
    return f"{int(s // 60):02d}:{s % 60:06.3f}"


def trim(src, dst, start, end):
    # re-encode for a frame-accurate cut (stream copy would only cut on keyframes)
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-ss", f"{start:.3f}", "-i", src,
           "-t", f"{end - start:.3f}", "-c:v", "libx264", "-crf", "18", "-preset", "fast",
           "-c:a", "aac", dst]
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    subprocess.run(cmd, check=True, capture_output=True, creationflags=flags)


def button(parent, text, cmd, color=PANEL, **kw):
    return Button(parent, text=text, command=cmd, bg=color, fg=FG, activebackground=ACCENT,
                  activeforeground="white", relief="flat", bd=0, padx=14, pady=6,
                  font=FONT, cursor="hand2", **kw)


class App:
    def __init__(self, root, src=None):
        self.root, self.cap, self.playing, self.frame = root, None, False, None
        self.total, self.fps, self.pos, self.start, self.end = 1, 30, 0, 0, 0
        self.dragging = None
        root.title("Video Trimmer")
        root.configure(bg=BG)
        k = root.tk.call("tk", "scaling") / 1.333  # follow Windows display scaling
        root.geometry(f"{int(1000 * k)}x{int(680 * k)}")
        root.minsize(int(820 * k), int(500 * k))

        top = Frame(root, bg=BG)
        top.pack(fill="x", padx=16, pady=(14, 8))
        button(top, "📂  Open video", self.open).pack(side="left")
        self.name = Label(top, text="No video loaded", bg=BG, fg=MUTED, font=FONT)
        self.name.pack(side="left", padx=12)

        self.screen = Label(root, bg="black")
        self.screen.pack(fill="both", expand=True, padx=16)
        self.screen.bind("<Configure>", lambda e: self.show())

        self.timeline = Canvas(root, height=44, bg=BG, highlightthickness=0, cursor="hand2")
        self.timeline.pack(fill="x", padx=16, pady=(10, 0))
        self.timeline.bind("<Button-1>", self.click)
        self.timeline.bind("<B1-Motion>", self.drag)
        self.timeline.bind("<ButtonRelease-1>", lambda e: setattr(self, "dragging", None))
        self.timeline.bind("<Configure>", lambda e: self.draw())

        ctrl = Frame(root, bg=BG)
        ctrl.pack(fill="x", padx=16, pady=8)
        for t, d in (("⏪ 1s", -1.0), ("◀ frame", -1)):
            button(ctrl, t, lambda d=d: self.step(d)).pack(side="left", padx=(0, 6))
        self.bplay = button(ctrl, "▶  Play", self.toggle, color=ACCENT, width=8)
        self.bplay.pack(side="left", padx=(0, 6))
        for t, d in (("frame ▶", 1), ("1s ⏩", 1.0)):
            button(ctrl, t, lambda d=d: self.step(d)).pack(side="left", padx=(0, 6))
        self.clock = Label(ctrl, text="00:00.000 / 00:00.000", bg=BG, fg=FG,
                           font=("Consolas", 12))
        self.clock.pack(side="right")

        cut = Frame(root, bg=PANEL)
        cut.pack(fill="x", padx=16, pady=(0, 8))
        button(cut, "[  Set start  (I)", self.mark_start, color=BG).pack(side="left", padx=8, pady=8)
        self.lstart = Label(cut, text="00:00.000", bg=PANEL, fg=START, font=("Consolas", 12))
        self.lstart.pack(side="left")
        button(cut, "Set end  (O)  ]", self.mark_end, color=BG).pack(side="left", padx=(20, 8))
        self.lend = Label(cut, text="00:00.000", bg=PANEL, fg=END, font=("Consolas", 12))
        self.lend.pack(side="left")
        self.bsave = button(cut, "💾  Save clip", self.save, color=ACCENT)
        self.bsave.pack(side="right", padx=8)
        self.ldur = Label(cut, text="", bg=PANEL, fg=MUTED, font=FONT)
        self.ldur.pack(side="left", padx=(20, 0))

        self.status = Label(root, text="Open a video to begin  •  Space play  •  ←/→ frame  "
                            "•  Shift+←/→ 1 s  •  I/O mark  •  Ctrl+S save",
                            bg=BG, fg=MUTED, font=("Segoe UI", 9), anchor="w")
        self.status.pack(fill="x", padx=16, pady=(0, 10))

        root.bind("<space>", lambda e: self.toggle())
        root.bind("<Left>", lambda e: self.step(-1))
        root.bind("<Right>", lambda e: self.step(1))
        root.bind("<Shift-Left>", lambda e: self.step(-1.0))
        root.bind("<Shift-Right>", lambda e: self.step(1.0))
        root.bind("<i>", lambda e: self.mark_start())
        root.bind("<o>", lambda e: self.mark_end())
        root.bind("<Control-s>", lambda e: self.save())
        if src:
            root.after(100, lambda: self.open(src))

    # ---------- video ----------
    def open(self, src=None):
        src = src or filedialog.askopenfilename(
            title="Choose a video",
            filetypes=[("Videos", "*.mp4 *.mov *.avi *.mkv *.webm *.m4v"), ("All files", "*.*")])
        if not src:
            return
        cap = cv2.VideoCapture(src)
        if not cap.isOpened() or cap.get(cv2.CAP_PROP_FRAME_COUNT) < 1:
            messagebox.showerror("Error", f"Could not open:\n{src}")
            return
        if self.cap:
            self.cap.release()
        self.cap, self.src, self.playing = cap, src, False
        self.fps = cap.get(cv2.CAP_PROP_FPS) or 30
        self.total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.start, self.end = 0, self.total - 1
        self.name.config(text=Path(src).name, fg=FG)
        self.seek(0)

    def seek(self, f):
        if not self.cap:
            return
        self.pos = min(max(int(f), 0), self.total - 1)
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.pos)
        ok, fr = self.cap.read()
        if ok:
            self.frame = fr
        self.refresh()

    def step(self, d):
        self.pause()
        # float = seconds, int = frames
        self.seek(self.pos + (round(d * self.fps) if isinstance(d, float) else d))

    def toggle(self):
        if not self.cap:
            return
        if self.playing:
            return self.pause()
        if self.pos >= self.total - 1:
            self.seek(0)
        self.playing = True
        self.bplay.config(text="❚❚  Pause")
        self.tick()

    def pause(self):
        self.playing = False
        self.bplay.config(text="▶  Play")

    def tick(self):
        if not self.playing:
            return
        ok, fr = self.cap.read()
        if not ok or self.pos >= self.total - 1:
            return self.pause()
        self.frame, self.pos = fr, self.pos + 1
        self.refresh()
        self.root.after(max(1, int(1000 / self.fps)), self.tick)

    # ---------- drawing ----------
    def refresh(self):
        self.show()
        self.draw()
        s = lambda f: f / self.fps
        self.clock.config(text=f"{fmt(s(self.pos))} / {fmt(s(self.total - 1))}")
        self.lstart.config(text=fmt(s(self.start)))
        self.lend.config(text=fmt(s(self.end)))
        self.ldur.config(text=f"⏱ {fmt(s(max(self.end - self.start, 0)))}")

    def show(self):
        if self.frame is None:
            return
        w, h = self.screen.winfo_width(), self.screen.winfo_height()
        if w < 2 or h < 2:
            return
        img = Image.fromarray(cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB))
        r = min(w / img.width, h / img.height)
        img = img.resize((max(1, int(img.width * r)), max(1, int(img.height * r))))
        self.photo = ImageTk.PhotoImage(img)
        self.screen.config(image=self.photo)

    def x_of(self, f):
        w = self.timeline.winfo_width() - 20
        return 10 + w * f / max(self.total - 1, 1)

    def f_of(self, x):
        w = self.timeline.winfo_width() - 20
        return round((x - 10) / max(w, 1) * (self.total - 1))

    def draw(self):
        c = self.timeline
        c.delete("all")
        w = c.winfo_width()
        c.create_rectangle(10, 16, w - 10, 28, fill=PANEL, outline="")
        if not self.cap:
            return
        xs, xe, xp = self.x_of(self.start), self.x_of(self.end), self.x_of(self.pos)
        c.create_rectangle(xs, 16, xe, 28, fill=ACCENT, outline="")
        for x, color in ((xs, START), (xe, END)):
            c.create_rectangle(x - 3, 8, x + 3, 36, fill=color, outline="")
        c.create_line(xp, 2, xp, 42, fill="white", width=2)
        c.create_oval(xp - 5, 0, xp + 5, 10, fill="white", outline="")

    # ---------- interaction ----------
    def click(self, e):
        if not self.cap:
            return
        self.pause()
        near = lambda f: abs(e.x - self.x_of(f)) <= 7
        self.dragging = "start" if near(self.start) else "end" if near(self.end) else "pos"
        self.drag(e)

    def drag(self, e):
        if not self.cap or not self.dragging:
            return
        f = min(max(self.f_of(e.x), 0), self.total - 1)
        if self.dragging == "start":
            self.start = min(f, self.end)
            self.seek(self.start)
        elif self.dragging == "end":
            self.end = max(f, self.start)
            self.seek(self.end)
        else:
            self.seek(f)

    def mark_start(self):
        if self.cap:
            self.start = self.pos
            self.end = max(self.end, self.start)
            self.refresh()

    def mark_end(self):
        if self.cap:
            self.end = self.pos
            self.start = min(self.start, self.end)
            self.refresh()

    def save(self):
        if not self.cap or str(self.bsave["state"]) == "disabled":
            return
        if self.end <= self.start:
            return messagebox.showwarning("Clip", "The end must be after the start.")
        self.pause()
        p = Path(self.src)
        dst = filedialog.asksaveasfilename(
            title="Save clip as", defaultextension=".mp4", initialdir=str(p.parent),
            initialfile=f"{p.stem}_clip.mp4", filetypes=[("MP4", "*.mp4")])
        if not dst:
            return
        start, end = self.start / self.fps, self.end / self.fps
        self.bsave.config(state="disabled", text="⏳  Saving...")
        self.status.config(text=f"Saving {fmt(start)} → {fmt(end)} ...", fg=FG)
        res = {}

        def work():
            try:
                trim(self.src, dst, start, end)
            except Exception as ex:
                res["error"] = getattr(ex, "stderr", b"")[-500:].decode(errors="ignore") or str(ex)

        t = threading.Thread(target=work, daemon=True)
        t.start()

        def wait():
            if t.is_alive():
                return self.root.after(200, wait)
            self.bsave.config(state="normal", text="💾  Save clip")
            if "error" in res:
                self.status.config(text="Save failed.", fg=END)
                messagebox.showerror("Save error", res["error"])
            else:
                self.status.config(text=f"✔ Saved: {dst}", fg=START)
        wait()


if __name__ == "__main__":
    if sys.platform == "win32":  # crisp text on displays scaled above 100%
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    root = Tk()
    App(root, sys.argv[1] if len(sys.argv) > 1 else None)
    root.mainloop()
