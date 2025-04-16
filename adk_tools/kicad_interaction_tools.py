# adk_tools/kicad_interaction_tools.py
import google.adk as adk
from typing import Dict, Any, Optional, List, Dict, Any
from pathlib import Path

# Assume imports work
from utils.kicad_utils import LibraryManager
from data_models.bom_data import BoM # Needs to load the BoM object

class GenerateKiCadFieldsDataTool(adk.tools.BaseTool):
    """Generates text suitable for pasting into KiCad's Edit Symbol Fields table."""
    def __init__(self, name="GenerateKiCadFieldsData", description="Generates data for KiCad field editor."):
        super().__init__(name=name, description=description)

    async def run_async(self, *, bom_data: List[Dict], tool_context: adk.ToolContext) -> Dict[str, Any]:
        """
        Input: bom_data (List of component dictionaries after verification).
        Output: {'clipboard_text': str}
        """
        print("TOOL: Generating KiCad field editor data...")
        header = "Reference\tValue\tFootprint\tDatasheet\tMPN\tDescription" # Adjust columns as needed
        lines = [header]
        try:
            for comp_dict in bom_data:
                 # Use defaults for missing fields
                 ref = comp_dict.get('ref', '')
                 val = comp_dict.get('value', '')
                 fp = comp_dict.get('footprint', '') or '~' # Use ~ for empty in KiCad often
                 ds = comp_dict.get('datasheet_url', '') or comp_dict.get('datasheet_local', '') or '~'
                 mpn = comp_dict.get('mpn', '') or '~'
                 desc = comp_dict.get('description', '') or '~'
                 lines.append(f"{ref}\t{val}\t{fp}\t{ds}\t{mpn}\t{desc}")
            return {'clipboard_text': "\n".join(lines)}
        except Exception as e:
            print(f"ERROR in GenerateKiCadFieldsDataTool: {e}")
            return {'clipboard_text': f"Error generating data: {e}"}

class CalculateFootprintAreaTool(adk.tools.BaseTool):
    """Calculates total estimated PCB area based on BoM footprints."""
    def __init__(self, lib_manager: LibraryManager, name="CalculateFootprintArea", description="Estimates total footprint area."):
        super().__init__(name=name, description=description)
        self._lib_manager = lib_manager

    async def run_async(self, *, bom_data: List[Dict], tool_context: adk.ToolContext) -> Dict[str, Any]:
        """
        Input: bom_data (List of component dictionaries).
        Output: {'total_area_mm2': float, 'breakdown': Dict[str, float|None]}
        """
        print("TOOL: Calculating estimated footprint area...")
        total_area = 0.0
        breakdown = {}
        errors = 0
        try:
            for comp_dict in bom_data:
                ref = comp_dict.get('ref')
                fp_ref = comp_dict.get('footprint')
                qty = comp_dict.get('qty', 1)
                area = None
                if fp_ref:
                    area = self._lib_manager.get_footprint_area(fp_ref) # Returns None on error/not found

                if area is not None:
                     total_area += area * qty
                     breakdown[ref] = round(area, 2)
                else:
                     breakdown[ref] = None # Indicate failure for this component
                     errors += 1

            return {'total_area_mm2': round(total_area, 2), 'breakdown': breakdown, 'errors': errors}
        except Exception as e:
             print(f"ERROR in CalculateFootprintAreaTool: {e}")
             return {'total_area_mm2': 0.0, 'breakdown': {}, 'errors': len(bom_data), 'error_msg': str(e)}

# Add Netlist Generation tool here if desired
# class GeneratePowerNetlistTool(adk.tools.BaseTool): ...