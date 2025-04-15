#!/bin/bash

echo "Implementing Verification Engine (check_assets.py)..."

# --- scripts/check_assets.py ---
echo "Creating scripts/check_assets.py..."
cat << EOF > scripts/check_assets.py
from typing import Dict, List, Any, Optional
from pathlib import Path
import time # For potential delays in API calls

# Import necessary classes from other modules
from .bom import BoM, Component
from .inventory import Inventory, InventoryComponent
from .health_calculator import HealthCalculator
# Import base classes/interfaces for dependency injection
from .utils.api_clients import LLMClient, FootprintAPIClient
# Import concrete managers/utils
from .utils.kicad_utils import LibraryManager # Assuming KiCadProject context is handled inside or passed separately
from .utils.file_utils import DatasheetManager # Assuming KiCadProject context is handled inside or passed separately
from .utils.config_loader import AppConfig
# Potentially import renderer if LMM check is implemented
# from .render_footprint import FootprintRenderer

class VerificationReport(BaseModel):
    """Simple structure to hold verification summary."""
    components_processed: int = 0
    needs_review: int = 0
    missing_footprint: int = 0
    missing_symbol: int = 0 # Heuristic
    datasheet_missing: int = 0
    api_downloads_pending: int = 0
    llm_suggestions_made: int = 0
    errors: List[str] = []

class VerificationEngine:
    """Orchestrates the verification process for a Bill of Materials."""

    def __init__(self,
                 config: AppConfig,
                 inventory: Inventory,
                 lib_manager: LibraryManager,
                 ds_manager: DatasheetManager,
                 llm_client: LLMClient,
                 fp_client: FootprintAPIClient,
                 health_calculator: HealthCalculator,
                 # Optional: fp_renderer: FootprintRenderer = None
                 ):
        """Initialize with all necessary dependencies."""
        self.config = config
        self.inventory = inventory
        self.lib_manager = lib_manager
        self.ds_manager = ds_manager
        self.llm_client = llm_client
        self.fp_client = fp_client
        self.health_calculator = health_calculator
        # self.fp_renderer = fp_renderer
        self.project_review_dir = Path("libs/review") # Make this configurable?

    def verify_bom(self, bom: BoM, check_llm_doc: bool = False, check_lmm_fp: bool = False) -> VerificationReport:
        """
        Verifies all components in the BoM object.
        Updates component status and health scores *in place*.
        Returns a summary report.
        """
        report = VerificationReport()
        components = bom.get_all_components()
        report.components_processed = len(components)

        print(f"\n--- Starting BoM Verification ({report.components_processed} components) ---")

        for i, component in enumerate(components):
            print(f"\n[{i+1}/{report.components_processed}] Verifying: {component.ref} ({component.value})...")
            try:
                self._verify_component(component, check_llm_doc, check_lmm_fp)

                # Update report counters based on final component status
                if component.status.footprint_verified == 'review_pending':
                    report.api_downloads_pending += 1
                if not component.status.footprint_exists and not component.status.api_downloaded:
                     if not component.status.llm_suggested: # Only count as missing if no suggestion either
                          report.missing_footprint += 1
                     else:
                          report.llm_suggestions_made +=1 # Count suggestions separately

                if not component.status.symbol_exists: # Heuristic
                    report.missing_symbol += 1
                if not component.status.datasheet_local and not component.datasheet_url:
                     report.datasheet_missing += 1
                if component.health_score.score < self.config.health_rules.thresholds.needs_review_below:
                    report.needs_review += 1

            except Exception as e:
                error_msg = f"Error verifying component {component.ref}: {e}"
                print(f"  ERROR: {error_msg}")
                report.errors.append(error_msg)

        print("\n--- BoM Verification Complete ---")
        print(f"Summary: {report.model_dump()}")
        return report


    def _verify_component(self, component: Component, check_llm_doc: bool, check_lmm_fp: bool):
        """Performs all verification steps for a single component."""

        # --- Reset Status (Optional - Decide if status should persist across runs) ---
        # component.status = ComponentStatus() # Reset completely? Or update? Let's update.
        component.llm_notes = [] # Clear previous notes

        # --- 1. Inventory Check ---
        inventory_match = self.inventory.find_match(component)
        if inventory_match:
            print(f"  INFO: Found potential inventory match: {inventory_match.part_id} ({inventory_match.description})")
            component.source_info = f"Inventory Match: {inventory_match.part_id}"
            # Use inventory footprint if BoM doesn't have one specified
            if not component.footprint:
                component.footprint = inventory_match.footprint
            # Inherit verified status from inventory part's source
            if inventory_match.footprint_source in ['manual', 'kit_ingest_verified']:
                 component.status.footprint_verified = True
                 print(f"  INFO: Using verified footprint '{component.footprint}' from inventory.")
            else: # api, llm, unknown source - treat as needs verification for BoM context
                 component.status.footprint_verified = False
                 print(f"  INFO: Using footprint '{component.footprint}' from inventory (source: {inventory_match.footprint_source}), verification recommended.")
        else:
            component.source_info = component.source_info or "BoM Defined" # Keep manual source if set

        # --- 2. Datasheet Check ---
        ds_status = self.ds_manager.check_local(component) # Updates component.datasheet_local if found
        component.update_status({'datasheet_local': ds_status})
        if not ds_status and component.datasheet_url:
            print(f"  Attempting datasheet download...")
            downloaded = self.ds_manager.download(component) # Tries download, updates local path on success
            component.update_status({'datasheet_local': downloaded})
            if not downloaded:
                 print(f"  WARN: Failed to download datasheet from {component.datasheet_url}")
                 component.llm_notes.append("Datasheet download failed.")


        # --- 3. Footprint Check & Acquisition ---
        component.update_status({'footprint_exists': False, 'api_downloaded': False, 'llm_suggested': False})
        # Skip API/LLM if footprint is already set AND verified (e.g., from trusted inventory)
        skip_fp_search = component.footprint and component.status.footprint_verified is True

        if component.footprint:
            fp_exists = self.lib_manager.footprint_exists(component.footprint)
            component.update_status({'footprint_exists': fp_exists})
            if fp_exists:
                 print(f"  Footprint '{component.footprint}' found in libraries.")
                 # Don't assume verified unless from trusted inventory source checked earlier
                 if component.status.footprint_verified is None: component.status.footprint_verified = False
            else:
                 print(f"  WARN: Assigned footprint '{component.footprint}' not found!")
                 component.llm_notes.append(f"Assigned footprint '{component.footprint}' not found.")
                 component.status.footprint_verified = False # Cannot be verified if not found
                 skip_fp_search = False # Allow search if assigned one not found

        # Try API or LLM if no footprint or assigned one not found/verified
        if not skip_fp_search:
            api_searched = False
            # Try API first if MPN exists
            if component.mpn:
                api_searched = True
                print(f"  Searching Footprint API for MPN: {component.mpn}...")
                try:
                    results = self.fp_client.search_by_mpn(component.mpn)
                    if results:
                        # Find best result (e.g., first one with KiCad footprint)
                        kicad_fp_result = next((r for r in results if r.get('download_url_kicad_fp')), None)
                        if kicad_fp_result:
                             print(f"  API Found KiCad Footprint. Attempting download...")
                             # Define review path: libs/review/<MPN>/
                             review_path = self.project_review_dir / component.mpn
                             review_path.mkdir(parents=True, exist_ok=True)
                             downloaded_path = self.fp_client.download_asset(kicad_fp_result, 'footprint', str(review_path))
                             if downloaded_path:
                                  print(f"  SUCCESS: Footprint downloaded to '{downloaded_path}' for review.")
                                  component.update_status({'api_downloaded': True, 'footprint_verified': 'review_pending'})
                                  component.source_info = f"API Download Pending ({kicad_fp_result.get('manufacturer', 'N/A')})"
                                  component.llm_notes.append(f"Footprint downloaded via API, requires manual review/acceptance.")
                             else:
                                  print(f"  WARN: API download failed for footprint.")
                                  component.llm_notes.append("API footprint download failed.")
                        else:
                             print(f"  INFO: API found results, but no direct KiCad footprint download link.")
                             component.llm_notes.append("API found matches but no direct KiCad footprint download.")
                    else:
                         print(f"  INFO: MPN not found via Footprint API.")
                         component.llm_notes.append("MPN not found via Footprint API.")
                    # Add delay to avoid hammering API?
                    # time.sleep(0.5)
                except Exception as e:
                    print(f"  ERROR: Footprint API search failed: {e}")
                    component.llm_notes.append(f"Footprint API search error: {e}")

            # Try LLM suggestion if footprint still missing and package info exists
            if not component.footprint and not component.status.api_downloaded and component.package:
                 print(f"  Attempting LLM footprint suggestion for package: {component.package}...")
                 try:
                      suggestion = self.llm_client.suggest_footprint(f"{component.description} {component.package}")
                      if suggestion:
                           print(f"  LLM Suggested Footprint: '{suggestion}' (Needs Verification)")
                           component.footprint = suggestion # Assign suggestion
                           component.update_status({'llm_suggested': True, 'footprint_exists': self.lib_manager.footprint_exists(suggestion)}) # Check if suggestion exists
                           component.status.footprint_verified = False # Must be verified
                           component.source_info = "LLM Suggestion"
                           component.llm_notes.append(f"LLM suggested footprint '{suggestion}'. VERIFY MANUALLY.")
                      else:
                           print(f"  INFO: LLM did not provide a footprint suggestion.")
                           component.llm_notes.append("LLM did not suggest a footprint.")
                 except Exception as e:
                      print(f"  ERROR: LLM footprint suggestion failed: {e}")
                      component.llm_notes.append(f"LLM footprint suggestion error: {e}")


        # --- 4. Symbol Check (Heuristic) ---
        # Try to find symbol based on Value/Description - very basic
        # A better approach might involve parsing symbol libraries more deeply
        # or having a field in bom.yaml specifying the symbol explicitly.
        symbol_ref_guess = f"Device:{component.value}" # Very naive guess
        sym_exists = self.lib_manager.symbol_exists(symbol_ref_guess)
        component.update_status({'symbol_exists': sym_exists})
        if not sym_exists:
             # Try description based?
             # sym_exists = self.lib_manager.find_symbol_heuristic(component.description)
             # component.update_status({'symbol_exists': sym_exists})
             pass # Keep it simple for now
        if sym_exists:
            print(f"  Symbol found (heuristic check).")
        else:
            print(f"  WARN: Symbol likely missing (heuristic check).")
            component.llm_notes.append("Symbol likely missing or needs explicit definition.")


        # --- 5. Optional LLM/LMM Checks ---
        if check_llm_doc and component.status.datasheet_local:
             print("  Running LLM Datasheet Checks...")
             datasheet_text = self.ds_manager.extract_text(component)
             if datasheet_text:
                  try:
                       # Example specific checks
                       pin_check = self.llm_client.check_pin_count_consistency(datasheet_text, component.model_dump())
                       pkg_check = self.llm_client.check_package_match(datasheet_text, component.model_dump())
                       # Update status based on results
                       component.llm_notes.append(f"LLM Doc Pin Check: {pin_check.get('notes', 'Error')}")
                       component.llm_notes.append(f"LLM Doc Pkg Check: {pkg_check.get('notes', 'Error')}")
                       # Could update a specific status flag e.g., component.status.llm_pin_match = pin_check.get('match')
                  except Exception as e:
                       print(f"  ERROR: LLM datasheet check failed: {e}")
                       component.llm_notes.append(f"LLM datasheet check error: {e}")
             else:
                  print("  WARN: Cannot run LLM Doc check, failed to extract text.")
                  component.llm_notes.append("LLM Doc check skipped (text extraction failed).")

        # if check_lmm_fp and component.status.footprint_exists and self.fp_renderer:
             # print("  Running LMM Footprint Check (Experimental)...")
             # try:
             #      fp_path = self.lib_manager.find_footprint_path(component.footprint) # Need this helper
             #      if fp_path:
             #           img_path = self.fp_renderer.render(fp_path)
             #           if img_path:
             #                with open(img_path, 'rb') as fimg: img_data = fimg.read()
             #                datasheet_text = self.ds_manager.extract_text(component) or ""
             #                lmm_result = self.llm_client.verify_footprint_visual(img_data, datasheet_text[:1000], component.model_dump())
             #                component.llm_notes.append(f"LMM Visual Check: {lmm_result.get('notes', 'Error')}")
             #                # Update status...
             #           else: component.llm_notes.append("LMM Check skipped (render failed).")
             #      else: component.llm_notes.append("LMM Check skipped (footprint file not found).")
             # except Exception as e:
             #      print(f"  ERROR: LMM footprint check failed: {e}")
             #      component.llm_notes.append(f"LMM footprint check error: {e}")


        # --- 6. Final Health Score Calculation ---
        # Pass self.health_calculator which holds the rules
        component.calculate_health(self.health_calculator)
        print(f"  Health Score: {component.health_score.score:.1f} / {self.health_calculator.max_possible_score:.1f}")
        if component.health_score.score < self.config.health_rules.thresholds.needs_review_below:
            print(f"  ** Review Recommended **")


if __name__ == '__main__':
     print("--- Testing VerificationEngine (requires full setup) ---")
     # This class is complex to test standalone without mocking all dependencies
     # or setting up a full project context.
     # Integration testing via the Jupyter notebook is recommended.
     pass

EOF

echo ""
echo "--- Verification Engine Implementation Complete ---"
echo "Created/Updated:"
echo "  - scripts/check_assets.py"
echo ""
echo "Next steps:"
echo "1. Review the generated Python file (\`check_assets.py\`)."
echo "2. Stage and commit these changes: \`git add scripts/\` && \`git commit -m 'Implement VerificationEngine' \`"
echo "3. Implement the actual API client classes (e.g., \`openai_client.py\`, \`snapeda_client.py\`) inheriting from the bases in \`api_clients.py\`."
echo "4. Implement the \`FootprintRenderer\` if you intend to use the LMM check."
echo "5. Refine the Jupyter Notebooks (\`1_*.ipynb\`, \`2_*.ipynb\`, \`3_*.ipynb\`) to call these classes and manage the workflow."
echo "-----------------------------------------------------"