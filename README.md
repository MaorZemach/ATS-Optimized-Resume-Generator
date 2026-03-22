# 🚀 ATS-Optimized Resume Generator

A practical Python-based tool designed to streamline the job application process by automatically tailoring resumes to specific job descriptions. This project focuses on professional accuracy, secure data management, and efficient document formatting.

## 💡 The Problem
In today's competitive job market, many qualified candidates are filtered out by Applicant Tracking Systems (ATS) simply because their resumes lack the specific terminology found in the job description. Manually editing a resume for every application is a repetitive, time-consuming task.

## ✨ What This Tool Does
This CLI (Command Line Interface) tool automates the "tailoring" process to ensure your profile stands out:
* **Contextual Alignment**: It analyzes job descriptions to highlight and prioritize the most relevant aspects of your professional background.
* **Hallucination Prevention**: Built with strict constraints to ensure the AI remains 100% faithful to your master profile—it never fabricates skills or experiences.
* **Professional Formatting**: Generates clean, single-column PDF layouts that are optimized for both human recruiters and automated scanning systems.
* **Security Focused**: Implements environment-based secret management (`.env`) to keep API credentials secure and private.

## 🛠️ Technical Highlights
* **AI Engine**: Powered by the **Anthropic Claude API** for advanced natural language processing and contextual understanding.
* **Modern Workflow**: Developed using an **AI-augmented development workflow (Claude Code)**, combining human architectural oversight with AI-assisted implementation.
* **Infrastructure**: Built with Python 3.12, utilizing `pdfkit` and `wkhtmltopdf` for high-fidelity document generation.

## 🚀 Quick Start
1.  **Clone the Repository**: 
    ```bash
    git clone [https://github.com/MaorZemach/ATS-Optimized-Resume-Generator.git](https://github.com/MaorZemach/ATS-Optimized-Resume-Generator.git)
    ```
2.  **Install Dependencies**: 
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure**: Add your `ANTHROPIC_API_KEY` to a `.env` file in the root directory.
4.  **Run**: 
    ```bash
    python main.py <your_job_description.txt>
    ```
