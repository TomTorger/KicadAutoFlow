from typing import Dict, List, Any, Optional

# Assuming component_base.py is accessible
from component_base import Component, HealthScore
# Assuming config_loader loads the AppConfig model correctly
# from scripts.utils.config_loader import AppConfig, HealthRules

class HealthCalculator:
    """Calculates a 'health score' for a component based on verification status."""

    def __init__(self, health_rules):
        """Initialize with health scoring rules from the config."""
        self.rules = health_rules
        self.max_possible_score = self._calculate_max_score()
        print(f"HealthCalculator initialized. Max possible score: {self.max_possible_score}")

    def _calculate_max_score(self) -> float:
        """Calculate the maximum possible score based on defined positive rules."""
        # This assumes points are assigned for achieving a 'good' state
        max_score = 0.0
        # Iterate through the points defined in the config's HealthPoints model
        # Using default values if not explicitly set in config for broader compatibility
        points_model = self.rules.points
        for field_name, default_value in points_model.model_fields.items():
            # Only sum positive point contributions for the max score baseline
            # Consider the most positive outcome for boolean/status checks
            if field_name == 'datasheet_local' and points_model.datasheet_local > 0:
                max_score += points_model.datasheet_local
            elif field_name == 'footprint_project_manual' and points_model.footprint_project_manual > 0:
                 # Assume the highest footprint score represents the 'best' case
                 max_score += max(points_model.footprint_project_manual,
                                  points_model.footprint_project_apiverified,
                                  points_model.footprint_project_inventory,
                                  points_model.footprint_kicad_lib)
            elif field_name == 'symbol_project_lib' and points_model.symbol_project_lib > 0:
                 max_score += max(points_model.symbol_project_lib, points_model.symbol_kicad_lib)
            elif field_name == 'mpn_exists' and points_model.mpn_exists > 0:
                 max_score += points_model.mpn_exists
            # Add optional checks if they have positive scores defined
            # Example: if hasattr(points_model, 'llm_doc_check_ok') and points_model.llm_doc_check_ok > 0:
            #    max_score += points_model.llm_doc_check_ok

        # Add points for URL only if local isn't counted, avoid double counting
        if hasattr(points_model, 'datasheet_url') and points_model.datasheet_url > 0 and not (hasattr(points_model, 'datasheet_local') and points_model.datasheet_local > 0):
             max_score += points_model.datasheet_url

        # Return a reasonable minimum if no positive points are defined
        return max(max_score, 1.0)


    def calculate(self, component: Component) -> Dict[str, Any]:
        """Calculates the health score and details for a given component."""
        score = 0.0
        details = []
        points = self.rules.points # Shortcut to points rules

        # 1. Datasheet Score
        if component.status.datasheet_local:
            score += points.datasheet_local
            details.append(f"[+{points.datasheet_local:.1f}] Datasheet Local")
        elif component.datasheet_url and component.status.datasheet_url_valid: # Check if URL was verified (optional)
            score += points.datasheet_url
            details.append(f"[+{points.datasheet_url:.1f}] Datasheet URL Valid")
        elif component.datasheet_url:
             # No points if only URL exists but wasn't verified/downloaded
             details.append("[+0.0] Datasheet URL Only")
        else:
             details.append("[-??] Datasheet Missing") # Consider negative points?

        # 2. Footprint Score
        if component.status.footprint_verified == 'review_pending':
            score += points.footprint_bom_apireview # Low score while pending review
            details.append(f"[+{points.footprint_bom_apireview:.1f}] Footprint Review Pending (API)")
        elif component.status.footprint_verified: # True means accepted/verified
            fp_source = component.source_info or ""
            fp_origin = component.footprint_source if hasattr(component, 'footprint_source') else 'unknown' # Handle base Component vs InventoryComponent
            # Prioritize source based on confidence
            if "ProjectLib-Manual" in fp_source: # Made manually for project
                 pts = points.footprint_project_manual
                 details.append(f"[+{pts:.1f}] Footprint Verified (Project Manual)")
            elif "ProjectLib-API" in fp_source: # API downloaded and accepted
                 pts = points.footprint_project_apiverified
                 details.append(f"[+{pts:.1f}] Footprint Verified (Project API)")
            elif "Inventory" in fp_source:
                if fp_origin == 'manual' or fp_origin == 'kit_ingest_verified':
                     pts = points.footprint_project_inventory
                     details.append(f"[+{pts:.1f}] Footprint Verified (Inventory Manual/Kit)")
                elif fp_origin == 'api':
                     pts = points.footprint_inventory_api
                     details.append(f"[+{pts:.1f}] Footprint Used (Inventory API)")
                elif fp_origin == 'llm':
                     pts = points.footprint_inventory_llm
                     details.append(f"[+{pts:.1f}] Footprint Used (Inventory LLM)")
                else: # Unknown inventory source
                     pts = points.footprint_kicad_lib # Default to KiCad lib score? Or lower?
                     details.append(f"[+{pts:.1f}] Footprint Used (Inventory Unknown Src)")
            elif component.status.footprint_exists and component.footprint: # Found in KiCad Lib
                pts = points.footprint_kicad_lib
                details.append(f"[+{pts:.1f}] Footprint Found (KiCad Lib)")
            else: # Should not happen if verified is True, but as fallback
                 pts = 0
                 details.append("[+0.0] Footprint Status Inconsistent")
            score += pts
        elif component.status.llm_suggested and component.footprint: # LLM suggested but not verified
            score += points.footprint_bom_llmsuggest
            details.append(f"[+{points.footprint_bom_llmsuggest:.1f}] Footprint LLM Suggested (Needs Verify)")
        elif component.status.footprint_exists and component.footprint: # Exists but not verified (e.g., found in KiCad lib but not explicitly accepted)
            score += points.footprint_kicad_lib * 0.5 # Reduced score?
            details.append(f"[+{points.footprint_kicad_lib * 0.5:.1f}] Footprint Found (Needs Verify)")
        else: # Missing
            details.append("[-??] Footprint Missing/Not Found")

        # 3. Symbol Score (Simplified)
        if component.status.symbol_exists: # Based on heuristic check
             # Could differentiate project vs standard lib if status is richer
             pts = max(points.symbol_project_lib, points.symbol_kicad_lib) # Assume best case found
             score += pts
             details.append(f"[+{pts:.1f}] Symbol Found (Heuristic)")
        else:
             details.append("[-??] Symbol Missing (Heuristic)")

        # 4. MPN Score
        if component.mpn:
             score += points.mpn_exists
             details.append(f"[+{points.mpn_exists:.1f}] MPN Provided")
        else:
             details.append("[+0.0] MPN Missing")

        # 5. Optional LLM/LMM Checks (Example)
        # if component.status.llm_doc_check_status == 'OK':
        #     pts = getattr(points, 'llm_doc_check_ok', 0.5)
        #     score += pts
        #     details.append(f"[+{pts:.1f}] LLM Doc Check OK")
        # elif component.status.llm_doc_check_status == 'Mismatch':
        #     pts = getattr(points, 'llm_doc_check_mismatch', -0.5) # Example negative points
        #     score += pts
        #     details.append(f"[{pts:.1f}] LLM Doc Check Mismatch!")
        # Add similar logic for LMM footprint check status if implemented

        # Ensure score isn't negative maybe? Or allow it?
        # score = max(0, score)

        return {
            "score": round(score, 2),
            "max_possible": self.max_possible_score,
            "details": details
        }

if __name__ == '__main__':
     print("--- Testing HealthCalculator ---")
     # Example Usage (requires mock component and config)
     # from component_base import Component
     # from scripts.utils.config_loader import load_config
     # config = load_config('../../config.yaml') # Adjust path
     # calc = HealthCalculator(config.health_rules)
     #
     # comp = Component(value="10k", description="Test Resistor", footprint="Resistor_SMD:R_0805_2012Metric")
     # comp.status.footprint_exists = True
     # comp.status.symbol_exists = True
     #
     # score_data = calc.calculate(comp)
     # print("\nTest Component Score:")
     # print(f"  Score: {score_data['score']} / {score_data['max_possible']}")
     # print("  Details:")
     # for detail in score_data['details']:
     #     print(f"    {detail}")
     pass

