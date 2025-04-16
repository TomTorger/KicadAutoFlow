# KicadAutoFlow (ADK Based)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
<!-- Add other badges if desired: build status, code coverage, etc. -->

A **Jupyter Notebook-driven framework powered by Google's Agent Development Kit (ADK)** designed to assist and streamline your KiCad project workflow. It emphasizes **inventory management, automated component verification, structured review, and optional AI assistance**, bridging the gap between your parts bin and a layout-ready KiCad project.

## Core Philosophy: Semi-Automation & User Control

This framework automates tedious tasks but relies on **your expertise for critical verification and design**.
*   **Automation:** Handles searching libraries/APIs for assets (symbols, footprints, datasheets), downloading files, performing initial consistency checks (using `kiutils` and optional AI), calculating health scores, and generating reports.
*   **User Control:** You make the final design decisions, **critically review and verify all footprints** (especially those from external sources), manage your inventory accuracy, create the schematic logic, and perform the PCB layout.
*   **AI as Assistant:** LLM/LMM features are aids for suggestion and basic checks, not infallible oracles. Always apply engineering judgment.

## Key Features

*   **Inventory-Aware Design:** Manage local parts in `inventory.yaml`, including image-assisted ingestion. Workflow prioritizes using these verified parts.
*   **Modular ADK Backend:** Logic organized into reusable ADK **Agents** (orchestrators like `VerificationAgent`), **Tools** (atomic actions like `CheckLibraryAssetTool`, `DownloadDatasheetTool`), and **Capabilities** (standardized interfaces to external services like `LLMCapability`, `FootprintAPICapability`).
*   **Comprehensive Asset Checking:** Verifies datasheets, symbols (via `kiutils`), and footprints (via `kiutils`) against project libraries, KiCad standard libraries, and external APIs (e.g., SnapEDA capability). Downloads assets to `libs/review/`.
*   **Component Health Score:** Quantifies the verification status (datasheet presence/validity, footprint existence/parsing/verification, symbol definition found, MPN presence) guiding review focus.
*   **Optional LLM/LMM Assistance:** Integrates AI for suggesting components/footprints, analyzing images for inventory, and experimental datasheet/footprint consistency checks.
*   **Structured Jupyter Workflow:** Manages the process via distinct notebooks: `1_Inventory_Management.ipynb`, `2_Project_Design_Exploration.ipynb`, `3_Project_Verification_and_Handoff.ipynb`.
*   **Actionable Markdown Documentation:** Generates `docs/Component_Review.md` per project, summarizing component data, verification results, health scores, images, and a checklist for required manual review actions.
*   **Reusable Blocks:** Supports using pre-verified hierarchical sheets stored in `libs/blocks/`.
*   **Offline Testing Framework:** Includes `pytest` structure for testing core logic without live API calls.

## Prerequisites

*   **Python:** 3.9+ Recommended (due to ADK/modern library dependencies)
*   **KiCad:** 7.0+ (Standard libraries installed, paths set in `config.yaml`).
*   **Git:** For version control.
*   **JupyterLab:** Recommended interface (`pip install jupyterlab`).
*   **Python Dependencies:** Install via `pip install -r requirements.txt`. Key deps: `google-adk`, `PyYAML`, `requests`, `pandas`, `ipywidgets`, `Pillow`, `PyPDF2`, `kiutils`, `pydantic`, `pytest`, `pytest-mock`.
*   **(Optional) API Keys:** For external services used by capabilities (e.g., Google AI for Gemini, SnapEDA). Add to `config.yaml`.
*   **(Optional) Footprint Renderer:** An external tool (like `pcbdraw` or potentially `kicad-cli` export) configured in `utils/render_footprint_util.py` is needed for LMM visual checks.

## Quick Start

1.  **Clone & Setup:**
    ```bash
    git clone <repo_url> KicadAutoFlow
    cd KicadAutoFlow
    cp config.yaml.template config.yaml
    # EDIT config.yaml: Set KiCad paths, add API keys (optional)
    python -m venv venv
    source venv/bin/activate  # Or .\venv\Scripts\activate on Windows
    pip install -r requirements.txt
    jupyter lab
    ```
2.  **Inventory:** Open `1_Inventory_Management.ipynb`. Add a few common parts you have (e.g., resistors, caps), **ensuring you provide the correct, existing KiCad footprint**. Try the image ingestor.
3.  **Design Exploration:** Open `2_Project_Design_Exploration.ipynb`. Define a simple goal (e.g., "Blink an LED with ESP32"). Let the LLM suggest parts (it should prioritize your inventory). Generate the initial `MyExampleKiCadProject/bom.yaml`.
4.  **KiCad Schematic:** Open `MyExampleKiCadProject/` in KiCad. Create a simple schematic based on the generated BoM. Add power flags. Annotate, ERC check, Save. **Export BoM** (CSV or XML) to the project folder (e.g., `MyExampleKiCadProject/MyExampleKiCadProject-bom.csv`).
5.  **Verification:** Open `3_Project_Verification_and_Handoff.ipynb`. Update the `KICAD_BOM_EXPORT_FILENAME`. Run the cells to load the BoM, run verification, review health scores, generate the Markdown report, and prep data for KiCad fields.
6.  **Review:** Open `docs/Component_Review.md`. Check the details and action items.
7.  **(Optional) KiCad Fields:** Go back to Eeschema, use `Tools -> Edit Symbol Fields` and paste the generated data.

## Setup Instructions

*(Detailed steps - same as Iteration 2)*

## Workflow Overview

*(Detailed multi-notebook steps - same as Iteration 2, emphasizing KiCad export/import)*

## Project Structure Explained

*   **`adk_agents/`:** Contains ADK Agent classes orchestrating workflows (e.g., `VerificationAgent`).
*   **`adk_tools/`:** Contains ADK Tool classes/functions performing specific actions (e.g., `CheckLibraryAssetTool`, `DownloadDatasheetTool`). These are called by Agents.
*   **`adk_capabilities/`:** Python classes providing standardized interfaces to external services (e.g., `LLMCapability`, `FootprintAPICapability`). Used by Tools.
*   **`data_models/`:** Pydantic classes defining core data structures (`Component`, `InventoryItem`, `HealthScore`, etc.).
*   **`utils/`:** Shared Python helper functions/classes not specific to ADK structure (Config loading, KiCad file parsing (`kiutils`), file downloading, health calculation logic).
*   **`libs/`:** Project-level KiCad assets managed by Git:
    *   `symbols.kicad_sym`: Custom/verified symbols.
    *   `footprints.pretty/`: Custom/verified footprints.
    *   `blocks/`: Reusable `.kicad_sch` files.
    *   `review/`: **(Gitignored Content)** Temporary holding for API-downloaded assets awaiting user verification.
*   **`docs/`:** **(Gitignored Content)** Generated output (`Component_Review.md`), downloaded datasheets, inventory images, rendered footprints.
*   **`*.ipynb`:** Jupyter Notebooks providing the user interface to the workflow.
*   **`<project_name>/`:** Folder for your specific KiCad project (`.kicad_pro`, `.kicad_sch`, `.kicad_pcb`) and its **canonical `bom.yaml`** (updated by Notebook 3).
*   `inventory.yaml`: **(Tracked)** The central database of your physical component inventory. Accuracy is key.
*   `config.yaml`: **(Gitignored)** Your local configuration (API keys, paths).
*   `tests/`: Offline tests using `pytest` and `pytest-mock`.

## Important Considerations

*(Warnings - same as Iteration 2, reinforcing verification)*

## Contributing (Optional)

*(Placeholder for contribution guidelines)*

## License

MIT License (Copyright [Year] [Your Name/Organization])