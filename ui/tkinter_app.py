"""
AI Test Engineering Platform — Tkinter Desktop UI
Provides a GUI to configure, run, and view results of the QA pipeline.
"""
import sys
import os
import threading
import queue
import webbrowser
import subprocess
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# Make sure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.settings import settings
from config.constants import REPORTS_DIR


# ─────────────────────────────────────────────────────────────────────────────
# Color Palette & Fonts
# ─────────────────────────────────────────────────────────────────────────────
BG_DARK      = "#0f172a"   # Slate 900
BG_PANEL     = "#1e293b"   # Slate 800
BG_CARD      = "#334155"   # Slate 700
ACCENT       = "#6366f1"   # Indigo 500
ACCENT_HOVER = "#4f46e5"   # Indigo 600
SUCCESS      = "#22c55e"   # Green 500
DANGER       = "#ef4444"   # Red 500
WARNING      = "#f59e0b"   # Amber 500
TEXT_PRIMARY = "#f8fafc"   # Slate 50
TEXT_MUTED   = "#94a3b8"   # Slate 400
BORDER       = "#475569"   # Slate 600

FONT_TITLE   = ("Segoe UI", 18, "bold")
FONT_HEADING = ("Segoe UI", 12, "bold")
FONT_BODY    = ("Segoe UI", 10)
FONT_MONO    = ("Consolas", 9)
FONT_SMALL   = ("Segoe UI", 9)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI Test Engineering Platform")
        self.geometry("1280x800")
        self.minsize(1024, 680)
        self.configure(bg=BG_DARK)

        self.log_queue = queue.Queue()
        self.is_running = False
        self.last_report_dir = None

        self._setup_styles()
        self._build_ui()
        self._poll_log_queue()

    # ── Styles ────────────────────────────────────────────────────────────────
    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TFrame",      background=BG_DARK)
        style.configure("Panel.TFrame", background=BG_PANEL)
        style.configure("Card.TFrame", background=BG_CARD)

        style.configure("Title.TLabel", background=BG_DARK, foreground=TEXT_PRIMARY, font=FONT_TITLE)
        style.configure("Heading.TLabel", background=BG_PANEL, foreground=TEXT_PRIMARY, font=FONT_HEADING)
        style.configure("Body.TLabel",  background=BG_PANEL, foreground=TEXT_MUTED, font=FONT_BODY)
        style.configure("Card.TLabel",  background=BG_CARD,  foreground=TEXT_PRIMARY, font=FONT_BODY)

        style.configure("Accent.TButton",
            background=ACCENT, foreground="white", font=("Segoe UI", 10, "bold"),
            borderwidth=0, focusthickness=0, padding=(16, 8))
        style.map("Accent.TButton",
            background=[("active", ACCENT_HOVER), ("disabled", BORDER)],
            foreground=[("disabled", TEXT_MUTED)])

        style.configure("Secondary.TButton",
            background=BG_CARD, foreground=TEXT_PRIMARY, font=FONT_BODY,
            borderwidth=1, relief="flat", padding=(12, 7))
        style.map("Secondary.TButton",
            background=[("active", BORDER)])

        style.configure("TEntry",
            fieldbackground=BG_CARD, foreground=TEXT_PRIMARY,
            insertcolor=TEXT_PRIMARY, borderwidth=1, relief="flat")

        style.configure("Horizontal.TSeparator", background=BORDER)

        style.configure("pass.TLabel",    background=BG_CARD, foreground=SUCCESS, font=("Segoe UI", 9, "bold"))
        style.configure("fail.TLabel",    background=BG_CARD, foreground=DANGER,  font=("Segoe UI", 9, "bold"))
        style.configure("partial.TLabel", background=BG_CARD, foreground=WARNING, font=("Segoe UI", 9, "bold"))
        style.configure("pending.TLabel", background=BG_CARD, foreground=TEXT_MUTED, font=("Segoe UI", 9, "bold"))

        # Progress bar
        style.configure("Accent.Horizontal.TProgressbar",
            troughcolor=BG_CARD, background=ACCENT, thickness=6)

    # ── Main UI ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Top bar ──
        topbar = tk.Frame(self, bg=BG_DARK, pady=16, padx=24)
        topbar.pack(fill="x")
        tk.Label(topbar, text="⚡  AI Test Engineering Platform",
                 bg=BG_DARK, fg=TEXT_PRIMARY, font=FONT_TITLE).pack(side="left")
        tk.Label(topbar, text="Autonomous QA — Powered by Groq + Playwright",
                 bg=BG_DARK, fg=TEXT_MUTED, font=FONT_SMALL).pack(side="left", padx=16)

        ttk.Separator(self, orient="horizontal").pack(fill="x")

        # ── Body: left sidebar + main area ──
        body = tk.Frame(self, bg=BG_DARK)
        body.pack(fill="both", expand=True)

        self._build_sidebar(body)
        self._build_main(body)

    def _build_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg=BG_PANEL, width=320, padx=20, pady=20)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # ── Config heading ──
        tk.Label(sidebar, text="Configuration", bg=BG_PANEL, fg=TEXT_PRIMARY,
                 font=FONT_HEADING).pack(anchor="w", pady=(0, 14))

        # ── Requirements CSV ──
        tk.Label(sidebar, text="Requirements CSV", bg=BG_PANEL, fg=TEXT_MUTED,
                 font=FONT_SMALL).pack(anchor="w")
        csv_frame = tk.Frame(sidebar, bg=BG_PANEL)
        csv_frame.pack(fill="x", pady=(2, 12))
        self.csv_var = tk.StringVar(value="requirements.csv")
        csv_entry = tk.Entry(csv_frame, textvariable=self.csv_var,
                             bg=BG_CARD, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                             relief="flat", font=FONT_BODY, bd=6)
        csv_entry.pack(side="left", fill="x", expand=True)
        tk.Button(csv_frame, text="…", bg=BG_CARD, fg=TEXT_PRIMARY, relief="flat",
                  font=FONT_BODY, cursor="hand2",
                  command=self._browse_csv).pack(side="right", padx=(4, 0))

        # ── Output Directory ──
        tk.Label(sidebar, text="Output Directory", bg=BG_PANEL, fg=TEXT_MUTED,
                 font=FONT_SMALL).pack(anchor="w")
        out_frame = tk.Frame(sidebar, bg=BG_PANEL)
        out_frame.pack(fill="x", pady=(2, 12))
        self.output_dir_var = tk.StringVar(value=settings.OUTPUT_DIR)
        output_dir_entry = tk.Entry(out_frame, textvariable=self.output_dir_var,
                                     bg=BG_CARD, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                                     relief="flat", font=FONT_BODY, bd=6)
        output_dir_entry.pack(side="left", fill="x", expand=True)
        tk.Button(out_frame, text="…", bg=BG_CARD, fg=TEXT_PRIMARY, relief="flat",
                  font=FONT_BODY, cursor="hand2",
                  command=self._browse_output_dir).pack(side="right", padx=(4, 0))

        # ── Primary API Key ──
        tk.Label(sidebar, text="Primary Groq API Key", bg=BG_PANEL, fg=TEXT_MUTED,
                 font=FONT_SMALL).pack(anchor="w")
        self.api_var = tk.StringVar(value=settings.GROQ_API_KEY[:10] + "…" if settings.GROQ_API_KEY else "")
        self.api_entry = tk.Entry(sidebar, textvariable=self.api_var,
                                  bg=BG_CARD, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                                  relief="flat", font=FONT_MONO, bd=6, show="•")
        self.api_entry.pack(fill="x", pady=(2, 12))

        # ── Fallback API Key ──
        tk.Label(sidebar, text="Gemini API Key (Fallback)", bg=BG_PANEL, fg=TEXT_MUTED,
                 font=FONT_SMALL).pack(anchor="w")
        self.fallback_var = tk.StringVar(value=settings.GEMINI_API_KEY)
        self.fallback_entry = tk.Entry(sidebar, textvariable=self.fallback_var,
                                       bg=BG_CARD, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                                       relief="flat", font=FONT_MONO, bd=6, show="•")
        self.fallback_entry.pack(fill="x", pady=(2, 12))

        # ── Headless toggle ──
        tk.Label(sidebar, text="Browser Mode", bg=BG_PANEL, fg=TEXT_MUTED,
                 font=FONT_SMALL).pack(anchor="w")
        self.headless_var = tk.BooleanVar(value=settings.BROWSER_HEADLESS)
        modes = tk.Frame(sidebar, bg=BG_PANEL)
        modes.pack(fill="x", pady=(2, 16))
        tk.Radiobutton(modes, text="Headless", variable=self.headless_var, value=True,
                       bg=BG_PANEL, fg=TEXT_MUTED, selectcolor=BG_CARD,
                       activebackground=BG_PANEL, font=FONT_SMALL).pack(side="left")
        tk.Radiobutton(modes, text="Visible", variable=self.headless_var, value=False,
                       bg=BG_PANEL, fg=TEXT_MUTED, selectcolor=BG_CARD,
                       activebackground=BG_PANEL, font=FONT_SMALL).pack(side="left", padx=12)

        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", pady=12)

        # ── Run button ──
        self.run_btn = tk.Button(sidebar, text="▶  Run Pipeline", bg=ACCENT, fg="white",
                                  font=("Segoe UI", 11, "bold"), relief="flat",
                                  cursor="hand2", pady=10, command=self._run_pipeline)
        self.run_btn.pack(fill="x", pady=(0, 8))

        self.stop_btn = tk.Button(sidebar, text="■  Stop", bg=BG_CARD, fg=DANGER,
                                   font=("Segoe UI", 10, "bold"), relief="flat",
                                   cursor="hand2", pady=8, state="disabled",
                                   command=self._request_stop)
        self.stop_btn.pack(fill="x", pady=(0, 8))

        self.report_btn = tk.Button(sidebar, text="📄  Open HTML Report", bg=BG_CARD, fg=TEXT_PRIMARY,
                                     font=FONT_BODY, relief="flat", cursor="hand2", pady=8,
                                     state="disabled", command=self._open_report)
        self.report_btn.pack(fill="x", pady=(0, 8))

        self.folder_btn = tk.Button(sidebar, text="📁  Open Report Folder", bg=BG_CARD, fg=TEXT_PRIMARY,
                                     font=FONT_BODY, relief="flat", cursor="hand2", pady=8,
                                     state="disabled", command=self._open_folder)
        self.folder_btn.pack(fill="x")

        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", pady=14)

        # ── Status indicator ──
        self.status_dot = tk.Label(sidebar, text="●  Idle", bg=BG_PANEL, fg=TEXT_MUTED, font=FONT_BODY)
        self.status_dot.pack(anchor="w")

        self.progress = ttk.Progressbar(sidebar, mode="indeterminate",
                                         style="Accent.Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(8, 0))

    def _build_main(self, parent):
        main = tk.Frame(parent, bg=BG_DARK, padx=20, pady=16)
        main.pack(side="left", fill="both", expand=True)

        # ── Tab bar ──
        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill="both", expand=True)

        style = ttk.Style()
        style.configure("TNotebook", background=BG_DARK, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG_PANEL, foreground=TEXT_MUTED,
                         padding=(14, 6), font=FONT_BODY)
        style.map("TNotebook.Tab",
                  background=[("selected", BG_CARD)],
                  foreground=[("selected", TEXT_PRIMARY)])

        # ── Tab 1: Live Log ──
        log_tab = tk.Frame(self.notebook, bg=BG_DARK)
        self.notebook.add(log_tab, text=" 📋 Live Log ")
        self._build_log_tab(log_tab)

        # ── Tab 2: Results ──
        results_tab = tk.Frame(self.notebook, bg=BG_DARK)
        self.notebook.add(results_tab, text=" ✅ Results ")
        self._build_results_tab(results_tab)

        # ── Tab 3: Test Engineering (Pipeline 1) ──
        eng_tab = tk.Frame(self.notebook, bg=BG_DARK)
        self.notebook.add(eng_tab, text=" 🧠 Test Engineering ")
        self._build_engineering_tab(eng_tab)

    def _build_log_tab(self, parent):
        top = tk.Frame(parent, bg=BG_DARK, pady=8)
        top.pack(fill="x")
        tk.Label(top, text="Live Execution Log", bg=BG_DARK, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(side="left")
        tk.Button(top, text="Clear", bg=BG_CARD, fg=TEXT_MUTED, font=FONT_SMALL,
                  relief="flat", cursor="hand2", command=self._clear_log).pack(side="right")

        self.log_text = scrolledtext.ScrolledText(
            parent, bg="#020617", fg="#e2e8f0", font=FONT_MONO,
            relief="flat", bd=0, wrap="word",
            insertbackground=TEXT_PRIMARY, state="disabled"
        )
        self.log_text.pack(fill="both", expand=True)

        # Tag colors for different log levels
        self.log_text.tag_config("INFO",    foreground="#94a3b8")
        self.log_text.tag_config("WARNING", foreground="#f59e0b")
        self.log_text.tag_config("ERROR",   foreground="#ef4444")
        self.log_text.tag_config("SUCCESS", foreground="#22c55e")
        self.log_text.tag_config("SYSTEM",  foreground="#818cf8")
        self.log_text.tag_config("ts",      foreground="#475569")

    def _build_results_tab(self, parent):
        tk.Label(parent, text="Test Results", bg=BG_DARK, fg=TEXT_PRIMARY,
                 font=FONT_HEADING, pady=8).pack(anchor="w")

        cols = ("ID", "Status", "Confidence", "Reasoning")
        self.results_tree = ttk.Treeview(parent, columns=cols, show="headings", height=20)

        style = ttk.Style()
        style.configure("Treeview",
            background=BG_PANEL, fieldbackground=BG_PANEL, foreground=TEXT_PRIMARY,
            font=FONT_BODY, rowheight=30)
        style.configure("Treeview.Heading",
            background=BG_CARD, foreground=TEXT_PRIMARY, font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", ACCENT)])

        self.results_tree.heading("ID",         text="Test ID")
        self.results_tree.heading("Status",     text="Status")
        self.results_tree.heading("Confidence", text="Confidence")
        self.results_tree.heading("Reasoning",  text="Reasoning / AI Fix")

        self.results_tree.column("ID",         width=140, anchor="w")
        self.results_tree.column("Status",     width=80,  anchor="center")
        self.results_tree.column("Confidence", width=90,  anchor="center")
        self.results_tree.column("Reasoning",  width=600, anchor="w")

        self.results_tree.tag_configure("PASS",    background="#14532d", foreground="#86efac")
        self.results_tree.tag_configure("FAIL",    background="#450a0a", foreground="#fca5a5")
        self.results_tree.tag_configure("PARTIAL", background="#451a03", foreground="#fcd34d")

        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)

        self.results_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _build_engineering_tab(self, parent):
        self.current_analysis_json = None
        
        # Split into left (input/clarifications) and right (generated grid)
        paned = ttk.PanedWindow(parent, orient="horizontal")
        paned.pack(fill="both", expand=True, pady=8)
        
        left_frame = tk.Frame(paned, bg=BG_DARK)
        right_frame = tk.Frame(paned, bg=BG_DARK)
        paned.add(left_frame, weight=1)
        paned.add(right_frame, weight=2)
        
        # --- Left Frame: Input ---
        tk.Label(left_frame, text="1. Raw Requirements (Stories, BRD)", bg=BG_DARK, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        self.raw_req_text = scrolledtext.ScrolledText(left_frame, bg=BG_PANEL, fg=TEXT_PRIMARY, font=FONT_BODY, height=10, relief="flat", bd=0, insertbackground=TEXT_PRIMARY)
        self.raw_req_text.pack(fill="both", expand=True, pady=(8, 8))
        self.raw_req_text.insert("1.0", "Test the dashboard.") # Placeholder
        
        btn_frame = tk.Frame(left_frame, bg=BG_DARK)
        btn_frame.pack(fill="x", pady=(0, 16))
        self.analyze_btn = tk.Button(btn_frame, text="🧠 Analyze Requirements", bg=ACCENT, fg="white", font=FONT_SMALL, relief="flat", cursor="hand2", command=self._analyze_requirements)
        self.analyze_btn.pack(side="left")
        
        # Clarifications section
        tk.Label(left_frame, text="2. Analysis & Clarifications", bg=BG_DARK, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(anchor="w")
        self.clarifications_text = scrolledtext.ScrolledText(left_frame, bg=BG_PANEL, fg=WARNING, font=FONT_BODY, height=8, relief="flat", bd=0, state="disabled")
        self.clarifications_text.pack(fill="both", expand=True, pady=(8, 0))
        
        # --- Right Frame: Grid ---
        top_right = tk.Frame(right_frame, bg=BG_DARK)
        top_right.pack(fill="x")
        tk.Label(top_right, text="3. Generated Test Cases", bg=BG_DARK, fg=TEXT_PRIMARY, font=FONT_HEADING).pack(side="left")
        self.approve_btn = tk.Button(top_right, text="💾 Approve & Save (vX)", bg=SUCCESS, fg="white", font=FONT_SMALL, relief="flat", cursor="hand2", state="disabled", command=self._approve_and_save)
        self.approve_btn.pack(side="right")
        
        cols = ("Module", "Feature", "TestCase", "Priority", "Confidence")
        self.tc_tree = ttk.Treeview(right_frame, columns=cols, show="headings", height=20)
        self.tc_tree.heading("Module", text="Module")
        self.tc_tree.heading("Feature", text="Feature")
        self.tc_tree.heading("TestCase", text="Test Case")
        self.tc_tree.heading("Priority", text="Priority")
        self.tc_tree.heading("Confidence", text="Confidence")
        
        self.tc_tree.column("Module", width=100)
        self.tc_tree.column("Feature", width=100)
        self.tc_tree.column("TestCase", width=300)
        self.tc_tree.column("Priority", width=60)
        self.tc_tree.column("Confidence", width=80)
        
        scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=self.tc_tree.yview)
        self.tc_tree.configure(yscrollcommand=scrollbar.set)
        self.tc_tree.pack(side="left", fill="both", expand=True, pady=(8, 0))
        scrollbar.pack(side="right", fill="y", pady=(8, 0))

    def _sync_settings(self):
        # Apply UI settings to in-memory settings object
        user_groq = self.api_var.get().strip()
        if user_groq and not user_groq.endswith("…"):
            settings.GROQ_API_KEY = user_groq
        
        settings.GEMINI_API_KEY = self.fallback_var.get()
        settings.BROWSER_HEADLESS = self.headless_var.get()
        settings.OUTPUT_DIR = self.output_dir_var.get().strip()
        
        # Reset the LLM client fallback state so it always starts with Groq
        from core.llm_client import llm
        llm.reset_fallback()

    def _analyze_requirements(self):
        raw_text = self.raw_req_text.get("1.0", "end").strip()
        if not raw_text:
            messagebox.showwarning("Empty", "Please enter some requirements first.")
            return
            
        self._sync_settings()
        self.analyze_btn.config(state="disabled", text="Analyzing...")
        self.clarifications_text.config(state="normal")
        self.clarifications_text.delete("1.0", "end")
        self.clarifications_text.insert("end", "AI is analyzing requirements...")
        self.clarifications_text.config(state="disabled")
        
        def _run_analysis():
            try:
                from agents.requirement_analysis import RequirementAnalysisAgent
                agent = RequirementAnalysisAgent()
                result = agent.analyze(raw_text)
                self.after(0, self._on_analysis_done, result)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
                self.after(0, lambda: self.analyze_btn.config(state="normal", text="🧠 Analyze Requirements"))
                
        threading.Thread(target=_run_analysis, daemon=True).start()
        
    def _on_analysis_done(self, result: dict):
        self.analyze_btn.config(state="normal", text="🧠 Analyze Requirements")
        self.current_analysis_json = result
        
        # Update Clarifications
        self.clarifications_text.config(state="normal")
        self.clarifications_text.delete("1.0", "end")
        
        clarifications = result.get("clarifications_needed", [])
        if clarifications:
            self.clarifications_text.insert("end", "⚠️ Missing Information Detected:\\n\\n", "warn")
            for c in clarifications:
                self.clarifications_text.insert("end", f"• {c}\\n")
            self.clarifications_text.insert("end", "\\nPlease update the raw requirements above and re-analyze.")
            self.approve_btn.config(state="disabled", bg=BORDER, cursor="arrow")
        else:
            self.clarifications_text.insert("end", "✅ Requirements look complete.\\nProject Context: " + result.get("project_context", ""))
            self.approve_btn.config(state="normal", bg=SUCCESS, cursor="hand2")
            
        self.clarifications_text.config(state="disabled")
        
        # Update Grid
        for row in self.tc_tree.get_children():
            self.tc_tree.delete(row)
            
        reqs = result.get("requirements", [])
        for i, req in enumerate(reqs):
            self.tc_tree.insert("", "end", values=(
                req.get("module", ""),
                req.get("feature", ""),
                req.get("test_case", ""),
                req.get("priority", ""),
                f"{req.get('confidence', 1.0):.0%}"
            ))
            
    def _approve_and_save(self):
        if not self.current_analysis_json:
            return
            
        # Resolve target directory (user-configured output directory or current directory)
        base_dir = Path(settings.OUTPUT_DIR).resolve() if settings.OUTPUT_DIR else Path(".")
        
        # Find next version number inside the target directory
        import glob
        pattern = str(base_dir / "requirements_v*.csv")
        existing_files = glob.glob(pattern)
        
        version = 1
        if existing_files:
            import os
            nums = []
            for f in existing_files:
                basename = os.path.basename(f)
                num_str = basename.replace("requirements_v", "").replace(".csv", "")
                if num_str.isdigit():
                    nums.append(int(num_str))
            if nums:
                version = max(nums) + 1
                
        filename = base_dir / f"requirements_v{version}.csv"
        json_filename = base_dir / f"analysis_v{version}.json"
        
        # Save JSON
        import json
        with open(json_filename, "w") as f:
            json.dump(self.current_analysis_json, f, indent=2)
            
        # Save CSV
        import csv
        reqs = self.current_analysis_json.get("requirements", [])
        headers = ["ID", "Module", "Feature", "Requirement", "Test Case", "Preconditions", "Test Data", "Expected Result", "Priority", "Confidence"]
        
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for i, req in enumerate(reqs):
                writer.writerow({
                    "ID": f"TC{str(i+1).zfill(3)}",
                    "Module": req.get("module", ""),
                    "Feature": req.get("feature", ""),
                    "Requirement": req.get("requirement", ""),
                    "Test Case": req.get("test_case", ""),
                    "Preconditions": "\\n".join(req.get("preconditions", []) if isinstance(req.get("preconditions"), list) else [req.get("preconditions", "")]),
                    "Test Data": req.get("test_data", ""),
                    "Expected Result": req.get("expected_result", ""),
                    "Priority": req.get("priority", "Medium"),
                    "Confidence": req.get("confidence", 1.0)
                })
                
        self.csv_var.set(str(filename))
        self.approve_btn.config(text=f"💾 Saved {filename.name}")
        self._log_message("SYSTEM", f"Pipeline 1 complete. Saved {filename.name} and {json_filename.name}")
        messagebox.showinfo("Approved", f"Test cases approved and saved to:\\n{filename}\\n\\nYou can now click 'Run Pipeline' to execute them.")


    def _browse_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All", "*.*")])
        if path:
            self.csv_var.set(path)

    def _browse_output_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir_var.set(path)

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _open_report(self):
        if self.last_report_dir:
            report = Path(self.last_report_dir) / "report.html"
            if report.exists():
                webbrowser.open(report.as_uri())
                return
        messagebox.showinfo("No Report", "No report generated yet. Run the pipeline first!")

    def _open_folder(self):
        if self.last_report_dir and os.path.exists(self.last_report_dir):
            subprocess.Popen(f'explorer "{self.last_report_dir}"')
        else:
            messagebox.showinfo("No Folder", "No report folder yet. Run the pipeline first!")

    def _request_stop(self):
        self._stop_requested = True
        self._log_message("WARNING", "Stop requested — will halt after current test completes...")

    # ── Logging ───────────────────────────────────────────────────────────────
    def _log_message(self, level: str, text: str):
        self.log_queue.put((level, text))

    def _poll_log_queue(self):
        try:
            while True:
                level, text = self.log_queue.get_nowait()
                self._write_log(level, text)
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)

    def _write_log(self, level: str, text: str):
        self.log_text.config(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] ", "ts")
        self.log_text.insert("end", f"[{level}] {text}\n", level)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    # ── Pipeline Runner ───────────────────────────────────────────────────────
    def _run_pipeline(self):
        if self.is_running:
            return

        # Auto-sync: If there are unapproved generated test cases, save them automatically
        if str(self.approve_btn["state"]) == "normal":
            self._log_message("SYSTEM", "Auto-approving generated test cases before run...")
            self._approve_and_save()
        elif self.current_analysis_json and not self.csv_var.get().startswith("requirements_v"):
            # They have generated analysis, but it's blocked by clarifications and hasn't been saved!
            response = messagebox.askyesno(
                "Pending Clarifications", 
                "You have generated test cases in the Test Engineering tab, but the AI asked for clarifications so they were not saved.\n\nDo you want to force-save and run them anyway?"
            )
            if response:
                self._approve_and_save()
            else:
                return

        csv_path = self.csv_var.get()
        if not os.path.exists(csv_path):
            messagebox.showerror("File Not Found", f"Requirements CSV not found:\n{csv_path}")
            return

        # Apply UI settings to in-memory settings object
        self._sync_settings()

        # Reset state
        self._stop_requested = False
        self.is_running = True
        self.run_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.report_btn.config(state="disabled")
        self.folder_btn.config(state="disabled")
        self.status_dot.config(text="● Running…", fg=ACCENT)
        self.progress.start(12)

        # Clear results
        for row in self.results_tree.get_children():
            self.results_tree.delete(row)

        self.notebook.select(0)  # Switch to log tab
        self._log_message("SYSTEM", "═" * 60)
        self._log_message("SYSTEM", f"Pipeline started | CSV: {csv_path}")
        self._log_message("SYSTEM", "═" * 60)

        thread = threading.Thread(target=self._run_in_thread, args=(csv_path,), daemon=True)
        thread.start()

    def _run_in_thread(self, csv_path: str):
        """Runs the full orchestrator pipeline in a background thread."""
        try:
            import csv as csv_mod
            from models.schemas import Requirement, TestResult
            from core.browser import BrowserManager
            from core.state import AgentState
            from agents.planner import PlannerAgent
            from agents.navigation import NavigationAgent, memory_store
            from agents.observation import ObservationAgent
            from agents.verification import VerificationAgent
            from agents.evidence import EvidenceAgent
            from agents.reporter import ReportingAgent
            from agents.reflection import ReflectionAgent
            from agents.requirement_analysis import RequirementAnalysisAgent

            # Clear memory cache for a fresh, clean execution run
            memory_store.clear()

            def ui_log(msg: str):
                level = "INFO"
                if "[ERROR]" in msg or "error" in msg.lower():
                    level = "ERROR"
                elif "[WARNING]" in msg or "warn" in msg.lower():
                    level = "WARNING"
                elif "PASS" in msg or "success" in msg.lower():
                    level = "SUCCESS"
                # Strip the logger prefix if present
                clean = msg.replace("[INFO] qa_platform: ", "").replace("[ERROR] qa_platform: ", "").replace("[WARNING] qa_platform: ", "")
                self._log_message(level, clean)

            # Monkey-patch the logger to also push to UI
            import utils.logger as logger_mod
            original_info = logger_mod.log.info
            original_warn = logger_mod.log.warning
            original_error = logger_mod.log.error

            logger_mod.log.info    = lambda m: (original_info(m),    self._log_message("INFO",    m))
            logger_mod.log.warning = lambda m: (original_warn(m),    self._log_message("WARNING", m))
            logger_mod.log.error   = lambda m: (original_error(m),   self._log_message("ERROR",   m))

            # Load requirements
            requirements = []
            with open(csv_path, mode='r', encoding='utf-8') as f:
                reader = csv_mod.DictReader(f)
                for row in reader:
                    requirements.append(Requirement(
                        id=row.get('ID', ''),
                        module=row.get('Module', 'General'),
                        feature=row.get('Feature', 'Unknown'),
                        description=row.get('Requirement', row.get('Description', '')),
                        preconditions=[p.strip() for p in row.get('Preconditions', '').split('\n') if p.strip()],
                        test_data=row.get('Test Data', ''),
                        expected_result=row.get('Expected Result', ''),
                        priority=row.get('Priority', 'Medium'),
                        confidence=float(row.get('Confidence', 1.0)) if row.get('Confidence') else 1.0,
                        business_rules=[row.get('Rules', '')]
                    ))

            self._log_message("INFO", f"Loaded {len(requirements)} requirement(s)")

            planner      = PlannerAgent()
            verification = VerificationAgent()
            evidence     = EvidenceAgent()
            reporter     = ReportingAgent(str(evidence.run_dir))
            self.last_report_dir = str(evidence.run_dir)

            final_results = []
            total = len(requirements)

            for idx, req in enumerate(requirements):
                if getattr(self, '_stop_requested', False):
                    self._log_message("WARNING", "Pipeline stopped by user.")
                    break

                self._log_message("SYSTEM", f"{'─'*50}")
                self._log_message("SYSTEM", f"[{idx+1}/{total}] {req.id}: {req.description[:80]}")

                state   = AgentState()
                state.current_requirement = req
                browser = BrowserManager(headless=settings.BROWSER_HEADLESS)

                try:
                    tasks = planner.plan(req)
                    if not tasks:
                        result = TestResult(test_case_id=req.id, status="FAIL", reasoning="Planner failed.")
                        final_results.append(result)
                        self._append_result(result)
                        continue

                    browser.launch_browser()
                    nav_agent        = NavigationAgent(browser)
                    reflection_agent = ReflectionAgent()
                    task_queue = tasks.copy()
                    retries = 0

                    while task_queue:
                        if getattr(self, '_stop_requested', False):
                            break
                        task = task_queue.pop(0)
                        success, msg = nav_agent.execute_task(task, state)
                        if not success:
                            if retries >= 3:
                                break
                            if "rate_limit_exceeded" in msg or "429" in msg:
                                self._log_message("ERROR", "Rate limit hit. Stopping navigation.")
                                break
                            retries += 1
                            corrections = reflection_agent.reflect(state, task, msg)
                            if corrections:
                                task_queue = corrections + task_queue
                            else:
                                break

                    obs_agent = ObservationAgent(browser)
                    obs_agent.observe(state, description=f"Final state for {req.id}")

                    result = verification.verify(state)
                    evidence.package_evidence(state)
                    final_results.append(result)
                    self._append_result(result)

                except Exception as e:
                    msg = f"Error: {e}"
                    self._log_message("ERROR", msg)
                    result = TestResult(test_case_id=req.id, status="FAIL", reasoning=msg)
                    final_results.append(result)
                    self._append_result(result)
                finally:
                    browser.close_browser()

            self._log_message("SYSTEM", "═" * 60)
            self._log_message("SYSTEM", "Generating reports…")
            reporter.generate_all(final_results)
            self._log_message("SUCCESS", f"All reports saved to: {self.last_report_dir}")

            # Restore logger
            logger_mod.log.info    = original_info
            logger_mod.log.warning = original_warn
            logger_mod.log.error   = original_error

        except Exception as e:
            self._log_message("ERROR", f"Pipeline crashed: {e}")
        finally:
            self.after(0, self._on_pipeline_done)

    def _append_result(self, result):
        """Inserts a result row into the results Treeview from any thread."""
        def _do():
            status = result.status.upper()
            tag    = status if status in ("PASS", "FAIL", "PARTIAL") else "pending"
            conf   = f"{result.confidence_score:.0%}" if result.confidence_score else "—"
            reason = result.reasoning
            if result.suggested_fix:
                reason += f" | FIX: {result.suggested_fix}"
            self.results_tree.insert("", "end",
                values=(result.test_case_id, status, conf, reason),
                tags=(status,))
        self.after(0, _do)

    def _on_pipeline_done(self):
        self.is_running = False
        self.run_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.report_btn.config(state="normal")
        self.folder_btn.config(state="normal")
        self.status_dot.config(text="● Done", fg=SUCCESS)
        self.progress.stop()
        self.notebook.select(1)  # Switch to Results tab
        self._log_message("SYSTEM", "Pipeline finished.")


if __name__ == "__main__":
    app = App()
    app.mainloop()
