#!/bin/bash

# --- Assume we are already in the root of the initialized Git repo ---

# Define a placeholder name for the example KiCad project folder
# You might want to rename this later based on your actual first project
PROJECT_EXAMPLE_NAME="MyExampleKiCadProject"

echo "Setting up KiCad Design Assistant structure in current directory (.)"

# --- Create Basic Root Files ---
echo "Creating basic files in root..."

# .gitignore
echo "Creating .gitignore..."
cat << EOF > .gitignore
# KiCad backup files
*.kicad_sch-bak
*.kicad_pcb-bak
*.kicad_pro-bak
*-bak.*
*.bak

# KiCad cache and layout settings
fp-info-cache
*.kicad_prl

# Python cache and virtual environment
__pycache__/
*.pyc
*.pyo
venv/
*.venv/
env/
*.env/

# Jupyter Notebook checkpoints
.ipynb_checkpoints/

# User configuration (contains secrets!)
config.yaml

# Generated/Downloaded Documentation & Images (often large/binary)
docs/datasheets/
docs/inventory_images/
docs/generated_images/
docs/Component_Review.md # Optional: track if desired, ignore if strictly generated

# Temporary review libraries (content should be manually moved)
libs/review/*
!libs/review/.gitkeep # Keep the directory tracked

# Build and output files
output/
gerbers/
dist/
build/

# OS specific files
.DS_Store
Thumbs.db
EOF

# README.md
echo "Creating README.md..."
echo "# KiCad Design Assistant Template" > README.md
echo "" >> README.md
echo "A template repository for managing KiCad projects with inventory awareness and automation assistance." >> README.md
echo "" >> README.md
echo "## Setup" >> README.md
echo "" >> README.md
echo "1. Create \`config.yaml\` from \`config.yaml.template\` and add your API keys/paths." >> README.md
echo "2. Setup a Python virtual environment: \`python -m venv venv\`" >> README.md
echo "3. Activate the environment: \`source venv/bin/activate\` (Linux/macOS) or \`.\venv\Scripts\activate\` (Windows Git Bash/PowerShell)" >> README.md
echo "4. Install dependencies: \`pip install -r requirements.txt\`" >> README.md
echo "5. Start Jupyter Lab: \`jupyter lab\`" >> README.md

# config.yaml.template
echo "Creating config.yaml.template..."
cat << EOF > config.yaml.template
# Template for Configuration - COPY TO config.yaml AND FILL IN (config.yaml is gitignored)

# API Keys (Keep secret!)
api_keys:
  openai: "YOUR_OPENAI_API_KEY"
  google_ai: "YOUR_GOOGLE_AI_API_KEY"
  snapeda: "YOUR_SNAPEDA_API_KEY_IF_ANY"
  # Add other API keys as needed

# File Paths (Relative to project root or absolute)
# Example: Adjust based on your KiCad installation if needed
kicad_paths:
  standard_symbol_libs:
    - "/usr/share/kicad/symbols" # Linux example
    # - "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols" # macOS example
    # - "C:/Program Files/KiCad/7.0/share/kicad/symbols" # Windows example
  standard_footprint_libs:
    - "/usr/share/kicad/footprints" # Linux example
    # - "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints" # macOS example
    # - "C:/Program Files/KiCad/7.0/share/kicad/footprints" # Windows example

# Health Score Rules (Example - Adjust weights as desired)
health_rules:
  points:
    datasheet_local: 1.0
    datasheet_url: 0.5
    footprint_project_manual: 2.0    # Manually verified in project lib
    footprint_project_apiverified: 1.8 # API downloaded & user accepted
    footprint_project_inventory: 1.5  # From inventory, manually verified there
    footprint_kicad_lib: 1.0          # Standard KiCad lib
    footprint_inventory_api: 0.8      # From inventory, originally API sourced
    footprint_inventory_llm: 0.3      # From inventory, originally LLM suggested
    footprint_bom_apireview: 0.2      # API download pending review
    footprint_bom_llmsuggest: 0.1     # LLM suggested, needs verification
    symbol_project_lib: 1.0           # Found in project symbol lib
    symbol_kicad_lib: 0.5             # Found in standard KiCad lib (heuristic)
    mpn_exists: 0.5
    # llm_doc_check_ok: 0.5             # Optional experimental checks
    # lmm_footprint_check_ok: 0.5

  thresholds:
    needs_review_below: 4.0 # Example threshold

# LLM Configuration
llm_settings:
  default_provider: "openai" # or "google_ai"
  default_text_model: "gpt-4"
  default_vision_model: "gpt-4-vision-preview"
  # Add model-specific settings if needed

# Other settings
defaults:
  quantity_per_kit_value: 10
EOF

# inventory.yaml
echo "Creating inventory.yaml..."
echo "inventory_parts:" > inventory.yaml
echo "# Add your inventory items here" >> inventory.yaml
echo "# Example:" >> inventory.yaml
echo "#  - part_id: INV001" >> inventory.yaml
echo "#    description: '10k Resistor, 1/4W, 5%'" >> inventory.yaml
echo "#    value: 10k" >> inventory.yaml
echo "#    package: 0805" >> inventory.yaml
echo "#    footprint: Resistor_SMD:R_0805_2012Metric # Verified Footprint!" >> inventory.yaml
echo "#    footprint_source: manual # Options: manual, api, llm, kit_ingest_verified" >> inventory.yaml
echo "#    mpn: RC0805JR-0710KL" >> inventory.yaml
echo "#    quantity: 50" >> inventory.yaml
echo "#    datasheet_local: null" >> inventory.yaml
echo "#    storage_location: 'Bin X1'" >> inventory.yaml
echo "#    image_path: null " >> inventory.yaml

# requirements.txt
echo "Creating requirements.txt..."
cat << EOF > requirements.txt
# Core
PyYAML
requests
pandas
jupyterlab
ipywidgets
Pillow # For image handling
PyPDF2 # For PDF text extraction

# Optional LLM/API Clients (Install specific ones needed)
# openai
# google-cloud-aiplatform

# Optional KiCad Parsing (Requires careful consideration)
# kicad-python # or other parsers like sexpdata

# Other utilities
pathspec # For gitignore style matching if needed
pydantic # For config/data validation
EOF

# --- Create Directories ---
echo "Creating directories..."
mkdir -p docs/datasheets
mkdir -p docs/inventory_images
mkdir -p docs/generated_images/footprints
mkdir -p libs/footprints.pretty
mkdir -p libs/review
mkdir -p scripts/utils
mkdir -p "$PROJECT_EXAMPLE_NAME"

# --- Create Placeholder Files ---
echo "Creating placeholder files..."

# .gitkeep files
touch docs/datasheets/.gitkeep
touch docs/inventory_images/.gitkeep
touch docs/generated_images/footprints/.gitkeep
touch libs/footprints.pretty/.gitkeep
touch libs/review/.gitkeep

# Lib files
touch libs/symbols.kicad_sym

# Script files
touch scripts/utils/__init__.py
touch scripts/utils/api_clients.py
touch scripts/utils/config_loader.py
touch scripts/utils/file_utils.py
touch scripts/utils/kicad_utils.py
touch scripts/bom.py
touch scripts/health_calculator.py
touch scripts/inventory.py
touch scripts/check_assets.py
touch scripts/ingest_inventory.py
touch scripts/populate_kicad_fields.py
touch scripts/render_footprint.py
touch scripts/doc_generator.py
# touch scripts/schematic_checker.py # Optional

# Notebook files
touch 1_Inventory_Management.ipynb
touch 2_Project_Design_Exploration.ipynb
touch 3_Project_Verification_and_Handoff.ipynb

# Example Project Placeholders
touch "$PROJECT_EXAMPLE_NAME/$PROJECT_EXAMPLE_NAME.kicad_pro"
touch "$PROJECT_EXAMPLE_NAME/bom.yaml" # Project-specific BoM will live here
touch "$PROJECT_EXAMPLE_NAME/sym-lib-table"
touch "$PROJECT_EXAMPLE_NAME/fp-lib-table"


echo ""
echo "--- Structure Created in Current Directory ---"
echo "Next steps:"
echo "1. Stage and commit these files: \`git add .\` && \`git commit -m 'Initial structure setup' \`"
echo "2. Create \`config.yaml\` from the template and add your API keys/paths."
echo "3. Set up Python virtual environment and install requirements: \`python -m venv venv && source venv/bin/activate && pip install -r requirements.txt\`"
echo "4. Start populating \`inventory.yaml\` or begin designing in JupyterLab!"
echo "--------------------------------------------"