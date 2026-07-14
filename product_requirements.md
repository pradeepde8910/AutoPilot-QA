# Generic Autonomous Web QA Agent - Product Requirements

## Core Principle
A generic agent that tests web applications by understanding natural-language requirements instead of relying on hardcoded scripts. It decides *how* to accomplish tasks dynamically.

## High-Level Architecture
- **User Input**: Website URL + Requirements (e.g., CSV format).
- **Planner Agent**: Understands what needs testing.
- **Navigation Agent**: Explores the website automatically.
- **Observation Agent**: Captures DOM, Accessibility, Vision, OCR.
- **Verification Agent**: Compares observations to requirements.
- **Evidence Agent**: Collects Screenshots, Logs, HTML, Network data.
- **Report Agent**: Generates CSV, Excel, PDF, or HTML Dashboard.

## Types of Checks
1. **UI Validation**: Presence of buttons, text, images, logos, forms.
2. **Functional Testing**: End-to-end flows (e.g., Search functionality).
3. **Navigation Testing**: Page loading and heading verification.
4. **Accessibility**: Alt text, ARIA roles, color contrast, keyboard navigation.
5. **Performance**: Load time, LCP, CLS, TTI.
6. **Security Checks (Basic)**: HTTPS, security headers, mixed content.
7. **Visual Validation**: Screenshot comparison for layout shifts.
8. **Responsive Testing**: Desktop, Tablet, Mobile verification.

## Target Output
Comprehensive report including:
- Test status (PASS/FAIL)
- Confidence score
- Screenshots
- Notes and metrics
- Executive summary

## Constraints & Technology
- Must utilize **Groq LLM** for fast reasoning and decision making.
