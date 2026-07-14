"""
Master Entry Point.
Loads requirements and initializes the OrchestratorAgent.
"""
import os
import csv
from typing import List
from models.schemas import Requirement
from agents.orchestrator import OrchestratorAgent
from utils.logger import log

def load_requirements(csv_path: str) -> List[Requirement]:
    reqs = []
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            reqs.append(Requirement(
                id=row.get('ID', ''),
                module=row.get('Module', 'General'),
                feature=row.get('Feature', 'Unknown'),
                description=row.get('Requirement', row.get('Description', '')), # support old 'Description' column
                preconditions=[p.strip() for p in row.get('Preconditions', '').split('\n') if p.strip()],
                test_data=row.get('Test Data', ''),
                expected_result=row.get('Expected Result', ''),
                priority=row.get('Priority', 'Medium'),
                confidence=float(row.get('Confidence', 1.0)) if row.get('Confidence') else 1.0,
                business_rules=[row.get('Rules', '')]
            ))
    return reqs

def main():
    csv_path = "requirements.csv"
    if not os.path.exists(csv_path):
        log.error(f"{csv_path} not found. Please create one with columns: ID, Module, Description, Rules.")
        return
        
    requirements = load_requirements(csv_path)
    if not requirements:
        log.warning("No requirements found in CSV.")
        return

    log.info("Starting Master Orchestrator Pipeline")
    
    # Initialize the Orchestrator and run the pipeline
    orchestrator = OrchestratorAgent()
    orchestrator.run(requirements)

if __name__ == "__main__":
    main()
