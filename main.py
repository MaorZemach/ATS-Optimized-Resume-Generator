#!/usr/bin/env python3
"""
ResumeTailor — Generate ATS-optimized, targeted resumes from a master JSON.
Usage: python main.py <job_description.txt>
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import anthropic
import markdown as md_lib
import pdfkit
from dotenv import load_dotenv

# ── Constants ──────────────────────────────────────────────────────────────────
MASTER_RESUME_PATH = Path("master_resume.json")
OUTPUT_MD_PATH = Path("tailored_resume.md")
OUTPUT_PDF_PATH = Path("tailored_resume.pdf")
MODEL = "claude-opus-4-6"

# ── PDF Stylesheet ─────────────────────────────────────────────────────────────
# Embedded directly into the HTML <style> tag so no external file is needed.
PDF_STYLESHEET = """
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: Arial, Helvetica, sans-serif;
    font-size: 10pt;
    line-height: 1.45;
    color: #1a1a1a;
}

/* Name — large, bold, centered */
h1 {
    font-size: 22pt;
    font-weight: 700;
    text-align: center;
    letter-spacing: 0.5px;
    margin-bottom: 4pt;
    color: #111111;
}

/* Contact info paragraph immediately after H1 */
h1 + p {
    text-align: center;
    font-size: 9pt;
    color: #444444;
    margin-bottom: 10pt;
}

/* Subtle section dividers */
hr {
    border: none;
    border-top: 1.2px solid #cccccc;
    margin: 8pt 0;
}

/* Section headers */
h2 {
    font-size: 11pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: #222222;
    border-bottom: 1.5px solid #222222;
    padding-bottom: 2pt;
    margin-top: 10pt;
    margin-bottom: 5pt;
}

/* Job-role headers */
h3 {
    font-size: 10.5pt;
    font-weight: 700;
    color: #1a1a1a;
    margin-top: 6pt;
    margin-bottom: 2pt;
}

p { margin-bottom: 4pt; }

/* Single-column bullet lists — ATS safe */
ul {
    margin: 2pt 0 4pt 16pt;
    padding: 0;
    list-style-type: disc;
}

li {
    margin-bottom: 2pt;
    line-height: 1.4;
}

strong { font-weight: 700; color: #111111; }
"""

# wkhtmltopdf page options
PDFKIT_OPTIONS = {
    "page-size": "A4",
    "margin-top": "1.8cm",
    "margin-right": "1.8cm",
    "margin-bottom": "1.8cm",
    "margin-left": "1.8cm",
    "encoding": "UTF-8",
    "no-outline": None,
    "quiet": "",
}

# ── Prompts ────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert technical resume writer and ATS optimization specialist.
Your task is to tailor a master resume JSON for a specific job description to maximize ATS keyword matching and recruiter impact.

You will receive:
1. A master resume in JSON format (containing arrays of summaries, experience bullets, and skill categories)
2. A job description

Your output must be a single, clean Markdown document — the final tailored resume — with NO extra commentary, NO explanations, NO preamble, and NO trailing notes.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULES — READ THESE BEFORE WRITING ANYTHING:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. NEVER INVENT CONTENT. You are STRICTLY FORBIDDEN from fabricating, hallucinating,
   or implying any skill, technology, tool, certification, or experience that does
   not appear verbatim (or as a clear synonym) in the candidate's master JSON.
   This is the most important rule. Violating it would be resume fraud.

2. MISSING SKILLS ARE SILENTLY IGNORED. If the job description requires a skill,
   technology, or tool that is NOT in the master JSON (e.g., M365, Kubernetes,
   Terraform, DHCP, PowerShell), you must NOT add it anywhere in the resume —
   not in Skills, not in bullet points, not in the Summary. Simply omit it.

3. REPHRASING IS ALLOWED — FABRICATION IS NOT. You may reword existing bullet
   points and the summary to echo the job description's tone and terminology,
   BUT only when the underlying fact already exists in the JSON. For example:
   ✓ ALLOWED: "Managed VMware VMs" → "Administered VMware virtualization infrastructure"
   ✗ FORBIDDEN: Adding "Managed Hyper-V clusters" if Hyper-V is not in the JSON.

4. SKILLS SECTION: Only list skills that exist in the JSON's "skills" object.
   You may reorganize them into different category labels if that better matches
   the JD, but every individual skill item must trace back to the original JSON.

5. KEYWORD COMMENT: In the ATS_KEYWORDS comment at the bottom, only list keywords
   that appear in BOTH the job description AND the candidate's master JSON.
   Do not list JD keywords that the candidate does not actually possess.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Follow this exact Markdown structure:

# [Candidate Full Name]
[website] | [linkedin] | [email] | [phone]

---

## Summary
[The single best-matching summary, lightly edited to mirror job description language —
 only using technologies and terms already present in the JSON]

---

## Experience

### [Role] — [Company] | [Dates]
- [Only the bullet points most relevant to this job]
- [Omit any bullets that don't relate to the job requirements]
- [You may lightly reword bullets to incorporate exact keywords from the JD without changing the facts]

---

## Skills
- **[Category Name]:** skill1, skill2, skill3
- **[Category Name]:** skill4, skill5
[Only include skills from the JSON that are relevant to the job. Remove irrelevant categories entirely. Each category MUST be its own bullet point.]

---

## Education
**[Degree]** — [Institution] ([Dates])

---

## Certifications
- [Name] — [Issuer] ([Date])
[Omit certifications not relevant to the role]

---

## Projects

**[Project Name]**
[Description — only include if relevant to the JD]

**[Project Name]**
[Description — only include if relevant to the JD]

---

<!-- ATS_KEYWORDS: keyword1, keyword2, keyword3, ... -->
[Keywords that appear in BOTH the JD and the candidate's JSON — never JD-only keywords]
"""

TAILOR_PROMPT_TEMPLATE = """Here is the candidate's master resume in JSON format:

```json
{resume_json}
```

Here is the job description to target:

---
{job_description}
---

Now produce the tailored resume Markdown as instructed. Select ONLY the most relevant content. The goal is a tight, impactful resume that beats ATS systems for this specific role."""


# ── Loaders ────────────────────────────────────────────────────────────────────

def load_master_resume() -> dict:
    """Load and validate the master resume JSON file."""
    if not MASTER_RESUME_PATH.exists():
        print(f"[ERROR] '{MASTER_RESUME_PATH}' not found in the current directory.")
        print("        Please create it with keys: contact_info, summary, experience,")
        print("        education, certifications, projects, skills.")
        sys.exit(1)

    try:
        with open(MASTER_RESUME_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse '{MASTER_RESUME_PATH}': {e}")
        sys.exit(1)


def load_job_description(path: str) -> str:
    """Load the job description from a text file."""
    jd_path = Path(path)
    if not jd_path.exists():
        print(f"[ERROR] Job description file '{jd_path}' not found.")
        sys.exit(1)

    content = jd_path.read_text(encoding="utf-8").strip()
    if not content:
        print(f"[ERROR] Job description file '{jd_path}' is empty.")
        sys.exit(1)

    return content


# ── Core: Claude API call ──────────────────────────────────────────────────────

def tailor_resume(resume: dict, job_description: str) -> str:
    """
    Call Claude API with streaming + adaptive thinking to generate
    a tailored resume Markdown document.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or not api_key.startswith("sk-ant"):
        print("[ERROR] ANTHROPIC_API_KEY is missing or formatted incorrectly.")
        print("        Check that your .env file exists next to main.py and contains:")
        print("          ANTHROPIC_API_KEY=sk-ant-...")
        print("        Make sure there are no quotes, spaces, or extra characters.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    resume_json = json.dumps(resume, ensure_ascii=False, indent=2)
    user_message = TAILOR_PROMPT_TEMPLATE.format(
        resume_json=resume_json,
        job_description=job_description,
    )

    print("[*] Sending to Claude (streaming with adaptive thinking)...")
    print("[*] Generating tailored resume — this may take 15–30 seconds...\n")

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            collected_text = []

            with client.messages.stream(
                model=MODEL,
                max_tokens=4096,
                thinking={"type": "adaptive"},
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                for event in stream:
                    if (
                        event.type == "content_block_delta"
                        and hasattr(event.delta, "type")
                        and event.delta.type == "text_delta"
                    ):
                        print(event.delta.text, end="", flush=True)
                        collected_text.append(event.delta.text)

                final = stream.get_final_message()
            break  # success — exit retry loop
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < max_retries:
                print(f"\n[WARNING] API is overloaded, waiting 5 seconds before retrying... (attempt {attempt}/{max_retries})")
                time.sleep(5)
            else:
                raise

    # Prefer the verified full text from the final message object
    full_text = ""
    for block in final.content:
        if block.type == "text":
            full_text = block.text
            break

    if not full_text:
        full_text = "".join(collected_text)

    return full_text.strip()


# ── Output: Markdown + PDF ─────────────────────────────────────────────────────

def save_markdown(markdown: str) -> None:
    """Save the tailored resume Markdown to disk."""
    OUTPUT_MD_PATH.write_text(markdown, encoding="utf-8")
    print(f"\n\n[✓] Markdown saved  → {OUTPUT_MD_PATH.resolve()}")


def _get_pdfkit_config() -> "pdfkit.configuration | None":
    """
    Return a pdfkit Configuration pointing to wkhtmltopdf.

    Search order:
    1. Default Windows installer path  (C:\\Program Files\\wkhtmltopdf\\bin\\...)
    2. System PATH — pdfkit finds it automatically (return None)
    """
    windows_default = Path(r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe")
    if sys.platform == "win32" and windows_default.exists():
        return pdfkit.configuration(wkhtmltopdf=str(windows_default))
    return None  # rely on PATH


def markdown_to_pdf(markdown: str) -> None:
    """
    Convert Markdown → styled HTML → PDF via pdfkit / wkhtmltopdf.

    Steps:
    1. Strip the ATS_KEYWORDS HTML comment (metadata only, not for PDF).
    2. Convert Markdown to an HTML fragment using the `markdown` library.
    3. Wrap in a full HTML document with the CSS embedded in <style>.
    4. Pass the HTML string to pdfkit, which renders it with wkhtmltopdf.
    """
    # Strip ATS metadata comment — it lives only in the .md file
    clean_md = re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL).strip()

    # Markdown → HTML body fragment
    html_body = md_lib.markdown(clean_md, extensions=["extra", "sane_lists"])

    # Full self-contained HTML document with embedded stylesheet
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Tailored Resume</title>
  <style>{PDF_STYLESHEET}</style>
</head>
<body>
{html_body}
</body>
</html>"""

    config = _get_pdfkit_config()
    pdfkit.from_string(
        full_html,
        str(OUTPUT_PDF_PATH),
        options=PDFKIT_OPTIONS,
        configuration=config,  # None → pdfkit searches PATH automatically
    )

    print(f"[✓] PDF saved       → {OUTPUT_PDF_PATH.resolve()}")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    # Load .env from the same directory as this script, regardless of cwd
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")

    parser = argparse.ArgumentParser(
        description="ResumeTailor — Generate an ATS-optimized resume for a specific job.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py job_desc.txt
  python main.py "path/to/Senior DevOps Engineer.txt"

Setup:
  1. Create a .env file in this directory:
       ANTHROPIC_API_KEY=sk-ant-...
  2. Ensure master_resume.json exists in this directory.
  3. Run: python main.py <your_job_description.txt>
        """,
    )
    parser.add_argument(
        "job_description",
        metavar="JOB_DESCRIPTION_FILE",
        help="Path to a .txt file containing the job description",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  ResumeTailor — ATS-Optimized Resume Generator")
    print("=" * 60)

    resume = load_master_resume()
    job_description = load_job_description(args.job_description)

    candidate_name = resume.get("contact_info", {}).get("name", "Candidate")
    print(f"[*] Master resume loaded for: {candidate_name}")
    print(f"[*] Job description loaded ({len(job_description)} characters)")

    # Step 1: Generate Markdown via Claude
    tailored_markdown = tailor_resume(resume, job_description)

    # Step 2: Save Markdown
    save_markdown(tailored_markdown)

    # Step 3: Convert to PDF
    print("[*] Converting to PDF...")
    try:
        markdown_to_pdf(tailored_markdown)
    except Exception as e:
        print(f"[WARNING] PDF generation failed: {e}")
        print("          The Markdown file is still intact.")

    print(f"\n[*] Model used: {MODEL}")
    print("=" * 60)
    print("  Done! Output files:")
    print(f"    • tailored_resume.md  (raw Markdown)")
    print(f"    • tailored_resume.pdf (print-ready PDF)")
    print("=" * 60)


if __name__ == "__main__":
    main()
