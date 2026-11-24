# UBE Tailor - Copyright (C) 2026 Desertravel. Licensed under the GNU GPL v3 or later (see LICENSE).
"""UBE Tailor window: pick outfits, convert them to UBE BodySlide projects, grade the fit, patch the plugins.
Start it with "UBE Tailor.bat" or from MO2's executables. The final Batch Build is done
in BodySlide. On the first start it asks for the Mod Organizer 2 modpack and shows what is installed / missing.
"""
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from collections import Counter
from tkinter import filedialog, messagebox, ttk

import env

tc = None                     # tailor_core: imported once the modpack and PyNifly are there (see main())

ALL = "All"
LEFT_OUT = "Left out of a converted outfit"
OUTDATED = "Made with an older Tailor"
# palette (dark teal + gold, matching the icon)
BG, PANEL, FIELD, HOVER = "#0f2228", "#17343c", "#0a181c", "#1f4650"
FG, MUTED, ACCENT, ACCENT2, GOLD, SEL = "#e8f2f3", "#8fb3b8", "#1fa6ac", "#2cc4ca", "#ffd166", "#1f5560"
GRADE = {"A": "#5fd38d", "B": GOLD, "C": "#ff7b7b"}
FONT, FONT_B, MONO = ("Segoe UI", 10), ("Segoe UI Semibold", 10), ("Consolas", 10)


def apply_theme(root):
    root.configure(bg=BG)
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=BG, foreground=FG, font=FONT, bordercolor=PANEL, lightcolor=PANEL,
                 darkcolor=PANEL, troughcolor=FIELD, focuscolor=BG)
    st.configure("TFrame", background=BG)
    st.configure("TLabel", background=BG, foreground=FG)
    st.configure("Title.TLabel", font=("Segoe UI Semibold", 20))
    st.configure("Sub.TLabel", foreground=MUTED)
    st.configure("TButton", background=PANEL, foreground=FG, padding=(14, 7), borderwidth=0, relief="flat")
    st.map("TButton", background=[("disabled", "#13282e"), ("pressed", ACCENT), ("active", HOVER)],
           foreground=[("disabled", "#56757a")])
    st.configure("Accent.TButton", background=ACCENT, foreground="#041417", font=FONT_B)
    st.map("Accent.TButton", background=[("disabled", "#14484c"), ("pressed", GOLD), ("active", ACCENT2)],
           foreground=[("disabled", "#5d8a8d")])
    st.configure("Card.TButton", background=HOVER, foreground=FG)       # a plain button on a PANEL card
    st.map("Card.TButton", background=[("pressed", ACCENT), ("active", "#2a5a66")])
    st.configure("Danger.TButton", background="#5a2a2e")
    st.map("Danger.TButton", background=[("disabled", "#13282e"), ("active", "#8a3138")])
    st.configure("TCombobox", fieldbackground=FIELD, background=PANEL, foreground=FG, arrowcolor=GOLD,
                 selectbackground=FIELD, selectforeground=FG, padding=4)
    st.map("TCombobox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", FG)],
           selectbackground=[("readonly", FIELD)], selectforeground=[("readonly", FG)])
    for k, v in (("background", FIELD), ("foreground", FG), ("selectBackground", SEL), ("selectForeground", FG)):
        root.option_add("*TCombobox*Listbox." + k, v)
    st.configure("TEntry", fieldbackground=FIELD, foreground=FG, insertcolor=FG, padding=4)
    st.configure("TSpinbox", fieldbackground=FIELD, foreground=FG, insertcolor=FG, arrowcolor=GOLD,
                 background=PANEL, padding=3)
    st.configure("TCheckbutton", background=BG, foreground=FG)
    st.map("TCheckbutton", background=[("active", BG)], indicatorcolor=[("selected", ACCENT), ("!selected", FIELD)])
    st.configure("Treeview", background=FIELD, fieldbackground=FIELD, foreground=FG, rowheight=26, borderwidth=0)
    st.map("Treeview", background=[("selected", SEL)], foreground=[("selected", FG)])
    st.configure("Treeview.Heading", background=PANEL, foreground=GOLD, font=FONT_B, relief="flat", padding=(6, 6))
    st.map("Treeview.Heading", background=[("active", HOVER)])
    st.configure("Vertical.TScrollbar", background=PANEL, troughcolor=BG, arrowcolor=MUTED, bordercolor=BG)
    st.map("Vertical.TScrollbar", background=[("active", ACCENT)])
    st.configure("Horizontal.TProgressbar", troughcolor=FIELD, background=ACCENT, bordercolor=FIELD,
                 lightcolor=ACCENT, darkcolor=ACCENT, thickness=12)
    try:                                  # dark title bar on Windows 10/11
        import ctypes
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        v = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(v), ctypes.sizeof(v))
    except Exception:
        pass


GROUP_NAME = "UBE Auto Conversions"   # make_projects.GROUP (not imported here: it needs PyNifly)
BUILD_STEPS = (f"close the Tailor, press F5 in MO2, start BodySlide from MO2, pick the group "
               f"'{GROUP_NAME}' and your preset, tick Build Morphs, press Batch Build. Then open the Tailor again: it "
               "scans by itself.")


class App:
    def __init__(self, root):
        self.root = root
        root.title("UBE Tailor")
        root.geometry("1200x800")
        root.minsize(980, 620)
        self.items, self.db, self.checked = [], {}, set()
        self.q = queue.Queue()
        self.busy = False
        self.stop_flag = False
        self.offered_fix = False
        self.osp_at_start = None        # project files when MO2 started us (what a BodySlide started by us sees)

        # header: picture, title, live counters
        head = ttk.Frame(root, padding=(14, 12, 14, 6))
        head.pack(fill="x")
        if getattr(root, "_art", None) is not None:
            ttk.Label(head, image=root._art).pack(side="left", padx=(0, 12))
        names = ttk.Frame(head)
        names.pack(side="left")
        ttk.Label(names, text="UBE Tailor", style="Title.TLabel").pack(anchor="w")
        ttk.Label(names, text="Turns 3BA outfits into UBE BodySlide projects", style="Sub.TLabel").pack(anchor="w")
        side = ttk.Frame(head)
        side.pack(side="left", padx=(24, 0))
        ttk.Label(side, style="Sub.TLabel", text=f"{os.path.basename(env.INSTANCE)}  ·  profile {env.L['profile_name']}"
                  ).pack(anchor="w")
        links = ttk.Frame(side)
        links.pack(anchor="w", pady=(4, 0))
        ttk.Button(links, text="Modpack...", command=lambda: SetupWindow(root)).pack(side="left", padx=(0, 6))
        ttk.Button(links, text="Requirements", command=lambda: RequirementsWindow(root, None, first=True)).pack(side="left")
        ttk.Button(links, text="Guide", command=lambda: WelcomeWindow(root)).pack(side="left", padx=(6, 0))
        ttk.Button(links, text="Copy report", command=self.do_report).pack(side="left", padx=(6, 0))
        # preset, workers, re-convert: up here, so a narrow window never hides them behind the buttons
        opts = ttk.Frame(side)
        opts.pack(anchor="w", pady=(6, 0))
        ttk.Label(opts, text="Preset", style="Sub.TLabel").pack(side="left")
        self.preset = ttk.Combobox(opts, width=18, state="readonly")
        self.preset.pack(side="left", padx=(4, 14))
        self.preset.bind("<<ComboboxSelected>>", lambda _e: env.set_preset(self.preset.get()))
        ttk.Label(opts, text="Workers", style="Sub.TLabel").pack(side="left")
        self.workers = tk.IntVar(value=min(6, max(1, (os.cpu_count() or 4) // 2)))
        self._workers_now = self.workers.get()      # read by the running job: the box works while the Tailor works
        self.workers.trace_add("write", self._workers_changed)
        ttk.Spinbox(opts, from_=1, to=16, width=4, textvariable=self.workers).pack(side="left", padx=(4, 14))
        self.redo = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Re-convert done ones", variable=self.redo).pack(side="left")
        self.chips = {}
        chips = ttk.Frame(head)
        chips.pack(side="right")
        for key, label, col in (("done", "Done", GRADE["A"]), ("built", "Needs patch", ACCENT2),
                                ("pending", "To convert", GOLD)):
            box = tk.Frame(chips, bg=PANEL, padx=14, pady=6)
            box.pack(side="right", padx=4)
            num = tk.Label(box, text="-", bg=PANEL, fg=col, font=("Segoe UI Semibold", 16))
            num.pack()
            tk.Label(box, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack()
            self.chips[key] = num

        top = ttk.Frame(root, padding=(14, 6))
        top.pack(fill="x")
        self.btn_scan = ttk.Button(top, text="Scan", command=self.do_scan)
        self.btn_conv = ttk.Button(top, text="Convert selected", command=self.do_convert, style="Accent.TButton")
        self.btn_qa = ttk.Button(top, text="Check fit", command=self.do_qa)
        self.btn_fix = ttk.Button(top, text="Fix clipping", command=self.do_fix)
        self.btn_patch = ttk.Button(top, text="Update patch", command=self.do_patch)
        self.btn_doc = ttk.Button(top, text="Health check", command=self.do_doctor)
        self.btn_bs = ttk.Button(top, text="BodySlide", command=self.do_bodyslide)
        self.btn_os = ttk.Button(top, text="Outfit Studio", command=self.do_outfit_studio)
        self.btn_stop = ttk.Button(top, text="Stop", command=self.do_stop, state="disabled", style="Danger.TButton")
        for b in (self.btn_scan, self.btn_conv, self.btn_bs, self.btn_os, self.btn_qa, self.btn_fix, self.btn_patch,
                  self.btn_doc, self.btn_stop):
            b.pack(side="left", padx=(0, 6))

        flt = ttk.Frame(root, padding=(14, 4))
        flt.pack(fill="x")
        ttk.Label(flt, text="Search", style="Sub.TLabel").pack(side="left")
        self.text = tk.StringVar()
        e = ttk.Entry(flt, textvariable=self.text, width=28)
        e.pack(side="left", padx=(6, 14))
        e.bind("<KeyRelease>", lambda _e: self.populate())
        ttk.Label(flt, text="Show", style="Sub.TLabel").pack(side="left")
        self.kind = ttk.Combobox(flt, width=16, state="readonly", values=list(tc.KINDS.values()) + [ALL])
        self.kind.set(tc.KINDS["clothing"])            # default: outfits only, no jewelry / devices / NPC parts
        self.kind.pack(side="left", padx=(6, 14))
        self.kind.bind("<<ComboboxSelected>>", lambda _e: self.populate())
        ttk.Label(flt, text="State", style="Sub.TLabel").pack(side="left")
        self.state = ttk.Combobox(flt, width=26, state="readonly", values=[ALL, LEFT_OUT, OUTDATED] + list(tc.STATES.values()))
        self.state.set(tc.STATES["pending"])
        self.state.pack(side="left", padx=(6, 14))
        self.state.bind("<<ComboboxSelected>>", lambda _e: self.populate())
        ttk.Button(flt, text="Select shown", command=lambda: self.check_visible(True)).pack(side="left", padx=(0, 6))
        ttk.Button(flt, text="Clear selection", command=lambda: self.check_visible(False)).pack(side="left")
        self.count = ttk.Label(flt, text="", style="Sub.TLabel")
        self.count.pack(side="right")

        ttk.Label(root, style="Sub.TLabel", padding=(14, 0), text=(
            "Tip: right-click a piece or a mod for more - Fix clipping for just that piece, outfit or mod, and Open "
            "in Outfit Studio to touch it up by hand (the Tailor then leaves your edits alone).")).pack(anchor="w")
        mid = ttk.Frame(root, padding=(14, 6))
        mid.pack(fill="both", expand=True)
        self._mid = mid
        # shown only while MO2 still needs the output mod / plugin ticked (watch -> show_mo2)
        self.mo2_bar = tk.Label(root, text="", bg="#3a3216", fg=GOLD, font=FONT_B, anchor="w", justify="left",
                                padx=14, pady=8, wraplength=1100)
        cols = ("check", "state", "grade", "slots")
        self.tree = ttk.Treeview(mid, columns=cols, selectmode="none")
        self.tree.heading("#0", text="Mod / piece", anchor="w")
        for c, t, w in (("check", "✓", 46), ("state", "State", 210), ("grade", "Fit · moving", 330), ("slots", "Slots", 120)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="center", stretch=False)
        self.tree.column("#0", width=540)
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<Button-1>", self.on_click)
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.tag_configure("grp", font=FONT_B, foreground="#bfe9ec", background=PANEL)
        self.tree.tag_configure("odd", background="#0d1e23")
        for g, col in GRADE.items():
            self.tree.tag_configure(g, foreground=col)

        bot = ttk.Frame(root, padding=(14, 4))
        bot.pack(fill="x")
        self.bar = ttk.Progressbar(bot, maximum=100)
        self.bar.pack(fill="x")
        line = ttk.Frame(bot)
        line.pack(fill="x", pady=(3, 0))
        self.status = ttk.Label(line, text="Ready", style="Sub.TLabel")
        self.status.pack(side="left")
        tk.Label(line, text=f"UBE Tailor {env.VERSION}  ·  by {env.AUTHOR}", bg=BG, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="right")
        self.game_lbl = tk.Label(line, text="", bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.game_lbl.pack(side="right", padx=(0, 18))
        self.log = tk.Text(root, height=9, wrap="word", bg=FIELD, fg="#cfe6e8", insertbackground=FG, font=MONO,
                           relief="flat", padx=10, pady=8, highlightthickness=0)
        self.log.tag_configure("bad", foreground=GRADE["C"])
        self.log.tag_configure("next", foreground=GOLD)
        self.log.pack(fill="both", padx=14, pady=(4, 14))

        root.after(100, self.poll)
        root.after(120, self.prepare_output)
        root.after(150, self.check_game)
        root.after(200, self.do_scan)

    def new_projects(self):
        """Project files made since MO2 started the Tailor: a BodySlide started from here cannot see them."""
        if self.osp_at_start is None or not env.inside_mo2():
            return set()
        return tc.project_files() - self.osp_at_start

    def build_hint(self, why):
        """The 'Next:' line after converting or fixing: BodySlide from here, or (new projects) from MO2."""
        if self.new_projects():
            return f"Next: {BUILD_STEPS} ({why})"
        return (f"Next: press BodySlide -> group '{GROUP_NAME}' -> your preset -> tick Build Morphs -> Batch Build "
                f"({why}). Close BodySlide when it is done - the Tailor then scans by itself.")

    def do_bodyslide(self):
        """Open BodySlide (through MO2, so it sees the mods); when it is closed the Tailor scans again (watch)."""
        if tc.running("SkyrimSE.exe"):
            messagebox.showwarning("UBE Tailor", "The game is running. Close it first.")
            return
        # MO2 shows a program the mod folders as they were when it started the program, and BodySlide started from
        # here gets our view: projects converted since then are new files it cannot see, so Batch Build skipped
        # them without a word (the vanilla rings). Re-converted ones are fine (their files were there already).
        # Nobody wants half a Batch Build, so then the button only says how to build them (no Yes/No to get wrong).
        new = self.new_projects()
        if new:
            messagebox.showinfo("UBE Tailor", (
                f"{len(new)} project(s) were made since you opened the Tailor. A BodySlide started from here cannot "
                "see them (MO2 shows it the files as they were when it started the Tailor).\n\nTo build them: "
                + BUILD_STEPS))
            return
        ok, msg = env.launch_bodyslide()
        self.say(msg)
        if ok:
            self.say(f"Next: in BodySlide pick the group '{GROUP_NAME}', your preset, tick Build Morphs, press Batch "
                     "Build. Close BodySlide when it is done - the Tailor then scans by itself.")
        else:
            messagebox.showinfo("UBE Tailor", msg)

    # ------------------------------------------------------------ MO2: output mod + plugin, BodySlide closing
    def prepare_output(self):
        """First start: make the output mod with an empty UBE Tailor.esp, so MO2 lists both at once; then keep
        watching MO2 and BodySlide."""
        import merged_patch
        if merged_patch.ensure_plugin():
            self.say(f"Made the mod '{os.path.basename(env.OUT_MOD)}' with an empty UBE Tailor.esp - the Tailor fills "
                     "it when you convert outfits.")
        threading.Thread(target=self.watch, daemon=True).start()

    def watch(self):
        """Every 3 s: does MO2 have the output mod and plugin ticked, and has BodySlide just been closed (then the
        Tailor scans again, so the patch uses what BodySlide built)."""
        import merged_patch
        was = was_os = False
        while True:
            try:
                bs = tc.running("BodySlide x64.exe") or tc.running("BodySlide.exe")
                ost = tc.running("OutfitStudio x64.exe") or tc.running("OutfitStudio.exe")
                self.q.put(("mo2", merged_patch.mo2_status()))
                if was and not bs:
                    self.q.put(("autoscan", None))
                if was_os and not ost:
                    marked = tc.check_hand_edits(False)
                    if marked:
                        self.q.put(("hand", marked))
                was, was_os = bs, ost
            except Exception:
                pass
            time.sleep(3)

    def show_mo2(self, st):
        """MO2 closed: enable the mod / tick the plugin ourselves. MO2 open: it would overwrite that, so show a bar
        that says what to tick, and wait until the user did it."""
        import merged_patch
        name = os.path.basename(env.OUT_MOD)
        need = ([f"the mod '{name}' (left side)"] if not st["mod"] else []) + \
               ([f"the plugin {', '.join(st['unticked'])} (right side, at the bottom)"] if st["unticked"] else [])
        if need and not st["mo2"] and not self.busy and env.can_edit_profile():
            if merged_patch.place_in_load_order(st["files"]):
                self.say(f"Enabled the mod '{name}' in MO2 and ticked {', '.join(st['files'])} at the end of the "
                         "load order.")
                need = []
        if need:
            self.mo2_bar["text"] = ("⚠  In MO2: press F5, then tick " if st["mo2"] else "⚠  Start MO2 and tick ") + \
                " and ".join(need) + ". BodySlide and the game only see the Tailor's work then. The Tailor waits - " \
                "this bar goes away as soon as they are ticked."
            if not self.mo2_bar.winfo_ismapped():
                self.mo2_bar.pack(fill="x", padx=14, pady=(2, 4), before=self._mid)
        elif self.mo2_bar.winfo_ismapped():
            self.mo2_bar.pack_forget()
            self.say(f"MO2: the mod '{name}' and {', '.join(st['files'])} are ticked - ready.")

    # ------------------------------------------------------------ the game: SE or AE
    def check_game(self):
        """Show which Skyrim the modpack runs; ask when the Tailor cannot read it; warn when that version cannot load
        every plugin of the modpack (header 1.71 plugins on SE / old AE without BEES)."""
        import requirements
        if env.game_edition()[0] is None:
            ask_edition(self.root)
        it = requirements.game_item()
        ed, ver = env.game_edition()
        self.game_lbl["text"] = f"Skyrim {ed} {ver}".strip() if ed else "Skyrim version unknown"
        if not it.ok and it.url:
            self.say("Warning: " + it.detail)
            self.say("   " + it.how + "  " + it.url)

    # ------------------------------------------------------------ helpers
    def say(self, s):
        self.q.put(("log", s))

    def poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    tag = "bad" if ("failed:" in val or val.startswith(("Error", "Warning"))) else "next" if val.startswith("Next:") else ""
                    self.log.insert("end", val + "\n", tag)
                    self.log.see("end")
                elif kind == "prog":
                    i, total, text = val
                    self.bar["value"] = 100.0 * i / max(total, 1)
                    self.status["text"] = text
                elif kind == "scan":
                    self.items, self.db, presets = val
                    if presets and not self.preset["values"]:
                        self.preset["values"] = presets
                        if env.preset() in presets:
                            self.preset.set(env.preset())
                        else:
                            self.say("Next: pick your UBE body preset (top, under Modpack...) - the one you build your UBE body "
                                     "with in BodySlide. The fit check uses it.")
                    self.populate()
                elif kind == "ask":
                    self.ask_new(val)
                elif kind == "fix":
                    self.root.after(300, lambda v=val: self.offer_fix(*v))   # after the busy state clears
                elif kind == "clip":
                    self.root.clipboard_clear()
                    self.root.clipboard_append(val)
                    # also as a file next to the Tailor, to attach to a bug report; the folder opens with it selected
                    path = os.path.join(env.TOOL, "UBE Tailor report.txt")
                    try:
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(val.strip("`\n") + "\n")
                        subprocess.Popen(["explorer", "/select,", path])
                        where = f" and saved as '{os.path.basename(path)}' in the Tailor's folder (opened for you)"
                    except OSError:
                        where = ""
                    self.say(f"Report copied{where}. Paste it (Ctrl+V) or attach the file in your bug report on "
                             "Nexus or GitHub. It has no personal data: your user folder is replaced by %USERPROFILE%.")
                elif kind == "hand":
                    self.db = tc.load_db()
                    self.say(f"Edited by hand in Outfit Studio: {', '.join(n[11:] for n in val[:3])}"
                             + (f" and {len(val) - 3} more" if len(val) > 3 else "")
                             + " - Fix clipping and Re-convert leave it alone now. Run Batch Build to see it in game.")
                    self.populate()
                elif kind == "fix_new":
                    self.root.after(300, lambda v=val: self.offer_fix_new(v))   # after the busy state clears
                elif kind == "doctor":
                    self.root.after(300, lambda v=val: self.show_doctor(v))
                elif kind == "mo2":
                    self.show_mo2(val)
                elif kind == "autoscan":
                    if not self.busy:
                        self.say("BodySlide was closed - scanning again to use what it built...")
                        self.do_scan()
                elif kind == "done":
                    self.set_busy(False)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def set_busy(self, b):
        self.busy = b
        self.stop_flag = False
        for w in (self.btn_scan, self.btn_conv, self.btn_bs, self.btn_os, self.btn_qa, self.btn_fix, self.btn_patch,
                  self.btn_doc):
            w["state"] = "disabled" if b else "normal"
        self.btn_stop["state"] = "normal" if b else "disabled"
        if not b:
            self.status["text"] = "Ready"

    def run(self, fn):
        if self.busy:
            return
        self.set_busy(True)

        def work():
            try:
                fn()
            except Exception as e:
                self.say(f"Error: {e!r}")
            self.q.put(("done", None))
        threading.Thread(target=work, daemon=True).start()

    def do_stop(self):
        self.stop_flag = True
        self.say("Stopping...")

    def rescan(self):
        items = tc.scan()
        db = tc.load_db()
        self.q.put(("scan", (items, db, tc.list_presets())))
        return items

    @staticmethod
    def counts(items):
        c = Counter(i["state"] for i in items)
        return ", ".join(f"{tc.STATES[k]} {v}" for k, v in c.items())

    # ------------------------------------------------------------ list
    def of_kind(self):
        """Items of the type picked in 'Show' (clothing only by default)."""
        k = self.kind.get()
        return [i for i in self.items if k == ALL or tc.KINDS[i["kind"]] == k]

    def visible(self):
        text = self.text.get().lower()
        st = self.state.get()
        kind = self.of_kind()
        # "left out" / "older Tailor" are judged on the whole list (a left-out piece is one of an outfit converted
        # before), then cut to the type picked in Show like every other state
        pool = kind
        if st in (LEFT_OUT, OUTDATED):
            keep = {i["base"].lower() for i in kind}
            pool = [i for i in (tc.left_out(self.items) if st == LEFT_OUT else tc.outdated(self.items))
                    if i["base"].lower() in keep]
        return [i for i in pool
                if (st in (ALL, LEFT_OUT, OUTDATED) or tc.STATES[i["state"]] == st)
                and (text in i["base"].lower() or text in i["plugin"].lower())]

    def grade_text(self, it):
        qa = self.db.get(it["set"], {}).get("qa")
        if not qa:
            return ("edited by hand", None) if self.db.get(it["set"], {}).get("hand") else ("", None)
        worst = max(qa.get("in0", 0), qa.get("in1", 0))
        text, g = f"{tc.GRADES[qa['grade']]} ({worst} pts inside)", qa["grade"]
        mg = qa.get("motion")
        if mg:                                   # moving: how the piece follows the body's bones
            text += f" · moving {mg}" + (f" ({qa['motion_pct']}% at {qa['motion_bone']})" if mg != "A" else "")
            g = max(g, mg)                       # the worse of the two colours the row
        if self.db.get(it["set"], {}).get("fixed"):
            text += " · clipping fixed"
        if self.db.get(it["set"], {}).get("hand"):
            text += " · edited by hand"
        return text, g

    def populate(self):
        opened = {p for p in self.tree.get_children() if self.tree.item(p, "open")}
        self.tree.delete(*self.tree.get_children())
        vis = self.visible()
        groups = {}
        for it in vis:
            groups.setdefault(it["plugin"], []).append(it)
        for plugin, lst in groups.items():
            pid = "p:" + plugin
            n = sum(1 for i in lst if i["base"].lower() in self.checked)
            mark = "☑" if n == len(lst) else ("◪" if n else "☐")
            le = tc.FORMATS.get(lst[0].get("format", "SE"), "")
            self.tree.insert("", "end", iid=pid, text=f"  {plugin}   ({len(lst)})" + (f"   ⚠ {le}" if le else ""),
                             values=(mark, "", "", ""),
                             open=pid in opened or len(groups) <= 3, tags=("grp",))
            for k, it in enumerate(lst):
                g, grade = self.grade_text(it)
                tags = tuple(t for t in (grade, "odd" if k % 2 else None) if t)
                self.tree.insert(pid, "end", iid=it["base"].lower(), text=it["base"], tags=tags,
                                 values=("☑" if it["base"].lower() in self.checked else "☐",
                                         tc.STATES[it["state"]] + (f" · {it['by']}" if it.get("by") else ""), g,
                                         ", ".join(map(str, it["slots"]))))
        kind = self.of_kind()
        c = Counter(i["state"] for i in kind)
        for key, lab in self.chips.items():
            lab["text"] = f"{c.get(key, 0):,}"
        hint = ""
        text = self.text.get().lower()
        if text and self.state.get() != ALL:
            more = sum(1 for i in kind if text in i["base"].lower() or text in i["plugin"].lower()) - len(vis)
            if more > 0:
                hint = f"    (+{more:,} more match: set State to '{ALL}')"
        self.count["text"] = f"shown {len(vis):,}    selected {len(self.checked):,}    of {len(kind):,}" + hint

    def on_click(self, ev):
        row = self.tree.identify_row(ev.y)
        # a piece ticks wherever its row is clicked; a mod row only in the tick column (its name opens / closes it)
        if not row or (row.startswith("p:") and self.tree.identify_column(ev.x) != "#1"):
            return
        if row.startswith("p:"):
            kids = self.tree.get_children(row)
            on = not all(k in self.checked for k in kids)
            (self.checked.update if on else self.checked.difference_update)(kids)
        else:
            self.checked.symmetric_difference_update({row})
        self.populate()
        return "break"

    def on_right_click(self, ev):
        """Right-click on a piece: Fix clipping for it or its whole mod, open it in Outfit Studio. On a mod row:
        Fix clipping for every converted piece of that mod (search the mod's name, right-click it, done)."""
        row = self.tree.identify_row(ev.y)
        if not row:
            return
        conv = ("built", "done")
        if row.startswith("p:"):
            plugin, it = row[2:], None
        else:
            it = next((i for i in self.items if i["base"].lower() == row), None)
            if not it:
                return
            plugin = it["plugin"]
        mod = [i for i in self.items if i["plugin"] == plugin and i["state"] in conv]
        # a collection plugin holds many outfits: the pieces of one outfit share their mesh folder
        shown = [i for i in self.visible() if i["plugin"] == plugin and i["state"] in conv]
        menu = tk.Menu(self.root, tearoff=0)
        if it:
            if it["state"] in conv:
                menu.add_command(label="Fix clipping: this piece", command=lambda: self.open_fix([it]))
                keys = tc._outfit_keys(self.items)
                key = keys.get(it["base"].lower())
                outfit = [i for i in mod if key is not None and keys.get(i["base"].lower()) == key]
                if 1 < len(outfit) < len(mod):
                    folder = os.path.basename(os.path.dirname(it["base"]))
                    menu.add_command(label=f"Fix clipping: this outfit ({folder}, {len(outfit)} pieces)",
                                     command=lambda: self.open_fix(outfit))
            else:
                menu.add_command(label="Fix clipping: this piece (convert it first)", state="disabled")
        if self.text.get().strip() and 0 < len(shown) < len(mod):
            menu.add_command(label=f"Fix clipping: the {len(shown)} shown (search '{self.text.get().strip()}')",
                             command=lambda: self.open_fix(shown))
        menu.add_command(label=f"Fix clipping: all of {plugin} ({len(mod)} converted)",
                         command=lambda: self.open_fix(mod), state="normal" if mod else "disabled")
        if it:
            menu.add_separator()
            if it["state"] in conv:
                menu.add_command(label="Open in Outfit Studio", command=lambda: self.open_outfit_studio(it))
            else:
                menu.add_command(label="Open in Outfit Studio (convert it first)", state="disabled")
        menu.tk_popup(ev.x_root, ev.y_root)
        return "break"

    def do_outfit_studio(self):
        """Open the one ticked converted piece in Outfit Studio (the same as right-click > Open in Outfit Studio)."""
        sel = self.chosen(("built", "done"))
        if len(sel) != 1:
            messagebox.showinfo("UBE Tailor", (
                "Tick one converted piece (click it in the list), then press Outfit Studio - or right-click the piece "
                "and pick 'Open in Outfit Studio'.\n\nTouch it up there, save the project (File > Save Project), "
                "close Outfit Studio and run Batch Build. The Tailor marks the piece 'edited by hand' and Fix "
                "clipping / Re-convert leave it alone."))
            return
        self.open_outfit_studio(sel[0])

    def open_outfit_studio(self, it):
        name = tc.set_name_of(it["base"])
        path = tc.osp_of(it["base"])
        if os.path.basename(path).lower() in self.new_projects():
            messagebox.showinfo("UBE Tailor", (
                "This project was made since you opened the Tailor, so an Outfit Studio started from here cannot "
                f"see it.\n\nClose the Tailor, start Outfit Studio from MO2, then File > Load Project > '{name}'."))
            return
        ok, msg = env.launch_outfit_studio(name, path)
        self.say(msg)
        if ok:
            tc.mark_opened(name)            # when its project changes, the piece is 'edited by hand'
            self.say("   When you save it there, the Tailor marks it 'edited by hand': Fix clipping and Re-convert "
                     "leave it alone (you can still choose to include it).")
        else:
            messagebox.showinfo("UBE Tailor", msg)

    def check_visible(self, on):
        keys = {i["base"].lower() for i in self.visible()}
        (self.checked.update if on else self.checked.difference_update)(keys)
        self.populate()

    def chosen(self, states):
        return [i for i in self.items if i["base"].lower() in self.checked and i["state"] in states]

    def why_nothing(self):
        """Why Convert found nothing to do among the ticked pieces, in words."""
        ticked = [i for i in self.items if i["base"].lower() in self.checked]
        if not ticked:
            return ("No piece is ticked. Click a piece (or the box in the ✓ column) to tick it, or press "
                    "'Select shown' to tick every piece in the list.")
        c = Counter(i["state"] for i in ticked)
        if not self.redo.get() and (c.get("built") or c.get("done")):
            return (f"The {c.get('built', 0) + c.get('done', 0)} ticked piece(s) are converted already. To convert "
                    "them again, tick 'Re-convert done ones' (next to Workers) and press Convert again.")
        return ("None of the ticked pieces can be converted: " + ", ".join(
            f"{v} {tc.STATES[k]}" for k, v in c.most_common()) + ". Head pieces need no UBE version, native and "
            "hand-made UBE pieces are UBE already, and a missing or old LE mesh has to be fixed in its mod first.")

    # ------------------------------------------------------------ actions
    def do_scan(self):
        def work():
            if self.osp_at_start is None:
                self.osp_at_start = tc.project_files()
            try:
                tc.settle_method(log=self.say)         # once: only pieces the new method changes are outdated
            except Exception as e:
                self.say(f"Could not check the pieces converted before: {e}")
            try:
                tc.restore_crotch(log=self.say)        # once per piece: projects made before 0.9.3 cut the vulva
            except Exception as e:
                self.say(f"Could not check the converted pieces' crotch: {e}")
            try:
                tc.drop_handmade(log=self.say)         # a hand-made UBE version of a converted outfit wins
            except Exception as e:
                self.say(f"Could not check for hand-made UBE versions: {e}")
            if not tc.running("SkyrimSE.exe"):
                self.say("Updating the patches to the meshes BodySlide has built...")
                for line in tc.repoint(False).strip().splitlines()[-2:]:
                    self.say("   " + line)
            self.say("Scanning the mod list...")
            items = self.rescan()
            self.say(f"Found {len(items)} pieces: {self.counts(items)}")
            lo, old = tc.left_out(items), tc.outdated(items)
            if lo:
                outfits = sorted({os.path.dirname(i["base"]) for i in lo})
                self.say(f"Next: {len(lo)} piece(s) of {len(outfits)} outfit(s) you converted are still 3BA and will not "
                         f"fit the UBE body (State: '{LEFT_OUT}').")
            if old:
                self.say(f"Next: {len(old)} piece(s) were converted with an older version of the Tailor "
                         f"(State: '{OUTDATED}').")
            if not self.offered_fix:
                self.offered_fix = True                 # health check once per start, not after every scan
                self._doctor(auto=True)
        self.run(work)

    def _workers_changed(self, *_a):
        try:
            n = int(self.workers.get())
        except (tk.TclError, ValueError):
            return                                  # half-typed number: keep the last one
        if n >= 1:
            if getattr(self, "busy", False) and n != self._workers_now:
                self.say(f"Workers: {self._workers_now} -> {n} (the running job follows)")
            self._workers_now = n

    def live_workers(self):
        """How many workers a running job should use now (read from its thread; set by the Workers box)."""
        return self._workers_now

    def do_report(self):
        """Copy a short report for a bug report to the clipboard: versions, what the list holds, the health check
        and the end of the log. The user's own folder is replaced by %USERPROFILE%."""
        if self.busy:
            return
        log_tail = self.log.get("end-160l", "end").strip()

        def work():
            import doctor
            self.say("Making the report (runs the health check)...")
            gv = env.game_version()
            bs = env.bodyslide_exe()
            lines = [f"UBE Tailor {env.VERSION}",
                     "Skyrim " + (".".join(map(str, gv)) if gv else "version unknown"),
                     "BodySlide: " + (f"{os.path.basename(bs)} ({time.strftime('%Y-%m-%d', time.localtime(os.path.getmtime(bs)))})"
                                      f", add-ons {'yes' if env.bodyslide_reads_addons() else 'no'}" if bs else "not found"),
                     f"Inside MO2: {'yes' if env.inside_mo2() else 'no'}",
                     f"Preset: {env.preset() or '-'}; Fix clipping presets: {', '.join(env.S.get('fix_presets') or []) or '-'}",
                     "Pieces: " + (self.counts(self.items) if self.items else "not scanned"), "", "Health check:"]
            try:
                found = doctor.check()
                lines += [f"  [{f.level}] {f.title}" for f in found] or ["  all good"]
            except Exception as e:
                lines.append(f"  could not run: {e!r}")
            lines += ["", "Log (last lines):", log_tail]
            text = "\n".join(lines)
            home = os.path.expanduser("~")
            for h in {home, home.replace("\\", "/")}:
                text = text.replace(h, "%USERPROFILE%")
            self.q.put(("clip", "```\n" + text + "\n```"))
        self.run(work)

    # ------------------------------------------------------------ health check
    def _doctor(self, auto=False):
        import doctor
        found = doctor.check(log=self.say)
        if found and (not auto or any(f.level in ("fix", "you") for f in found)):
            self.q.put(("doctor", found))
        elif not auto:
            self.say("Health check: all good, nothing to repair.")

    def do_doctor(self):
        self.run(lambda: self._doctor(auto=False))

    def show_doctor(self, found):
        win = tk.Toplevel(self.root, bg=BG, padx=16, pady=12)
        win.title("Health check")
        win.transient(self.root)
        ttk.Label(win, text="Health check", style="Title.TLabel").pack(anchor="w")
        ttk.Label(win, style="Sub.TLabel", text="What the Tailor found, and what it can repair by itself.").pack(
            anchor="w", pady=(0, 8))
        colour = {"fix": GOLD, "you": ACCENT2, "info": MUTED}
        label = {"fix": "Can repair", "you": "Your step", "info": "Good to know"}
        for f in found:
            row = tk.Frame(win, bg=BG)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label[f.level], bg=BG, fg=colour[f.level], font=FONT_B, width=12, anchor="w").pack(
                side="left", anchor="n")
            tk.Label(row, text=f.title, bg=BG, fg=FG, font=FONT, wraplength=640, justify="left", anchor="w").pack(
                side="left", fill="x")
        btns = ttk.Frame(win)
        btns.pack(anchor="e", pady=(12, 0))
        fixable = [f for f in found if f.level == "fix"]

        def go():
            win.destroy()
            if tc.running("SkyrimSE.exe"):
                messagebox.showwarning("UBE Tailor", "The game is running. Close it first.")
                return
            import doctor

            def work():
                doctor.fix(found, self.preset.get(), self.live_workers, log=self.say, stop=lambda: self.stop_flag)
                self.rescan()
            self.run(work)
        if fixable:
            ttk.Button(btns, text=f"Fix all ({len(fixable)})", command=go, style="Accent.TButton").pack(side="left", padx=4)
        ttk.Button(btns, text="Close", command=win.destroy).pack(side="left", padx=4)

    def offer_fix(self, lo, old):
        parts = []
        if lo:
            parts.append(f"{len(lo)} piece(s) left out of outfits you converted (they would not fit the UBE body)")
        if old:
            parts.append(f"{len(old)} piece(s) converted with an older version of the Tailor")
        if messagebox.askyesno("UBE Tailor", "The Tailor found:\n\n- " + "\n- ".join(parts) +
                               "\n\nConvert them now? Head pieces are skipped on their own. "
                               "Afterwards run Batch Build in BodySlide."):
            self.convert_items(lo + old, self.preset.get())

    def _qa(self, sets, preset):
        t0 = time.time()
        grades = Counter()

        def on(i, total, name, res, err):
            if err:
                self.say(f"   failed: could not check {name[11:]}: {err}")
            else:
                grades[res["grade"]] += 1
            self.q.put(("prog", (i, total, f"Checking fit {i}/{total}")))
        tc.qa(sets, preset, self.live_workers, on, lambda: self.stop_flag)
        self.say(f"Fit on {preset}: " + ", ".join(f"{tc.GRADES[g]} {n}" for g, n in sorted(grades.items()))
                 + f"  ({time.time() - t0:.0f} s)")

    def do_convert(self):
        sel = self.chosen(("pending", "built", "done") if self.redo.get() else ("pending",))
        if not sel:
            messagebox.showinfo("UBE Tailor", self.why_nothing())
            return
        db = tc.load_db()
        hand = [i for i in sel if tc.hand_edited(db, i["set"])]
        if hand and not messagebox.askyesno("UBE Tailor", (
                f"{len(hand)} of the ticked pieces were edited by hand in Outfit Studio. Converting them again "
                "replaces your edits.\n\nConvert those too? (No = convert the others and leave them as they are)")):
            sel = [i for i in sel if i not in hand]
            if not sel:
                return
        if tc.running("SkyrimSE.exe"):
            messagebox.showwarning("UBE Tailor", "The game is running. Close it first.")
            return
        self.convert_items(sel, self.preset.get())

    def convert_items(self, sel, preset):
        if tc.running("SkyrimSE.exe"):
            messagebox.showwarning("UBE Tailor", "The game is running. Close it first.")
            return
        mates = tc.outfit_mates(sel, self.items)     # never leave half an outfit in 3BA
        sel = sel + mates
        le = sorted({i["plugin"] for i in sel if i.get("format", "SE") != "SE"}, key=str.lower)
        if le and not messagebox.askyesno(
                "UBE Tailor", f"{len(le)} of these outfit mods {'is' if len(le) == 1 else 'are'} "
                + tc.LE_NOTE + "\n\n- " + "\n- ".join(le[:12]) + ("\n- ..." if len(le) > 12 else "")
                + "\n\nConvert them anyway?"):
            return

        def work():
            t0 = time.time()
            if mates:
                self.say(f"Also converting {len(mates)} more piece(s) of the same outfits, so each outfit is complete.")
            self.say(f"Converting {len(sel)} pieces...")

            retried = set()

            def on(i, total, base, name, err, lines):
                if err and err.startswith("RETRY: "):
                    retried.add(base)
                    self.say(f"   {base}: the mesh library crashed ({err[7:]}) - tried again at the end, in a fresh process")
                elif base in retried and name and not err:
                    self.say(f"   {base}: OK on the second try")
                elif err and err.startswith(("HEAD: ", "OLDRIM: ", "MISSING: ")):
                    self.say(f"   skipped: {base}  ({err.split(': ', 1)[1]})")
                elif err:
                    self.say(f"   failed: {base}  {err}")
                elif name is None:
                    self.say("   " + base)
                self.q.put(("prog", (i, total, f"Converting {i}/{total}   {(time.time() - t0) / max(i, 1):.1f} s per piece")))
            prep = lambda i, total: self.q.put(("prog", (i, total, f"Copying the outfit meshes {i}/{total}   "
                                                                   "(first step, then the conversion starts)")))
            made, failed = tc.convert([i["base"] for i in sel], self.live_workers, on, lambda: self.stop_flag, prep)
            self.say(f"Converted {len(made)}, failed {len(failed)}  ({time.time() - t0:.0f} s)")
            if made and preset and not self.stop_flag:
                self._qa(made, preset)
            if made and not self.stop_flag:
                self.say(tc.repoint(False).strip().splitlines()[-1])
                self.say(self.build_hint("the patch switches each piece to its UBE mesh once it is built; run Fix "
                                         "clipping first if you want it"))
            self.rescan()
            if made and not self.stop_flag and env.S.get("fix_after_convert", "ask") == "ask":
                self.q.put(("fix_new", list(made)))
        self.run(work)

    def offer_fix_new(self, made):
        """After a conversion: Fix clipping just for the new pieces? Yes / No / Don't ask again (FixWindow has the
        tick to turn the question back on)."""
        presets = [p for p in (env.S.get("fix_presets") or ()) if p in (self.preset["values"] or ())]
        win = tk.Toplevel(self.root, bg=BG, padx=18, pady=14)
        win.title("Fix clipping")
        win.transient(self.root)
        ttk.Label(win, text=f"Fix clipping for the {len(made)} new piece(s)?", style="Title.TLabel").pack(anchor="w")
        if presets:
            text = (f"Only the pieces you just converted, for your presets from last time: {', '.join(presets)}. "
                    "Pieces fixed before are not touched.")
        else:
            text = "Only the pieces you just converted. You pick the presets in the next window."
        ttk.Label(win, style="Sub.TLabel", wraplength=520, justify="left", text=text).pack(anchor="w", pady=(4, 12))
        bot = ttk.Frame(win)
        bot.pack(fill="x")

        def yes():
            win.destroy()
            if presets:
                self.run_fix(made, presets)
            else:
                FixWindow(self, made, list(self.preset["values"]) or tc.list_presets(), ticked=True)

        def never():
            env.S["fix_after_convert"] = "never"
            env.save_settings(env.S)
            win.destroy()
            self.say("The Tailor will not ask again after converting (turn it back on in the Fix clipping window).")
        ttk.Button(bot, text="Yes, fix them", command=yes, style="Accent.TButton").pack(side="left")
        ttk.Button(bot, text="No", command=win.destroy).pack(side="left", padx=6)
        ttk.Button(bot, text="Don't ask again", command=never).pack(side="left")

    def do_qa(self):
        sel = self.chosen(("built", "done"))
        if not sel:
            messagebox.showinfo("UBE Tailor", f"Tick some converted pieces first (set State above to '{tc.STATES['done']}').")
            return
        preset = self.preset.get()
        if not preset:
            messagebox.showinfo("UBE Tailor", "Pick your UBE body preset first (top, under Modpack...).")
            return

        def work():
            self._qa([i["set"] for i in sel], preset)
            self.rescan()
        self.run(work)

    # ------------------------------------------------------------ fix clipping
    def do_fix(self):
        """Fix clipping for the ticked converted pieces (or all converted ones) at the presets the user picks."""
        sel = self.chosen(("built", "done"))
        pieces = sel or [i for i in self.items if i["state"] in ("built", "done")]
        self.open_fix(pieces, ticked=bool(sel))

    def open_fix(self, pieces, ticked=True):
        """The Fix clipping window for these pieces (Fix clipping button, or right-click on a piece / a mod)."""
        if self.busy:
            return
        if not pieces:
            messagebox.showinfo("UBE Tailor", "Convert some outfits first.")
            return
        if tc.running("BodySlide x64.exe") or tc.running("BodySlide.exe"):
            messagebox.showwarning("UBE Tailor", "BodySlide is open. Close it first - it reads the same project files.")
            return
        presets = list(self.preset["values"]) or tc.list_presets()
        if not presets:
            messagebox.showinfo("UBE Tailor", "No UBE body presets found (BodySlide\\SliderPresets).")
            return
        FixWindow(self, [i["set"] for i in pieces], presets, ticked=ticked)

    def run_fix(self, sets, presets, again=False, include_hand=False):
        """Fix clipping for these pieces; pieces already fixed for these presets are skipped unless again=True,
        pieces edited by hand in Outfit Studio unless include_hand=True."""
        import fix_clip

        def work():
            t0 = time.time()
            if not include_hand:
                db0 = tc.load_db()
                hand = [s for s in sets if tc.hand_edited(db0, s)]
                if hand:
                    self.say(f"{len(hand)} piece(s) edited by hand in Outfit Studio left alone (tick 'Also pieces "
                             "edited by hand' in the Fix clipping window to include them).")
            done = [] if again else fix_clip.done_for(tc.load_db(), sets, presets)
            if again:
                self.say(f"Fixing every one of the {len(sets)} piece(s) again, also the ones fixed before.")
            if done:
                self.say(f"{len(done)} piece(s) were already fixed or checked for these presets - skipped.")
            if len(done) == len(sets):
                self.say("Nothing new to fix. (A piece you convert again is fixed again next time.)")
                return
            self.say(f"Fixing clipping of {len(sets) - len(done)} piece(s) for {len(presets)} preset(s)... (pieces "
                     "that already fit every preset are left as they are)")
            n = Counter()
            tot = {"before": 0, "after": 0}
            worst = {"before": Counter(), "after": Counter()}

            def on(i, total, name, rep, err):
                if err:
                    n["failed"] += 1
                    self.say(f"   failed: {name[11:]}: {err}")
                elif rep:
                    n[rep["state"]] += 1
                    n["hidden"] += rep.get("hidden", 0)
                    n["hid_pieces"] += bool(rep.get("hidden"))
                    n["through0"] += rep.get("through", (0, 0))[0]
                    n["through1"] += rep.get("through", (0, 0))[1]
                    for k in ("before", "after"):
                        tot[k] += rep[k]
                        if rep["presets"]:
                            worst[k][max(v[k]["grade"] for v in rep["presets"].values())] += 1
                    if rep["state"] == "fixed":
                        g0 = max(v["before"]["grade"] for v in rep["presets"].values())
                        g1 = max(v["after"]["grade"] for v in rep["presets"].values())
                        self.say(f"   {name[11:]}: points inside {rep['before']} -> {rep['after']}   "
                                 f"(worst preset {tc.GRADES[g0]} -> {tc.GRADES[g1]})")
                left = (time.time() - t0) / max(i, 1) * (total - i)
                self.q.put(("prog", (i, total, f"Fixing clipping {i}/{total}   about {left / 60:.0f} min left")))
            fix_clip.fix_many(sets, presets, self.live_workers, on, lambda: self.stop_flag, again=again,
                              include_hand=include_hand)
            self.say(f"Fix clipping: {n['fixed']} fixed, {n['fine']} already fit every preset, {n['unchanged']} "
                     f"could not be improved without harm (left as they were), {n['failed']} failed  "
                     f"({time.time() - t0:.0f} s)" + ("  - stopped" if self.stop_flag else ""))
            if n["squeeze"]:
                self.say(f"   {n['squeeze']} squeeze outfit(s) (latex, corsets that press the body) left as converted: "
                         "fixing them would push the pressed outfit back out")
            self.say(f"   points inside, all chosen presets together: {tot['before']:,} -> {tot['after']:,}")
            for k in ("before", "after"):
                self.say(f"   worst grade per piece {k}: " + ", ".join(
                    f"{tc.GRADES[g]} {c}" for g, c in sorted(worst[k].items())))
            if n["hidden"]:
                self.say(f"   body hidden under the outfit (it cannot poke through there): {n['hidden']:,} points in "
                         f"{n['hid_pieces']} piece(s); skin through the outfit at your presets "
                         f"{n['through0']:,} -> {n['through1']:,} points")
            if n["fixed"] or n["hidden"]:
                self.say(self.build_hint("so the game gets the fixed pieces"))
            self.rescan()
        self.run(work)

    def do_patch(self):
        if tc.running("SkyrimSE.exe"):
            messagebox.showwarning("UBE Tailor", "The game is running. Close it first.")
            return

        def work():
            self.say("Looking for new outfits without a UBE patch...")
            found = tc.find_new_plugins(log=self.say)
            self.say(f"Found {len(found)} mod(s) without a patch.")
            self.q.put(("ask", found))
        self.run(work)

    def ask_new(self, found):
        """Let the user choose which new plugins get a UBE patch, then repoint everything."""
        win = tk.Toplevel(self.root, bg=BG, padx=16, pady=12)
        win.title("New outfits")
        win.transient(self.root)
        win.geometry("720x640")
        win.minsize(520, 360)
        ttk.Label(win, text="New outfits", style="Title.TLabel").pack(anchor="w")
        ttk.Label(win, style="Sub.TLabel", wraplength=680, justify="left",
                  text="These mods have outfits with no UBE patch. Tick the ones the tool should patch - or none, "
                       "and press Apply to just update the patch.").pack(anchor="w", pady=(0, 8))
        # buttons first (packed at the bottom), so they stay visible however long the list is
        bot = ttk.Frame(win)
        bot.pack(side="bottom", fill="x", pady=(10, 0))
        top = ttk.Frame(win)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="Search", style="Sub.TLabel").pack(side="left")
        flt = tk.StringVar()
        ttk.Entry(top, textvariable=flt, width=30).pack(side="left", padx=(6, 10))
        count = ttk.Label(top, text="", style="Sub.TLabel")
        count.pack(side="right")
        # the list: a canvas with a scrollbar (and the mouse wheel)
        box = tk.Frame(win, bg=BG)
        box.pack(fill="both", expand=True)
        canvas = tk.Canvas(box, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(box, orient="vertical", command=canvas.yview)
        rows = tk.Frame(canvas, bg=BG)
        rows.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=rows, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        wheel = lambda ev: canvas.yview_scroll(int(-ev.delta / 120) or (-1 if ev.delta > 0 else 1), "units")
        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", wheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>") if e.widget is win else None)
        picks, boxes = {}, {}
        for name, (_p, todo) in sorted(found.items(), key=lambda kv: kv[0].lower()):
            v = tk.BooleanVar(value=False)
            picks[name] = v
            boxes[name] = ttk.Checkbutton(rows, text=f"{name}   ({len(todo)} outfits)", variable=v,
                                          command=lambda: refresh())
            boxes[name].pack(anchor="w", pady=2)
        if not found:
            ttk.Label(rows, text="No new mods.").pack(anchor="w")

        def shown():
            t = flt.get().lower()
            return [n for n in boxes if t in n.lower()]

        def refresh(*_a):
            vis = set(shown())
            for n, w in boxes.items():
                w.pack_forget()
            for n in sorted(vis, key=str.lower):
                boxes[n].pack(anchor="w", pady=2)
            canvas.yview_moveto(0)
            count["text"] = f"{len(vis)} shown, {sum(v.get() for v in picks.values())} ticked of {len(picks)}"
        flt.trace_add("write", refresh)

        def tick(on):
            for n in shown():
                picks[n].set(on)
            refresh()

        def go():
            chosen = [n for n, v in picks.items() if v.get()]
            win.destroy()

            def work():
                import merged_patch
                if chosen:
                    res = merged_patch.build(add=chosen, log=self.say)
                    for fname, n_mods, n_armo, _n_arma, n_m in res:
                        self.say(f"Patch {fname}: {n_mods} mods, {n_armo} outfits, {n_m} masters")
                    if merged_patch.place_in_load_order([r[0] for r in res]):
                        self.say("   ticked and placed at the end of the load order")
                    else:
                        self.say("   <- MO2 is open: press F5, tick " + ", ".join(r[0] for r in res)
                                 + " and keep it at the bottom of the load order")
                self.say(tc.repoint(False).strip().splitlines()[-1])
                if chosen:
                    self.say("Press Scan to list the new outfits.")
                self.rescan()
            self.run(work)
        ttk.Button(bot, text="Tick shown", command=lambda: tick(True)).pack(side="left")
        ttk.Button(bot, text="Clear", command=lambda: tick(False)).pack(side="left", padx=6)
        ttk.Button(bot, text="Apply", command=go, style="Accent.TButton").pack(side="right")
        ttk.Button(bot, text="Cancel", command=win.destroy).pack(side="right", padx=6)
        refresh()


# ---------------------------------------------------------------- questions
class FixWindow:
    """Pick the presets to fix clipping for (all ticked: fixing for a few makes the others worse)."""

    def __init__(self, app, sets, presets, ticked):
        self.app, self.sets = app, sets
        win = self.win = tk.Toplevel(app.root, bg=BG, padx=16, pady=12)
        win.title("Fix clipping")
        win.transient(app.root)
        win.geometry("760x560")
        win.minsize(560, 380)
        ttk.Label(win, text="Fix clipping", style="Title.TLabel").pack(anchor="w")
        what = f"the {len(sets)} ticked piece(s)" if ticked else f"all {len(sets)} converted pieces"
        ttk.Label(win, style="Sub.TLabel", wraplength=720, justify="left", text=(
            f"Changes how {what} follow the body sliders, so they stay outside the UBE body at every preset ticked "
            "below (the shape at rest stays the same). A piece is only changed where that helps without making it "
            "worse at any of these presets; pieces that already fit them are left alone. It also hides the body "
            "where the outfit covers it at all these presets (a band of skin along every edge stays, see-through "
            "fabric never hides it), so the skin cannot poke through there. Keep all your presets "
            "ticked: fixing for a few makes the others worse. Afterwards run Batch Build in BodySlide again. "
            "Experimental - check the pieces in game.")).pack(anchor="w", pady=(0, 8))
        bot = ttk.Frame(win)
        bot.pack(side="bottom", fill="x", pady=(10, 0))
        opts = ttk.Frame(win)
        opts.pack(side="bottom", fill="x", pady=(8, 0))   # above the buttons, before the list takes the room
        self.again = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Fix every piece again, also the ones already fixed (takes long)",
                        variable=self.again, command=self.refresh).pack(anchor="w")
        self.hand = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Also pieces edited by hand in Outfit Studio (overwrites your edits)",
                        variable=self.hand).pack(anchor="w")
        self.ask_after = tk.BooleanVar(value=env.S.get("fix_after_convert", "ask") == "ask")
        ttk.Checkbutton(opts, text="After converting new outfits, ask me to fix them", variable=self.ask_after,
                        command=self.save_ask).pack(anchor="w")
        try:
            import fix_clip
            self._done_for = lambda p: fix_clip.done_for(self.db, sets, p)
            self.db = tc.load_db()
        except Exception:
            self._done_for = None
        box = tk.Frame(win, bg=BG)
        box.pack(fill="both", expand=True)
        canvas = tk.Canvas(box, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(box, orient="vertical", command=canvas.yview)
        rows = tk.Frame(canvas, bg=BG)
        rows.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=rows, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        wheel = lambda ev: canvas.yview_scroll(int(-ev.delta / 120) or (-1 if ev.delta > 0 else 1), "units")
        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", wheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>") if e.widget is win else None)
        self.picks = {}
        # the presets of the last run, ticked again: pieces already fixed for them are skipped, so only new and
        # re-converted pieces take time (other ticks make the Tailor check every piece again)
        last = set(env.S.get("fix_presets") or ()) & set(presets)
        if last:
            ttk.Label(win, style="Sub.TLabel", wraplength=720, justify="left", text=(
                "Ticked like your last run: pieces already fixed for these presets are skipped. Ticking another "
                "preset makes every piece be checked again, which takes much longer.")).pack(anchor="w", pady=(0, 6))
        for k, name in enumerate(presets):
            v = tk.BooleanVar(value=name in last if last else True)
            self.picks[name] = v
            ttk.Checkbutton(rows, text=name, variable=v, command=self.refresh).grid(
                row=k // 3, column=k % 3, sticky="w", padx=(0, 18), pady=2)
        self.count = ttk.Label(bot, text="", style="Sub.TLabel")
        ttk.Button(bot, text="All", command=lambda: self.tick(True)).pack(side="left")
        ttk.Button(bot, text="None", command=lambda: self.tick(False)).pack(side="left", padx=6)
        self.count.pack(side="left", padx=10)
        self.ok = ttk.Button(bot, text="Fix", command=self.go, style="Accent.TButton")
        self.ok.pack(side="right")
        ttk.Button(bot, text="Cancel", command=win.destroy).pack(side="right", padx=6)
        self.refresh()

    def chosen(self):
        return [n for n, v in self.picks.items() if v.get()]

    def refresh(self):
        chosen = self.chosen()
        n = len(chosen)
        text = f"{n} of {len(self.picks)} presets ticked"
        if n and self.again.get():
            text += f" - all {len(self.sets)} pieces"
        elif n and self._done_for:
            done = len(self._done_for(chosen))
            text += f" - {len(self.sets) - done} piece(s) to fix, {done} already done (skipped)"
        self.count["text"] = text
        self.ok["state"] = "normal" if n else "disabled"

    def save_ask(self):
        env.S["fix_after_convert"] = "ask" if self.ask_after.get() else "never"
        env.save_settings(env.S)

    def tick(self, on):
        for v in self.picks.values():
            v.set(on)
        self.refresh()

    def go(self):
        presets = self.chosen()
        env.S["fix_presets"] = presets
        env.save_settings(env.S)
        self.win.destroy()
        self.app.run_fix(self.sets, presets, again=self.again.get(), include_hand=self.hand.get())


def ask_edition(root):
    """Ask which Skyrim the modpack runs (only when SkyrimSE.exe cannot be read); the answer is saved."""
    win = tk.Toplevel(root, bg=BG, padx=20, pady=16)
    win.title("UBE Tailor - which Skyrim?")
    win.transient(root)
    win.grab_set()
    ttk.Label(win, text="Which Skyrim does this modpack run?", style="Title.TLabel").pack(anchor="w")
    ttk.Label(win, style="Sub.TLabel", wraplength=460, justify="left",
              text="UBE Tailor could not read the game's version (no SkyrimSE.exe in the game folder MO2 uses). "
                   "You find it in MO2 or in the SKSE log. The Tailor remembers your answer.").pack(anchor="w",
                                                                                                   pady=(4, 12))
    row = ttk.Frame(win)
    row.pack(anchor="w")

    def pick(e):
        env.set_game_edition(e)
        win.destroy()
    ttk.Button(row, text="Skyrim SE (1.5.97)", style="Accent.TButton", command=lambda: pick("SE")).pack(side="left")
    ttk.Button(row, text="Skyrim AE (1.6.x)", style="Accent.TButton",
               command=lambda: pick("AE")).pack(side="left", padx=8)
    ttk.Button(row, text="I don't know", command=win.destroy).pack(side="left")
    root.wait_window(win)


# ---------------------------------------------------------------- first start: welcome, modpack, requirements

class WelcomeWindow:
    """First start (and the Guide button): who made the tool, what it does, and the way from start to playing."""

    STEPS = (
        ("Pick your modpack", "Choose your Mod Organizer 2 folder. The Tailor reads everything else from MO2."),
        ("Check what you need", "The Tailor shows what is installed and what is missing (UBE 2.0, its Conversion "
                                "references, CBBE 3BA, BodySlide). 'Download' only opens the official page."),
        ("Pick outfits and convert", "Tick outfits in the list and press 'Convert selected'. Whole outfits are "
                                     "converted together, and each piece gets a fit grade (A is best)."),
        ("Build in BodySlide", "Start BodySlide from MO2, pick the group 'UBE Auto Conversions' and your UBE "
                               "preset, tick 'Build Morphs' and press Batch Build."),
        ("Scan, then play", "Back in the Tailor press Scan: the patch switches every built piece to its UBE "
                            "mesh. Close the Tailor and play."),
    )

    def __init__(self, root, on_done=None, first=False):
        self.root, self.on_done, self.first = root, on_done, first
        self.win = win = tk.Toplevel(root, bg=BG, padx=26, pady=20)
        win.title("Welcome to UBE Tailor")
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", self.close)
        head = tk.Frame(win, bg=BG)
        head.pack(fill="x")
        if getattr(root, "_art", None) is not None:
            tk.Label(head, image=root._art, bg=BG).pack(side="left", padx=(0, 14))
        names = tk.Frame(head, bg=BG)
        names.pack(side="left", anchor="w")
        tk.Label(names, text="UBE Tailor", bg=BG, fg=FG, font=("Segoe UI Semibold", 22)).pack(anchor="w")
        tk.Label(names, text=f"by {env.AUTHOR}   ·   version {env.VERSION}", bg=BG, fg=GOLD,
                 font=("Segoe UI Semibold", 11)).pack(anchor="w")
        tk.Label(win, bg=BG, fg=FG, font=("Segoe UI", 11), wraplength=620, justify="left", anchor="w",
                 text="Your 3BA / CBBE outfits, made for the UBE 2.0 body. The Tailor turns them into real UBE "
                      "BodySlide projects - shape, sliders and bone weights from UBE - and one small plugin, so "
                      "UBE characters can wear them without the body poking through.").pack(fill="x", pady=(14, 10))
        tk.Label(win, text="Where we go, step by step", bg=BG, fg=GOLD, font=FONT_B, anchor="w").pack(fill="x")
        for n, (title, text) in enumerate(self.STEPS, 1):
            row = tk.Frame(win, bg=PANEL, padx=12, pady=8)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=str(n), bg=ACCENT, fg="#041417", font=("Segoe UI Semibold", 12), width=2).pack(
                side="left", anchor="n", padx=(0, 12))
            col = tk.Frame(row, bg=PANEL)
            col.pack(side="left", fill="x", expand=True)
            tk.Label(col, text=title, bg=PANEL, fg=FG, font=FONT_B, anchor="w").pack(fill="x")
            tk.Label(col, text=text, bg=PANEL, fg=MUTED, font=("Segoe UI", 9), wraplength=540, justify="left",
                     anchor="w").pack(fill="x")
        tk.Label(win, bg=BG, fg=MUTED, font=("Segoe UI", 9), wraplength=620, justify="left", anchor="w",
                 text="Tips: close the game while the Tailor works. 'Health check' finds known problems and fixes "
                      "them. The gold 'Next:' lines in the log always tell you the next step.").pack(fill="x", pady=(10, 0))
        btns = tk.Frame(win, bg=BG)
        btns.pack(fill="x", pady=(14, 0))
        tk.Label(btns, text=f"Made by {env.AUTHOR}", bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
        ttk.Button(btns, text="Let's go" if first else "Close", command=self.go, style="Accent.TButton").pack(side="right")
        win.transient(root) if not first else None
        win.focus_force()

    def go(self):
        s = env.load_settings()
        s["welcome_seen"] = True
        env.save_settings(s)
        env.S.update(s)
        self.win.destroy()
        if self.on_done:
            self.on_done()

    def close(self):
        self.win.destroy()
        if self.first:                    # closed at the very first start: nothing else to show
            self.root.destroy()

def restart(root):
    """Start a fresh copy of the tool (the modules read the modpack's paths when they load) and close this one."""
    flags = (["-s"] if sys.flags.no_user_site else []) + (["-E"] if sys.flags.ignore_environment else [])
    subprocess.Popen([sys.executable] + flags + sys.argv, cwd=env.TOOL)
    root.destroy()


class SetupWindow:
    """Pick the Mod Organizer 2 modpack and profile. Saved in the settings; the tool then restarts."""

    def __init__(self, root, first=False):
        self.root = root
        self.win = win = tk.Toplevel(root, bg=BG, padx=18, pady=14) if not first else root
        if first:
            root.title("UBE Tailor - pick your modpack")
            root.geometry("760x420")
        else:
            win.title("Modpack")
            win.transient(root)
        ttk.Label(win, text="Your modpack", style="Title.TLabel").pack(anchor="w")
        ttk.Label(win, style="Sub.TLabel", wraplength=700, justify="left",
                  text="Pick the Mod Organizer 2 folder of your Skyrim SE modpack (the folder with ModOrganizer.exe "
                       "or ModOrganizer.ini). Everything else is read from MO2's own settings.").pack(anchor="w")
        row = ttk.Frame(win)
        row.pack(fill="x", pady=(12, 4))
        self.ini = ttk.Combobox(row, width=78)
        guesses = env.guesses()
        self.ini["values"] = [os.path.dirname(g) for g in guesses]
        cur = env.S.get("ini")
        self.ini.set(os.path.dirname(cur) if cur else (self.ini["values"][0] if guesses else ""))
        self.ini.pack(side="left", fill="x", expand=True)
        self.ini.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.ini.bind("<FocusOut>", lambda _e: self.refresh())
        ttk.Button(row, text="Browse...", command=self.browse).pack(side="left", padx=(6, 0))
        row2 = ttk.Frame(win)
        row2.pack(fill="x", pady=4)
        ttk.Label(row2, text="Profile", style="Sub.TLabel").pack(side="left")
        self.profile = ttk.Combobox(row2, width=30, state="readonly")
        self.profile.pack(side="left", padx=8)
        self.msg = tk.Label(win, text="", bg=BG, fg=MUTED, font=FONT, wraplength=700, justify="left", anchor="w")
        self.msg.pack(fill="x", pady=(8, 4))
        tk.Label(win, bg=BG, fg=MUTED, font=("Segoe UI", 9), wraplength=700, justify="left", anchor="w",
                 text=f"The Tailor writes its BodySlide projects and its plugin into one mod, '{env.OUTPUT_MOD_NAME}'. "
                      "It adds that mod and its plugin to your profile only while MO2 is closed (or when MO2 "
                      "started the Tailor), and copies each profile file it changes to "
                      + os.path.join(env.HOME, "backups") + " first.").pack(fill="x", pady=(4, 8))
        btns = ttk.Frame(win)
        btns.pack(anchor="e", pady=(6, 0))
        self.ok = ttk.Button(btns, text="Use this modpack", command=self.save, style="Accent.TButton")
        self.ok.pack(side="left", padx=4)
        if not first:
            ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="left", padx=4)
        self.layout = None
        self.refresh()

    def browse(self):
        d = filedialog.askdirectory(parent=self.win, title="Your Mod Organizer 2 folder")
        if d:
            self.ini.set(os.path.normpath(d))
            self.refresh()

    def refresh(self):
        inis = env.inis_in(self.ini.get()) if self.ini.get() else []
        self.layout = None
        if not inis:
            self.profile["values"] = []
            self.profile.set("")
            self.msg.config(text="No ModOrganizer.ini there.", fg=GRADE["C"])
            self.ok["state"] = "disabled"
            return
        try:
            L = env.layout(inis[0])
        except Exception as e:                       # unreadable ini
            self.msg.config(text=f"Cannot read {inis[0]}: {e}", fg=GRADE["C"])
            self.ok["state"] = "disabled"
            return
        profs = env.profiles(L)
        self.profile["values"] = profs
        want = env.S.get("profile") if env.S.get("ini") == L["ini"] else L["profile_name"]
        self.profile.set(want if want in profs else (profs[0] if profs else ""))
        L = env.layout(inis[0], self.profile.get() or None)
        probs = env.problems(L)
        self.layout = L if not probs else None
        self.msg.config(text=("\n".join(probs) if probs else
                              f"Game: {L['game']}\nMods: {L['mods']}\nProfile: {L['profile_name']}"),
                        fg=GRADE["C"] if probs else FG)
        self.ok["state"] = "normal" if self.layout else "disabled"
        self.profile.bind("<<ComboboxSelected>>", lambda _e: self.refresh_profile(inis[0]))

    def refresh_profile(self, ini):
        env.S["profile"] = self.profile.get()
        env.S["ini"] = env.layout(ini)["ini"]
        self.refresh()

    def save(self):
        if not self.layout:
            return
        s = env.load_settings()
        if s.get("ini") != self.layout["ini"]:
            s.pop("preset", None)                    # presets belong to a modpack
        s.update(ini=self.layout["ini"], profile=self.layout["profile_name"])
        env.save_settings(s)
        restart(self.root)


class RequirementsWindow:
    """One card per thing the Tailor needs: installed or missing, its official page, and Download / Skip.
    'Download' only opens the page in the browser: the Tailor never downloads or installs anything itself."""

    def __init__(self, root, on_done, first=False):
        import requirements
        self.req, self.root, self.on_done, self.skipped = requirements, root, on_done, set()
        self.win = tk.Toplevel(root, bg=BG, padx=18, pady=14)
        self.win.title("UBE Tailor - requirements")
        self.win.geometry("820x640")
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        ttk.Label(self.win, text="What UBE Tailor needs", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self.win, style="Sub.TLabel", wraplength=760, justify="left",
                  text="The Tailor checked your PC and your modpack. For anything missing, 'Download' opens its "
                       "official page in your browser - you download and install it yourself (in MO2), then press "
                       "'Check again'. The Tailor never downloads anything on its own.").pack(anchor="w")
        self.show_all = tk.BooleanVar(value=first)
        ttk.Checkbutton(self.win, text="Show installed ones too", variable=self.show_all,
                        command=self.fill).pack(anchor="w", pady=(8, 4))
        outer = tk.Frame(self.win, bg=BG)
        outer.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.cards = tk.Frame(self.canvas, bg=BG)
        self.cards.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.cards, anchor="nw", width=770)
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        btns = ttk.Frame(self.win)
        btns.pack(fill="x", pady=(10, 0))
        self.note = ttk.Label(btns, text="", style="Sub.TLabel")
        self.note.pack(side="left")
        self.go = ttk.Button(btns, text="Continue", command=self.done, style="Accent.TButton")
        self.go.pack(side="right", padx=4)
        ttk.Button(btns, text="Check again", command=self.recheck).pack(side="right", padx=4)
        self.items = requirements.check()
        self.fill()

    def recheck(self):
        self.items = self.req.check()
        self.fill()

    def card(self, it):
        box = tk.Frame(self.cards, bg=PANEL, padx=14, pady=10)
        box.pack(fill="x", pady=5, padx=(0, 6))
        top = tk.Frame(box, bg=PANEL)
        top.pack(fill="x")
        if it.ok:
            chip, col = it.chip or "Installed", GRADE["A"]
        elif it.need == "info":
            chip, col = "Please check", GOLD
        elif it.key in self.skipped:
            chip, col = "Skipped", MUTED
        else:
            chip, col = ("Missing" if it.need == "required" else "Optional - not installed"), \
                (GRADE["C"] if it.need == "required" else GOLD)
        tk.Label(top, text=it.name, bg=PANEL, fg=FG, font=FONT_B, anchor="w").pack(side="left")
        tk.Label(top, text=chip, bg=PANEL, fg=col, font=FONT_B).pack(side="right")
        tk.Label(box, text=it.detail, bg=PANEL, fg=MUTED, font=("Segoe UI", 9), anchor="w", justify="left",
                 wraplength=720).pack(fill="x", pady=(2, 0))
        if it.ok:
            return
        tk.Label(box, text=it.how, bg=PANEL, fg=FG, font=FONT, anchor="w", justify="left",
                 wraplength=720).pack(fill="x", pady=(6, 4))
        row = tk.Frame(box, bg=PANEL)
        row.pack(fill="x")
        if it.key == "modpack":
            ttk.Button(row, text="Pick my modpack...", style="Accent.TButton",
                       command=lambda: SetupWindow(self.root)).pack(side="left")
            return
        if it.key == "game" and not it.url:
            for e, t in (("SE", "Skyrim SE (1.5.97)"), ("AE", "Skyrim AE (1.6.x)")):
                ttk.Button(row, text=t, style="Accent.TButton",
                           command=lambda e=e: (env.set_game_edition(e), self.recheck())).pack(side="left", padx=(0, 8))
            return
        if it.url:
            ttk.Button(row, text="Download (opens the page)", style="Accent.TButton",
                       command=lambda u=it.url: webbrowser.open(u)).pack(side="left")
            tk.Label(row, text=it.url, bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(side="left", padx=8)
        if it.key not in self.skipped:
            ttk.Button(row, text="Skip", style="Card.TButton", command=lambda k=it.key: self.skip(k)).pack(side="right")

    def skip(self, key):
        self.skipped.add(key)
        self.fill()

    def fill(self):
        for w in self.cards.winfo_children():
            w.destroy()
        shown = [i for i in self.items if self.show_all.get() or not i.ok]
        for it in shown:
            self.card(it)
        if not shown:
            tk.Label(self.cards, text="Everything is installed.", bg=BG, fg=GRADE["A"], font=FONT_B).pack(anchor="w")
        blocking = [i for i in self.items if not i.ok and i.need == "required"
                    and (i.key in ("python", "pynifly", "modpack") or i.key not in self.skipped)]
        hard = [i for i in blocking if i.key in ("python", "pynifly", "modpack")]
        self.go["state"] = "disabled" if hard else "normal"
        self.go["text"] = "Continue" if not blocking else "Continue anyway"
        self.note["text"] = ("The Tailor cannot start without: " + ", ".join(i.name.split(" (")[0] for i in hard)) \
            if hard else (f"{len(blocking)} required item(s) missing - converting will not work until they are "
                          "installed" if blocking else "")

    def done(self):
        s = env.load_settings()
        s["requirements_seen"] = True
        env.save_settings(s)
        env.S.update(s)
        self.win.destroy()
        if self.on_done:
            self.on_done()

    def close(self):
        self.win.destroy()
        if self.on_done:                  # closed at the first start: nothing to run
            self.root.destroy()


def set_icon(root):
    """Window + taskbar icon. Uses tailor_icon_custom*.png if present, else the built-in needle icon."""
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("UBETailor")   # own taskbar icon, not Python's
    except Exception:
        pass
    custom = os.path.isfile(os.path.join(here, "tailor_icon_custom.png"))
    names = ["tailor_icon_custom.png", "tailor_icon_custom_64.png", "tailor_icon_custom_32.png"] if custom else \
        ["tailor_icon_256.png", "tailor_icon_64.png", "tailor_icon_32.png"]
    try:
        root._icons = [tk.PhotoImage(file=os.path.join(here, n)) for n in names
                       if os.path.isfile(os.path.join(here, n))]
        root.iconphoto(True, *root._icons)
    except Exception:
        pass                                  # a missing or unreadable picture must never stop the tool
    try:                                      # small picture shown in the window's header
        root._art = tk.PhotoImage(file=os.path.join(here, "tailor_icon_custom_96.png" if custom else "tailor_icon_64.png"))
    except Exception:
        root._art = None


def main():
    root = tk.Tk()
    set_icon(root)
    apply_theme(root)

    def start():
        global tc
        try:
            import tailor_core
        except Exception as e:                # e.g. PyNifly / numpy missing after all
            messagebox.showerror("UBE Tailor", f"UBE Tailor cannot start:\n\n{e}")
            root.destroy()
            return
        tc = tailor_core
        root.deiconify()
        App(root)

    def flow():
        if not env.READY:                     # first start (or the modpack moved): pick it
            root.deiconify()
            SetupWindow(root, first=True)
            return
        import requirements
        items = requirements.check()
        if not env.S.get("requirements_seen") or requirements.missing(items):
            root.withdraw()
            RequirementsWindow(root, start, first=not env.S.get("requirements_seen"))
        else:
            start()

    if not env.S.get("welcome_seen"):
        root.withdraw()
        WelcomeWindow(root, flow, first=True)
    else:
        flow()
    root.mainloop()

if __name__ == "__main__":
    main()
