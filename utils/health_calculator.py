# utils/health_calculator.py
# (Content from Iteration 3 update script using refined status flags is suitable)
from typing import Dict, List, Any, Optional
from data_models.component import Component, HealthScore
from utils.config_loader import HealthRules # Use relative import

class HealthCalculator:
    def __init__(self, health_rules: HealthRules):
        self.rules = health_rules
        self.max_possible_score = self._calculate_max_score(health_rules.points)
        print(f"HealthCalculator Initialized. Max possible score: {self.max_possible_score:.1f}")

    def _calculate_max_score(self, points) -> float:
        max_score = 0.0
        max_score += getattr(points, 'datasheet_local', 0.0)
        max_score += max(getattr(points, 'footprint_project_manual', 0.0), getattr(points, 'footprint_project_apiverified', 0.0), getattr(points, 'footprint_project_inventory', 0.0))
        max_score += getattr(points, 'footprint_parsed_ok', 0.0)
        max_score += getattr(points, 'symbol_definition_found', 0.0) # Use definition found score
        max_score += getattr(points, 'mpn_exists', 0.0)
        # Add optional positive scores if defined
        return max(max_score, 1.0)

    def calculate(self, component: Component) -> HealthScore:
        score = 0.0; details = []
        points = self.rules.points; status = component.status

        # 1. Datasheet
        if status.datasheet_local_path_valid: pts = points.datasheet_local; score += pts; details.append(f"[+{pts:.1f}] Datasheet Local Valid")
        elif component.datasheet_url: details.append("[+0.0] Datasheet URL Only")
        else: details.append("[FAIL] Datasheet Missing")

        # 2. Footprint
        if status.footprint_verified:
            fp_source = component.source_info or ""; inv_fp_source = getattr(component, 'footprint_source', 'unknown') if "Inventory" in fp_source else 'n/a'
            if "Manual" in fp_source or "Project" in fp_source or inv_fp_source == 'manual': pts = points.footprint_project_manual
            elif "API" in fp_source or inv_fp_source == 'api_verified': pts = points.footprint_project_apiverified
            elif inv_fp_source == 'kit_ingest_verified': pts = points.footprint_project_inventory
            else: pts = points.footprint_kicad_lib # Fallback verified score
            score += pts; details.append(f"[+{pts:.1f}] Footprint Verified ({fp_source.split(':')[0]})")
            # Add bonus if verified footprint also parsed okay
            if status.footprint_parsed_ok: pts_p = getattr(points, 'footprint_parsed_ok', 0.2); score += pts_p; details.append(f"[+{pts_p:.1f}] Footprint Parsable")
        elif status.footprint_review_pending: pts = points.footprint_bom_apireview; score += pts; details.append(f"[+{pts:.1f}] Footprint Review Pending (API)")
        elif status.llm_suggested and component.footprint: pts = points.footprint_bom_llmsuggest; score += pts; details.append(f"[+{pts:.1f}] Footprint LLM Suggested (Verify!)")
        elif status.footprint_found_libs and component.footprint: pts = points.footprint_kicad_lib; score += pts; details.append(f"[+{pts:.1f}] Footprint Found Lib (Verify!)")
        else: details.append("[FAIL] Footprint Missing/Not Found")

        # 3. Symbol
        if status.symbol_definition_found: pts = getattr(points, 'symbol_definition_found', 1.0); score += pts; details.append(f"[+{pts:.1f}] Symbol Definition Found")
        elif status.symbol_found_libs: pts = getattr(points, 'symbol_library_found', 0.2); score += pts; details.append(f"[+{pts:.1f}] Symbol Library Found (Def Unknown)")
        else: details.append("[FAIL] Symbol Library/Definition Missing")

        # 4. MPN
        if component.mpn: pts = points.mpn_exists; score += pts; details.append(f"[+{pts:.1f}] MPN Provided")
        else: details.append("[INFO] MPN Missing")

        # 5. Optional LLM/LMM Checks (Add scoring logic here based on status.llm_..._result)
        if status.llm_datasheet_check_result: details.append(f"[INFO] LLM Doc Check Ran: {status.llm_datasheet_check_result.get('notes','No notes')}")
        if status.lmm_footprint_check_result: details.append(f"[INFO] LMM FP Check Ran: {status.lmm_footprint_check_result.get('notes','No notes')}")

        final_score = round(max(0, score), 2)
        return HealthScore(score=final_score, max_possible=round(self.max_possible_score, 2), details=details, rules_version=self.rules.version)