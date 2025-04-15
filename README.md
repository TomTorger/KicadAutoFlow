# KicadAutoFlow

**(Formerly KicadDesignAssistant)**

A **Jupyter Notebook-driven framework** designed to assist and streamline your KiCad project workflow. It emphasizes **inventory management, automated component verification, structured review, and optional AI assistance**, bridging the gap between your parts bin and a layout-ready KiCad project.

## Core Philosophy

This framework embraces **semi-automation**. It automates tedious data gathering (datasheets, initial footprint/symbol searches) and analysis (health scores, basic checks) but fundamentally relies on **your expertise and verification** for critical design decisions, final asset validation (especially footprints!), and the creative processes of schematic capture and PCB layout. Treat all automated outputs (API results, LLM suggestions) as *aids requiring confirmation*, not infallible truth.

## Key Features

*   **Inventory-Aware Design:** Manage local component stock (`inventory.yaml`) with image-assisted ingestion and prioritize using available parts.
*   **Reusable Schematic Blocks:** Define and reuse common circuit blocks (`libs/blocks/`) via KiCad's hierarchy.
*   **Automated Asset Checking:** Verifies datasheets, symbols, and footprints against project/KiCad libraries and external APIs (e.g., SnapEDA), downloading assets to a review queue.
*   **Component Health Score:** Provides a quantifiable measure of each BoM component's verification status, guiding review efforts.
*   **LLM/LMM Assistance (Experimental):** Optional AI features for:
    *   Suggesting circuit blocks, inventory parts, standard footprints.
    *   Assisting inventory ingestion via image analysis (OCR/LMM).
    *   Performing basic datasheet consistency checks.
    *   *Requires careful configuration, prompt engineering, and critical evaluation of results.*
*   **Structured Jupyter Workflow:** Guides the process through distinct phases via dedicated notebooks (Inventory, Design Exploration, Verification/Handoff).
*   **Comprehensive Markdown Documentation:** Generates a `Component_Review.md` file per project, summarizing component details, verification results, images, health scores, and providing an actionable checklist for manual review.

## Prerequisites

*   **Python:** 3.8+ (with `pip` and `venv`)
*   **KiCad:** 7.0+ (Standard libraries should be installed and paths correctly set in `config.yaml`).
*   **Git:** For version control of the template and your projects.
*   **JupyterLab/Notebook:** The primary user interface (`pip install jupyterlab`).
*   **(Optional but Recommended) API Keys:** For services you wish to use (e.g., OpenAI/Google AI for LLM features, SnapEDA for footprint downloads).

## Quick Start

1.  Clone repo, `cd KicadAutoFlow`.
2.  Copy `config.yaml.template` -> `config.yaml`. **Edit `config.yaml`** to set KiCad paths (if non-standard) and any API keys you have.
3.  `python -m venv venv`
4.  `source venv/bin/activate` (or `.\venv\Scripts\activate` on Windows)
5.  `pip install -r requirements.txt`
6.  `jupyter lab`
7.  Open `1_Inventory_Management.ipynb` and explore/add some parts (try the image ingestor!).
8.  Open `2_Project_Design_Exploration.ipynb`, define a simple goal, and generate an initial `bom.yaml` for the example project.
9.  *Proceed to KiCad to create a basic schematic based on the BoM.*
10. *Export BoM from KiCad.*
11. Open `3_Project_Verification_and_Handoff.ipynb`, load the exported BoM, and run the verification loop. Explore the reports and generated documentation.

## Setup Instructions

*(Detailed steps, same as Iteration 2 - included for completeness)*

1.  **Clone/Copy:** Get a copy of this template repository.
2.  **Initialize Git:** `git init` (if starting fresh).
3.  **Configuration:**
    *   Copy `config.yaml.template` to `config.yaml`.
    *   **Edit `config.yaml`:** Add your **API keys** (this file is gitignored - keep secrets safe!). Adjust KiCad standard library paths if needed. Review health score rules & LLM settings.
4.  **Python Environment:**
    *   Create: `python -m venv venv`
    *   Activate: `source venv/bin/activate` (Linux/macOS) or `.\venv\Scripts\activate` (Windows Git Bash/PowerShell)
5.  **Install Dependencies:** `pip install -r requirements.txt`
6.  **Start Jupyter:** `jupyter lab` (or `jupyter notebook`) in the repository root.

## Workflow Overview

*(Detailed steps, same as Iteration 2 - included for completeness)*

1.  **`1_Inventory_Management.ipynb` (Ongoing):** Manage `inventory.yaml`. Add parts via image/manual entry. **Crucially verify footprints during ingestion.**
2.  **`2_Project_Design_Exploration.ipynb` (Project Start):** Define goal, review inventory/blocks, use LLM assist, generate initial project `bom.yaml`.
3.  **Manual KiCad Schematic Design:** Create hierarchical schematic in **Eeschema**. Use library blocks & BoM components. Assign footprints, wire, ERC, annotate. **Export BoM** (CSV/XML).
4.  **`3_Project_Verification_and_Handoff.ipynb` (Post-Schematic):** Load KiCad BoM. Run **Verification Loop** (Checks, Scores, API Downloads, Optional LLM checks). **Interactively accept reviewed assets**. Resolve missing/low-score items. Save canonical project `bom.yaml`. Generate `Component_Review.md`. Perform **focused manual review** using Markdown doc. Generate final pre-layout data.
5.  **Manual KiCad PCB Layout:** Open **Pcbnew**, update from schematic, place, route, DRC.

## Key Files & Directories

*(Detailed structure, same as Iteration 2 - included for completeness)*

*   `config.yaml`: **(Untracked)** User secrets, paths, settings.
*   `inventory.yaml`: **(Tracked)** User component inventory database.
*   `requirements.txt`: Python dependencies.
*   `scripts/`: Backend Python logic (OO structure).
*   `libs/`: Project KiCad libs (symbols, footprints, blocks, review queue).
*   `docs/`: Generated docs (Component Review MD), downloaded datasheets.
*   `*.ipynb`: Jupyter Notebook workflow interface.
*   `<project_name>/`: KiCad project files + canonical `bom.yaml`.

## Important Considerations

*   **API Client Implementation:** You **must** implement the actual API interaction logic in the placeholder files within `scripts/utils/` (e.g., `openai_client.py`, `snapeda_client.py`) for those features to work.
*   **Footprint Renderer:** LMM visual checks require a functioning `scripts/render_footprint.py`. This is complex and may need external tools. Treat LMM results as highly experimental.
*   **Verification is CRITICAL:** Automation assists, but **you** are responsible for validating downloaded assets (especially footprints), reviewing LLM outputs, and ensuring the final design correctness before layout and fabrication. Use the Health Scores and `Component_Review.md` to guide this process.
*   **LLM Limitations:** Understand that LLMs can hallucinate or misinterpret technical data. Double-check their suggestions and verification results.

## Contributing (Optional)

*(Add guidelines if you want others to contribute)*
We welcome contributions! Please follow standard Fork & Pull Request workflows. Ensure code includes docstrings and ideally unit tests for new functionality.

## License

MIT License (Copyright [Year] [Your Name/Organization])