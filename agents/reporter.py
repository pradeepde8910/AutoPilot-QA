"""
Reporting Agent.
Generates comprehensive Test Execution Reports in CSV, Excel, HTML, and PDF.
"""
import os
import csv
from datetime import datetime
from typing import List
from pathlib import Path
import pandas as pd
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright
from models.schemas import TestResult
from utils.logger import log

class ReportingAgent:
    def __init__(self, run_dir: str):
        self.run_dir = Path(run_dir)
        # Template directory is exactly at the root / templates
        self.template_dir = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates')))
        
    def generate_csv(self, results: List[TestResult]):
        log.info("Generating CSV Report...")
        csv_path = self.run_dir / "report.csv"
        with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Test ID", "Status", "Confidence", "Reasoning", "Suggested Fix"])
            for res in results:
                writer.writerow([res.test_case_id, res.status, res.confidence_score, res.reasoning, res.suggested_fix])
        log.info(f"CSV saved to {csv_path}")
        return csv_path

    def generate_excel(self, results: List[TestResult]):
        log.info("Generating Excel Report...")
        excel_path = self.run_dir / "report.xlsx"
        
        data = []
        for res in results:
            data.append({
                "Test ID": res.test_case_id,
                "Status": res.status,
                "Confidence": res.confidence_score,
                "Reasoning": res.reasoning,
                "Suggested Fix": res.suggested_fix
            })
            
        df = pd.DataFrame(data)
        
        # Use openpyxl via pandas ExcelWriter for basic styling
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Test Results')
            
            # Auto-adjust columns width
            worksheet = writer.sheets['Test Results']
            for idx, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_len, 50)
                
        log.info(f"Excel saved to {excel_path}")
        return excel_path

    def generate_html(self, results: List[TestResult]):
        log.info("Generating HTML Dashboard...")
        html_path = self.run_dir / "report.html"
        
        env = Environment(loader=FileSystemLoader(self.template_dir))
        template = env.get_template('report.html')
        
        passed = sum(1 for r in results if r.status == 'PASS')
        failed = sum(1 for r in results if r.status == 'FAIL')
        partial = sum(1 for r in results if r.status == 'PARTIAL')
        total = len(results)
        pass_rate = round((passed / total * 100) if total > 0 else 0, 1)
        
        html_content = template.render(
            date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total=total,
            passed=passed,
            failed=failed,
            partial=partial,
            pass_rate=pass_rate,
            results=results
        )
        
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        log.info(f"HTML Dashboard saved to {html_path}")
        return html_path

    def generate_pdf(self, html_path: str):
        log.info("Generating PDF Report from HTML Dashboard using Playwright...")
        pdf_path = self.run_dir / "report.pdf"
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # File URL format
                abs_path = os.path.abspath(html_path).replace('\\', '/')
                file_url = f"file:///{abs_path}"
                
                page.goto(file_url, wait_until="networkidle")
                # Wait for Chart.js animation to finish
                page.wait_for_timeout(1500)
                
                page.pdf(path=str(pdf_path), format="A4", print_background=True, margin={"top": "20px", "bottom": "20px"})
                browser.close()
                
            log.info(f"PDF Report saved to {pdf_path}")
            return pdf_path
        except Exception as e:
            log.error(f"Failed to generate PDF: {e}")
            return None

    def generate_all(self, results: List[TestResult]):
        """Generates all 4 report formats."""
        log.info(f"ReportingAgent starting generation for {len(results)} results in {self.run_dir}")
        self.generate_csv(results)
        self.generate_excel(results)
        html_path = self.generate_html(results)
        self.generate_pdf(html_path)
        log.info("ReportingAgent successfully generated all formats.")
