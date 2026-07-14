import os
import sys
import csv
import json
import glob
import logging
from datetime import datetime
from pathlib import Path
import gradio as gr
import pandas as pd

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.settings import settings
from config.constants import PROJECT_ROOT, REPORTS_DIR
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

# ─────────────────────────────────────────────────────────────────────────────
# Logger Redirection for Gradio
# ─────────────────────────────────────────────────────────────────────────────
# Global logs cache and active tracking
logs_cache = {
    "Global System Logs": []
}
active_test_case = "Global System Logs"

class GradioLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        try:
            log_entry = self.format(record)
            self.records.append(log_entry)
            
            global active_test_case, logs_cache
            # Write to the active test case partition
            if active_test_case not in logs_cache:
                logs_cache[active_test_case] = []
            logs_cache[active_test_case].append(log_entry)
            
            # Also append to global system logs
            if active_test_case != "Global System Logs":
                if "Global System Logs" not in logs_cache:
                    logs_cache["Global System Logs"] = []
                logs_cache["Global System Logs"].append(log_entry)
        except Exception:
            self.handleError(record)

    def get_logs(self, key="Global System Logs") -> str:
        global logs_cache
        entries = logs_cache.get(key, [])
        if isinstance(entries, list):
            return "\n".join(entries)
        return str(entries)

    def clear(self):
        self.records.clear()
        global logs_cache, active_test_case
        logs_cache = {
            "Global System Logs": []
        }
        active_test_case = "Global System Logs"

# Setup log hook
gradio_log_handler = GradioLogHandler()
gradio_log_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
logging.getLogger("qa_platform").addHandler(gradio_log_handler)

# Helper to build structured test execution HTML status
def build_status_html(requirements: list, current_id: str, results: dict) -> str:
    html = """
    <div style="background-color: #1e293b; padding: 15px; border-radius: 8px; border: 1px solid #334155; max-height: 250px; overflow-y: auto;">
        <h4 style="color: #94a3b8; margin-top: 0; margin-bottom: 10px; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px;">Test Execution Status</h4>
        <ul style="list-style: none; padding: 0; margin: 0;">
    """
    
    for req in requirements:
        status = results.get(req.id, "PENDING")
        if req.id == current_id and status == "PENDING":
            status = "RUNNING"
            
        color = "#64748b" # gray
        icon = "⚪"
        badge_text = "Pending"
        
        if status == "RUNNING":
            color = "#f59e0b" # amber
            icon = "🟡"
            badge_text = "Running"
        elif status == "PASS":
            color = "#22c55e" # green
            icon = "🟢"
            badge_text = "Pass"
        elif status == "FAIL":
            color = "#ef4444" # red
            icon = "🔴"
            badge_text = "Fail"
            
        html += f"""
        <li style="display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; border-bottom: 1px solid #334155; font-size: 13px;">
            <div style="display: flex; align-items: center; gap: 8px; color: #f8fafc;">
                <span style="font-size: 14px;">{icon}</span>
                <strong>{req.id}</strong>
                <span style="color: #94a3b8; max-width: 250px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{req.description}">{req.description}</span>
            </div>
            <span style="background-color: {color}20; color: {color}; border: 1px solid {color}40; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">
                {badge_text}
            </span>
        </li>
        """
        
    html += """
        </ul>
    </div>
    """
    return html

# ─────────────────────────────────────────────────────────────────────────────
# Global States
# ─────────────────────────────────────────────────────────────────────────────
is_running = False
stop_requested = False
current_analysis_json = None
last_report_dir = None

# Helper to scan for CSV files
def list_csv_files(output_dir=None):
    base_dir = Path(output_dir or settings.OUTPUT_DIR or ".")
    files = glob.glob(str(base_dir / "*.csv"))
    root_files = glob.glob("*.csv")
    all_files = list(set([str(Path(f).resolve()) for f in files + root_files]))
    return sorted(all_files)

# ─────────────────────────────────────────────────────────────────────────────
# Tab 1: Pipeline Execution logic
# ─────────────────────────────────────────────────────────────────────────────
def run_pipeline(csv_file, headless, output_dir, max_retries, groq_key, gemini_key, default_llm, gemini_default, auto_track, selected_tc):
    global is_running, stop_requested, last_report_dir, active_test_case, logs_cache
    
    if is_running:
        yield "Pipeline is already running!", pd.DataFrame(columns=["Test Case ID", "Status", "Confidence", "Reasoning"]), "", gr.update(), "Pipeline is already running!"
        return

    is_running = True
    stop_requested = False
    
    # Update settings from UI inputs
    settings.BROWSER_HEADLESS = headless
    settings.OUTPUT_DIR = output_dir or "reports"
    settings.MAX_RETRIES = int(max_retries)
    if groq_key:
        settings.GROQ_API_KEY = groq_key
    if gemini_key:
        settings.GEMINI_API_KEY = gemini_key
    if default_llm:
        settings.DEFAULT_LLM_MODEL = default_llm
    if gemini_default:
        settings.GEMINI_DEFAULT_MODEL = gemini_default
        
    gradio_log_handler.clear()
    
    if csv_file is None or not str(csv_file).strip():
        is_running = False
        yield "Error: No CSV file selected or uploaded.", pd.DataFrame(columns=["Test Case ID", "Status", "Confidence", "Reasoning"]), "", gr.update(), "Error: No CSV file selected or uploaded."
        return
        
    csv_path = csv_file.name if hasattr(csv_file, 'name') else csv_file
        
    if not os.path.exists(csv_path):
        is_running = False
        yield f"Error: CSV file not found at {csv_path}", pd.DataFrame(columns=["Test Case ID", "Status", "Confidence", "Reasoning"]), "", gr.update(), f"Error: CSV file not found at {csv_path}"
        return

    logger = logging.getLogger("qa_platform")
    logger.info(f"Starting test execution pipeline for requirements in {csv_path}")
    
    # Load requirements
    requirements = []
    try:
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
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
    except Exception as e:
        is_running = False
        logger.error(f"Failed to load requirements from CSV: {e}")
        yield "Error loading CSV", pd.DataFrame(columns=["Test Case ID", "Status", "Confidence", "Reasoning"]), "", gr.update(), gradio_log_handler.get_logs("Global System Logs")
        return

    logger.info(f"Loaded {len(requirements)} requirement(s) from CSV")
    
    # Build initial status HTML
    results_map = {}
    active_test_case = "Global System Logs"
    status_html = build_status_html(requirements, active_test_case, results_map)
    
    dropdown_choices = ["Global System Logs"] + [r.id for r in requirements]
    dropdown_val = active_test_case if auto_track else (selected_tc or "Global System Logs")
    
    yield status_html, pd.DataFrame(columns=["Test Case ID", "Status", "Confidence", "Reasoning"]), "", gr.update(choices=dropdown_choices, value=dropdown_val), gradio_log_handler.get_logs(dropdown_val)

    planner = PlannerAgent()
    verification = VerificationAgent()
    evidence = EvidenceAgent()
    reporter = ReportingAgent(str(evidence.run_dir))
    last_report_dir = str(evidence.run_dir)
    
    # Reset navigation memory cache at the start of the execution run
    memory_store.clear()
    
    final_results = []
    results_table_data = []

    total = len(requirements)
    for idx, req in enumerate(requirements):
        if stop_requested:
            logger.warning("Pipeline execution stopped by user request.")
            break
            
        # Switch logging focus to this test case
        active_test_case = req.id
        logs_cache[active_test_case] = []
        
        logger.info(f"====== [{idx+1}/{total}] Processing Test Case: {req.id} ======")
        
        status_html = build_status_html(requirements, active_test_case, results_map)
        dropdown_val = active_test_case if auto_track else (selected_tc or "Global System Logs")
        yield status_html, pd.DataFrame(results_table_data, columns=["Test Case ID", "Status", "Confidence", "Reasoning"]), "", gr.update(choices=dropdown_choices, value=dropdown_val), gradio_log_handler.get_logs(dropdown_val)

        state = AgentState()
        state.current_requirement = req
        browser = BrowserManager(headless=settings.BROWSER_HEADLESS)

        try:
            tasks = planner.plan(req)
            if not tasks:
                res = TestResult(test_case_id=req.id, status="FAIL", reasoning="Planner failed to generate steps.")
                final_results.append(res)
                results_table_data.append([req.id, res.status, f"{res.confidence_score or 1.0:.0%}", res.reasoning])
                results_map[req.id] = "FAIL"
                status_html = build_status_html(requirements, active_test_case, results_map)
                dropdown_val = active_test_case if auto_track else (selected_tc or "Global System Logs")
                yield status_html, pd.DataFrame(results_table_data, columns=["Test Case ID", "Status", "Confidence", "Reasoning"]), "", gr.update(choices=dropdown_choices, value=dropdown_val), gradio_log_handler.get_logs(dropdown_val)
                continue

            browser.launch_browser()
            nav_agent = NavigationAgent(browser)
            reflection_agent = ReflectionAgent()
            task_queue = tasks.copy()
            retries = 0

            while task_queue:
                if stop_requested:
                    break
                task = task_queue.pop(0)
                success, msg = nav_agent.execute_task(task, state)
                if not success:
                    if retries >= 3:
                        break
                    if "rate_limit_exceeded" in msg or "429" in msg:
                        logger.error("Rate limit hit. Stopping navigation.")
                        break
                    retries += 1
                    corrections = reflection_agent.reflect(state, task, msg)
                    if corrections:
                        task_queue = corrections + task_queue
                    else:
                        break

            obs_agent = ObservationAgent(browser)
            obs_agent.observe(state, description=f"Final state for {req.id}")

            res = verification.verify(state)
            evidence.package_evidence(state)
            final_results.append(res)
            
            status_val = res.status.upper()
            results_map[req.id] = status_val
            conf_val = f"{res.confidence_score:.0%}" if res.confidence_score else "—"
            reason_val = res.reasoning
            if res.suggested_fix:
                reason_val += f" | Suggested Fix: {res.suggested_fix}"
            results_table_data.append([req.id, status_val, conf_val, reason_val])
            
            status_html = build_status_html(requirements, active_test_case, results_map)
            dropdown_val = active_test_case if auto_track else (selected_tc or "Global System Logs")
            yield status_html, pd.DataFrame(results_table_data, columns=["Test Case ID", "Status", "Confidence", "Reasoning"]), "" , gr.update(choices=dropdown_choices, value=dropdown_val), gradio_log_handler.get_logs(dropdown_val)

        except Exception as e:
            msg = f"Execution Exception: {e}"
            logger.error(msg)
            res = TestResult(test_case_id=req.id, status="FAIL", reasoning=msg)
            final_results.append(res)
            results_map[req.id] = "FAIL"
            results_table_data.append([req.id, "FAIL", "—", msg])
            status_html = build_status_html(requirements, active_test_case, results_map)
            dropdown_val = active_test_case if auto_track else (selected_tc or "Global System Logs")
            yield status_html, pd.DataFrame(results_table_data, columns=["Test Case ID", "Status", "Confidence", "Reasoning"]), "", gr.update(choices=dropdown_choices, value=dropdown_val), gradio_log_handler.get_logs(dropdown_val)
        finally:
            browser.close_browser()

    # Reset active test case to Global System Logs after completion
    active_test_case = "Global System Logs"
    logger.info("Pipeline test execution complete. Compiling final reports...")
    
    status_html = build_status_html(requirements, active_test_case, results_map)
    dropdown_val = active_test_case if auto_track else (selected_tc or "Global System Logs")
    yield status_html, pd.DataFrame(results_table_data, columns=["Test Case ID", "Status", "Confidence", "Reasoning"]), "", gr.update(choices=dropdown_choices, value=dropdown_val), gradio_log_handler.get_logs(dropdown_val)

    try:
        reporter.generate_all(final_results)
        logger.info(f"All reports saved successfully to: {last_report_dir}")
    except Exception as e:
        logger.error(f"Failed to generate reports: {e}")
        
    status_html = build_status_html(requirements, active_test_case, results_map)
    dropdown_val = active_test_case if auto_track else (selected_tc or "Global System Logs")
    yield status_html, pd.DataFrame(results_table_data, columns=["Test Case ID", "Status", "Confidence", "Reasoning"]), "", gr.update(choices=dropdown_choices, value=dropdown_val), gradio_log_handler.get_logs(dropdown_val)

    is_running = False
    
    # Generate HTML block containing download/view links
    report_folder_name = os.path.basename(last_report_dir)
    report_url = f"/reports/{report_folder_name}/report.html"
    report_html = f"""
    <div style="background-color: #1e293b; padding: 15px; border-radius: 8px; border: 1px solid #475569; margin-top: 15px;">
        <h4 style="color: #22c55e; margin-top: 0; font-size: 16px;">✅ Pipeline Run Complete</h4>
        <p style="color: #f8fafc; margin-bottom: 12px; font-size: 14px;">HTML, CSV, Excel and PDF reports have been generated.</p>
        <div style="display: flex; gap: 15px; flex-wrap: wrap;">
            <a href="{report_url}" target="_blank" style="background-color: #6366f1; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 14px; transition: background 0.2s;">
                🌐 Open HTML Report in Browser
            </a>
            <span style="color: #94a3b8; align-self: center; font-size: 13px;">Local Directory: <code>{last_report_dir}</code></span>
        </div>
    </div>
    """
    dropdown_val = active_test_case if auto_track else (selected_tc or "Global System Logs")
    yield status_html, pd.DataFrame(results_table_data, columns=["Test Case ID", "Status", "Confidence", "Reasoning"]), report_html, gr.update(choices=dropdown_choices, value=dropdown_val), gradio_log_handler.get_logs(dropdown_val)

def stop_pipeline(selected_tc):
    global stop_requested
    stop_requested = True
    logging.getLogger("qa_platform").warning("Stop requested by user — will halt after current test case completes...")
    return gradio_log_handler.get_logs(selected_tc)

# ─────────────────────────────────────────────────────────────────────────────
# Tab 2: Requirements Analysis Logic
# ─────────────────────────────────────────────────────────────────────────────
def analyze_requirements(raw_text, groq_key, gemini_key, default_llm, gemini_default):
    global current_analysis_json
    
    if not raw_text.strip():
        return (
            "<div style='color: #ef4444;'>Please enter raw requirements text first.</div>",
            gr.update(interactive=False),
            pd.DataFrame(columns=["Module", "Feature", "Test Case", "Priority", "Confidence"]),
            gr.update()
        )
        
    # Apply temporary settings for analysis
    if groq_key:
        settings.GROQ_API_KEY = groq_key
    if gemini_key:
        settings.GEMINI_API_KEY = gemini_key
    if default_llm:
        settings.DEFAULT_LLM_MODEL = default_llm
    if gemini_default:
        settings.GEMINI_DEFAULT_MODEL = gemini_default
        
    logging.getLogger("qa_platform").info("Starting requirements intelligence analysis from UI...")
    
    analyzer = RequirementAnalysisAgent()
    result = analyzer.analyze(raw_text)
    current_analysis_json = result
    
    clarifications = result.get("clarifications_needed", [])
    if clarifications:
        clarifications_html = """
        <div style="background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px; border-radius: 6px; margin-bottom: 15px; color: #78350f;">
            <strong style="font-size: 15px;">⚠️ Missing Information/Clarifications Needed:</strong>
            <ul style="margin: 8px 0 0 16px; padding: 0;">
        """
        for c in clarifications:
            clarifications_html += f"<li style='margin-bottom: 4px;'>{c}</li>"
        clarifications_html += """
            </ul>
            <p style="margin-top: 8px; font-size: 13px; font-style: italic;">Update the raw requirements above with the details and re-analyze to enable saving.</p>
        </div>
        """
        enable_save = gr.update(interactive=False)
    else:
        clarifications_html = f"""
        <div style="background-color: #dcfce7; border-left: 4px solid #22c55e; padding: 12px; border-radius: 6px; margin-bottom: 15px; color: #14532d;">
            <strong>✅ Requirements Complete!</strong>
            <p style="margin: 4px 0 0 0; font-size: 13px;">Project Context: {result.get('project_context', '')}</p>
        </div>
        """
        enable_save = gr.update(interactive=True)
        
    reqs = result.get("requirements", [])
    table_data = []
    for r in reqs:
        table_data.append([
            r.get("module", ""),
            r.get("feature", ""),
            r.get("test_case", ""),
            r.get("priority", "Medium"),
            f"{r.get('confidence', 1.0):.0%}"
        ])
        
    df = pd.DataFrame(table_data, columns=["Module", "Feature", "Test Case", "Priority", "Confidence"])
    return clarifications_html, enable_save, df, ""

def approve_and_save(output_dir):
    global current_analysis_json
    if not current_analysis_json:
        return "<div style='color: #ef4444;'>No analysis results to save. Run analysis first.</div>", gr.update()
        
    base_dir = Path(output_dir or settings.OUTPUT_DIR or ".")
    base_dir.mkdir(parents=True, exist_ok=True)
    
    # Auto-resolve version number
    pattern = str(base_dir / "requirements_v*.csv")
    existing_files = glob.glob(pattern)
    
    version = 1
    if existing_files:
        nums = []
        for f in existing_files:
            basename = os.path.basename(f)
            num_str = basename.replace("requirements_v", "").replace(".csv", "")
            if num_str.isdigit():
                nums.append(int(num_str))
        if nums:
            version = max(nums) + 1
            
    csv_filename = (base_dir / f"requirements_v{version}.csv").resolve()
    json_filename = (base_dir / f"analysis_v{version}.json").resolve()
    
    # Save Raw Analysis JSON
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(current_analysis_json, f, indent=2)
        
    # Save Structured CSV Requirements
    reqs = current_analysis_json.get("requirements", [])
    headers = ["ID", "Module", "Feature", "Requirement", "Test Case", "Preconditions", "Test Data", "Expected Result", "Priority", "Confidence"]
    
    with open(csv_filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for i, req in enumerate(reqs):
            writer.writerow({
                "ID": f"TC{str(i+1).zfill(3)}",
                "Module": req.get("module", ""),
                "Feature": req.get("feature", ""),
                "Requirement": req.get("requirement", ""),
                "Test Case": req.get("test_case", ""),
                "Preconditions": "\n".join(req.get("preconditions", []) if isinstance(req.get("preconditions"), list) else [req.get("preconditions", "")]),
                "Test Data": req.get("test_data", ""),
                "Expected Result": req.get("expected_result", ""),
                "Priority": req.get("priority", "Medium"),
                "Confidence": req.get("confidence", 1.0)
            })
            
    logging.getLogger("qa_platform").info(f"Saved: {csv_filename.name} and {json_filename.name}")
    
    # Re-scan for files to update the selector dropdown
    updated_files = list_csv_files(output_dir)
    csv_dropdown_update = gr.update(choices=updated_files, value=str(csv_filename))
    
    status_html = f"""
    <div style="background-color: #dcfce7; border-left: 4px solid #22c55e; padding: 12px; border-radius: 6px; margin-top: 10px; color: #14532d;">
        <strong>💾 Saved Successfully!</strong>
        <p style="margin: 4px 0 0 0; font-size: 13px;">Created <code>{csv_filename.name}</code> and <code>{json_filename.name}</code>. You can now run this suite from the Test Runner tab.</p>
    </div>
    """
    return status_html, csv_dropdown_update

# ─────────────────────────────────────────────────────────────────────────────
# Tab 3: Configuration Settings Logic
# ─────────────────────────────────────────────────────────────────────────────
def save_settings(headless, output_dir, max_retries, groq_key, gemini_key, default_llm, gemini_default):
    settings.BROWSER_HEADLESS = headless
    settings.OUTPUT_DIR = output_dir or "reports"
    settings.MAX_RETRIES = int(max_retries)
    if groq_key:
        settings.GROQ_API_KEY = groq_key
    if gemini_key:
        settings.GEMINI_API_KEY = gemini_key
    if default_llm:
        settings.DEFAULT_LLM_MODEL = default_llm
    if gemini_default:
        settings.GEMINI_DEFAULT_MODEL = gemini_default
        
    try:
        lines = []
        if os.path.exists(".env"):
            with open(".env", "r", encoding="utf-8") as f:
                lines = f.readlines()
        
        env_keys = {
            "BROWSER_HEADLESS": str(headless).lower(),
            "OUTPUT_DIR": output_dir,
            "MAX_RETRIES": str(max_retries),
            "DEFAULT_LLM_MODEL": default_llm,
            "GEMINI_DEFAULT_MODEL": gemini_default
        }
        if groq_key:
            env_keys["GROQ_API_KEY"] = groq_key
        if gemini_key:
            env_keys["GEMINI_API_KEY"] = gemini_key
            
        new_lines = []
        processed_keys = set()
        for line in lines:
            line_strip = line.strip()
            if "=" in line_strip and not line_strip.startswith("#"):
                parts = line_strip.split("=", 1)
                k = parts[0].strip()
                if k in env_keys:
                    new_lines.append(f"{k}={env_keys[k]}\n")
                    processed_keys.add(k)
                    continue
            new_lines.append(line)
            
        for k, v in env_keys.items():
            if k not in processed_keys:
                new_lines.append(f"{k}={v}\n")
                
        with open(".env", "w", encoding="utf-8") as f:
            f.writelines(new_lines)
            
        return "<div style='color: #22c55e; font-weight: bold;'>✅ Settings saved to .env file and synced in-memory!</div>"
    except Exception as e:
        return f"<div style='color: #ef4444;'>⚠️ Synced in-memory, but failed to write to .env: {e}</div>"

# ─────────────────────────────────────────────────────────────────────────────
# UI Construction (Gradio Blocks)
# ─────────────────────────────────────────────────────────────────────────────
custom_css = """
body.dark {
    --body-background-fill: #0f172a;
    --background-fill-primary: #1e293b;
    --background-fill-secondary: #0f172a;
    --border-color-primary: #334155;
    --text-color-primary: #f8fafc;
    --text-color-secondary: #94a3b8;
}
.gradio-container {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif !important;
}
.log-box textarea {
    font-family: 'Consolas', 'Courier New', monospace !important;
    font-size: 13px !important;
    line-height: 1.4 !important;
}
"""

with gr.Blocks(theme=gr.themes.Default(primary_hue="indigo", secondary_hue="slate"), css=custom_css, title="AI Test Engineering Platform") as gradio_app:
    gr.Markdown("# 🤖 AI Test Engineering Platform")
    gr.Markdown("An autonomous, multi-agent orchestration framework that executes, self-heals, and reports web application tests.")
    
    with gr.Tabs() as tabs:
        # ── TAB 1: TEST RUNNER ───────────────────────────────────────────────
        with gr.Tab("Test Runner"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### ⚙️ Run Configuration")
                    
                    csv_options = list_csv_files()
                    default_csv = csv_options[0] if csv_options else ""
                    
                    csv_selector = gr.Dropdown(
                        label="Select Requirements CSV File", 
                        choices=csv_options, 
                        value=default_csv, 
                        interactive=True
                    )
                    
                    upload_csv = gr.File(
                        label="Or Upload New CSV File", 
                        file_types=[".csv"], 
                        type="filepath"
                    )
                    
                    headless_opt = gr.Checkbox(
                        label="Headless Browser Mode", 
                        value=settings.BROWSER_HEADLESS
                    )
                    
                    with gr.Accordion("🔑 API Overrides & Advanced", open=False):
                        groq_key_input = gr.Textbox(
                            label="Groq API Key Override", 
                            placeholder="gsk_...", 
                            type="password",
                            value=settings.GROQ_API_KEY if settings.GROQ_API_KEY else ""
                        )
                        gemini_key_input = gr.Textbox(
                            label="Gemini API Key Override", 
                            placeholder="AIza...", 
                            type="password",
                            value=settings.GEMINI_API_KEY if settings.GEMINI_API_KEY else ""
                        )
                        
                    with gr.Row():
                        run_btn = gr.Button("🚀 Run Pipeline", variant="primary")
                        stop_btn = gr.Button("🛑 Stop Run", variant="stop")
                        
                with gr.Column(scale=2):
                    gr.Markdown("### 📋 Live Output & Execution Results")
                    
                    # Colored list of test cases showing status
                    live_status_html = gr.HTML(
                        value="<div style='color: #94a3b8; font-style: italic;'>Run the pipeline to view execution status.</div>"
                    )
                    
                    with gr.Row():
                        log_viewer_dropdown = gr.Dropdown(
                            choices=["Global System Logs"],
                            value="Global System Logs",
                            label="Select Test Case to View Raw Logs",
                            scale=3
                        )
                        auto_track_logs = gr.Checkbox(
                            label="Auto-follow current test",
                            value=True,
                            scale=1
                        )
                    
                    # Log streamer textbox
                    console_output = gr.Textbox(
                        label="Test Case Raw Logs", 
                        lines=12, 
                        max_lines=30, 
                        elem_classes=["log-box"],
                        value="Logs will appear here when a test case is selected or running."
                    )
                    
                    # HTML report placeholder
                    report_status_output = gr.HTML(value="")
            
            gr.Markdown("### 📊 Test Case Results")
            results_df = gr.Dataframe(
                headers=["Test Case ID", "Status", "Confidence", "Reasoning"],
                datatype=["str", "str", "str", "str"],
                col_count=(4, "fixed"),
                interactive=False,
                wrap=True
            )
            
            # Map elements
            run_btn.click(
                fn=run_pipeline,
                inputs=[
                    csv_selector, 
                    headless_opt, 
                    gr.State(settings.OUTPUT_DIR), 
                    gr.State(settings.MAX_RETRIES), 
                    groq_key_input, 
                    gemini_key_input,
                    gr.State(settings.DEFAULT_LLM_MODEL),
                    gr.State(settings.GEMINI_DEFAULT_MODEL),
                    auto_track_logs,
                    log_viewer_dropdown
                ],
                outputs=[live_status_html, results_df, report_status_output, log_viewer_dropdown, console_output]
            )
            
            stop_btn.click(
                fn=stop_pipeline,
                inputs=[log_viewer_dropdown],
                outputs=[console_output]
            )
            
            # Callback to update console log display when user selects a different test case
            def update_log_display(selected_tc):
                return gradio_log_handler.get_logs(selected_tc)
                
            log_viewer_dropdown.change(
                fn=update_log_display,
                inputs=[log_viewer_dropdown],
                outputs=[console_output]
            )
            
            # Update selector dynamically on file upload
            def handle_upload(file):
                if file:
                    return gr.update(choices=list_csv_files(), value=file.name)
                return gr.update()
                
            upload_csv.change(
                fn=handle_upload,
                inputs=[upload_csv],
                outputs=[csv_selector]
            )
            
        # ── TAB 2: REQUIREMENTS ANALYSIS ──────────────────────────────────────
        with gr.Tab("Requirements Analysis"):
            gr.Markdown("### 🧠 Analyze Raw Project Requirements")
            gr.Markdown("Input plain text requirements, BRDs, or user stories. The AI agent will parse them into structured test cases.")
            
            with gr.Row():
                with gr.Column(scale=1):
                    raw_requirements_input = gr.Textbox(
                        label="Raw Requirements Input (Text)",
                        placeholder="Paste user stories, URLs, credentials, or other specifications here...",
                        lines=12
                    )
                    
                    analyze_btn = gr.Button("🧠 Analyze Requirements", variant="primary")
                    approve_btn = gr.Button("💾 Approve and Save CSV", variant="secondary", interactive=False)
                    save_status_output = gr.HTML(value="")
                    
                with gr.Column(scale=1):
                    # For clarifications & missing info
                    clarifications_output = gr.HTML(
                        value="<div style='color: #94a3b8; font-style: italic;'>Submit requirements for analysis to check completeness.</div>"
                    )
            
            gr.Markdown("### 🧪 Generated Structured Test Cases")
            analysis_df = gr.Dataframe(
                headers=["Module", "Feature", "Test Case", "Priority", "Confidence"],
                datatype=["str", "str", "str", "str", "str"],
                col_count=(5, "fixed"),
                interactive=False,
                wrap=True
            )
            
            # Action maps
            analyze_btn.click(
                fn=analyze_requirements,
                inputs=[
                    raw_requirements_input, 
                    groq_key_input, 
                    gemini_key_input,
                    gr.State(settings.DEFAULT_LLM_MODEL),
                    gr.State(settings.GEMINI_DEFAULT_MODEL)
                ],
                outputs=[clarifications_output, approve_btn, analysis_df, save_status_output]
            )
            
            approve_btn.click(
                fn=approve_and_save,
                inputs=[gr.State(settings.OUTPUT_DIR)],
                outputs=[save_status_output, csv_selector]
            )
            
        # ── TAB 3: SETTINGS ──────────────────────────────────────────────────
        with gr.Tab("Platform Settings"):
            gr.Markdown("### ⚙️ System Settings")
            gr.Markdown("Configure default orchestration options and API configurations. Saving settings writes them directly to `.env`.")
            
            with gr.Row():
                with gr.Column(scale=1):
                    setting_headless = gr.Checkbox(
                        label="Headless Browser Mode", 
                        value=settings.BROWSER_HEADLESS
                    )
                    
                    setting_output_dir = gr.Textbox(
                        label="Output Directory (for Reports)", 
                        value=settings.OUTPUT_DIR or "reports"
                    )
                    
                    setting_max_retries = gr.Number(
                        label="Max Self-Healing Retries per Step", 
                        value=settings.MAX_RETRIES,
                        precision=0
                    )
                    
                    setting_default_llm = gr.Dropdown(
                        label="Default Primary LLM Model",
                        choices=["llama-3.3-70b-versatile", "gemini-2.5-flash", "deepseek-r1"],
                        value=settings.DEFAULT_LLM_MODEL
                    )
                    
                    setting_gemini_default = gr.Dropdown(
                        label="Gemini Fallback/Vision Model",
                        choices=["gemini-2.5-flash", "gemini-2.0-flash-exp"],
                        value=settings.GEMINI_DEFAULT_MODEL
                    )
                    
                with gr.Column(scale=1):
                    setting_groq_key = gr.Textbox(
                        label="Groq API Key", 
                        placeholder="Keep unchanged or paste new key...", 
                        type="password",
                        value=settings.GROQ_API_KEY if settings.GROQ_API_KEY else ""
                    )
                    
                    setting_gemini_key = gr.Textbox(
                        label="Gemini API Key", 
                        placeholder="Keep unchanged or paste new key...", 
                        type="password",
                        value=settings.GEMINI_API_KEY if settings.GEMINI_API_KEY else ""
                    )
                    
            save_settings_btn = gr.Button("💾 Save Configuration Settings", variant="primary")
            save_settings_status = gr.HTML(value="")
            
            save_settings_btn.click(
                fn=save_settings,
                inputs=[
                    setting_headless,
                    setting_output_dir,
                    setting_max_retries,
                    setting_groq_key,
                    setting_gemini_key,
                    setting_default_llm,
                    setting_gemini_default
                ],
                outputs=[save_settings_status]
            )

# Standalone run entry point
if __name__ == "__main__":
    gradio_app.launch(server_name="0.0.0.0", server_port=8000)
