"""
Evidence Agent.
Responsible for packaging and persisting all telemetry and logs from the AgentState
to the disk for reporting and debugging.
"""
import os
import json
from datetime import datetime
from pathlib import Path
from core.state import AgentState
from config.constants import REPORTS_DIR
from utils.logger import log

class EvidenceAgent:
    def __init__(self):
        # Create a unique run directory inside reports/
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = REPORTS_DIR / f"run_{timestamp}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        log.info(f"EvidenceAgent initialized. Packaging evidence to: {self.run_dir}")

    def package_evidence(self, state: AgentState) -> str:
        """
        Iterates over the state's observations and writes them to disk.
        Returns the path to the evidence package directory.
        """
        log.info("EvidenceAgent starting packaging process...")
        
        try:
            # Create a subfolder for this specific requirement if applicable
            req_id = state.current_requirement.id if state.current_requirement else "general"
            evidence_dir = self.run_dir / req_id
            evidence_dir.mkdir(exist_ok=True)
            
            if not state.observations:
                log.warning("No observations found in state to package.")
                return str(evidence_dir)
                
            # Usually we package the final/latest observation
            latest_obs = state.observations[-1]
            raw = latest_obs.raw_data or {}
            
            # 1. Package DOM & HTML
            if state.browser_state and state.browser_state.dom_snapshot:
                dom_path = evidence_dir / "dom_snapshot.html"
                with open(dom_path, "w", encoding="utf-8") as f:
                    f.write(state.browser_state.dom_snapshot)
                state.log_history(f"Evidence saved: {dom_path}")
                
            # 2. Package Console Logs
            console_logs = raw.get("full_console_logs", [])
            if console_logs:
                console_path = evidence_dir / "console_logs.json"
                with open(console_path, "w", encoding="utf-8") as f:
                    json.dump(console_logs, f, indent=4)
                state.log_history(f"Evidence saved: {console_path}")
                
            # 3. Package Network Requests (Pseudo-HAR)
            network_reqs = raw.get("full_network_requests", [])
            if network_reqs:
                network_path = evidence_dir / "network_requests.json"
                with open(network_path, "w", encoding="utf-8") as f:
                    json.dump(network_reqs, f, indent=4)
                state.log_history(f"Evidence saved: {network_path}")
            
            # 4. Package Telemetry Summary
            # Remove full logs from telemetry summary to keep it clean
            summary_raw = {k: v for k, v in raw.items() if k not in ["full_console_logs", "full_network_requests"]}
            telemetry_path = evidence_dir / "telemetry_summary.json"
            with open(telemetry_path, "w", encoding="utf-8") as f:
                json.dump(summary_raw, f, indent=4)
            state.log_history(f"Evidence saved: {telemetry_path}")
            
            # 5. Accessibility Report
            if state.browser_state and state.browser_state.accessibility_tree:
                a11y_path = evidence_dir / "accessibility_report.json"
                with open(a11y_path, "w", encoding="utf-8") as f:
                    json.dump(state.browser_state.accessibility_tree, f, indent=4)
                state.log_history(f"Evidence saved: {a11y_path}")
                
            # 6. Copy Screenshot
            if state.browser_state and state.browser_state.latest_screenshot_path:
                import shutil
                src_screenshot = Path(state.browser_state.latest_screenshot_path)
                if src_screenshot.exists():
                    dst_screenshot = evidence_dir / src_screenshot.name
                    shutil.copy2(src_screenshot, dst_screenshot)
                    state.log_history(f"Evidence saved: {dst_screenshot}")
            
            log.info(f"Evidence successfully packaged into {evidence_dir}")
            return str(evidence_dir)
            
        except Exception as e:
            error_msg = f"EvidenceAgent failed to package evidence: {e}"
            log.error(error_msg)
            state.add_failure(error_msg)
            return ""
