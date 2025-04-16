# utils/kicad_utils.py
# (Content from Iteration 3 update script using kiutils is suitable)
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Union, Literal, Any # Added Union, Literal
import os
import re
# Ensure kiutils is installed: pip install kiutils
try:
    from kiutils.footprint import Footprint
    from kiutils.symbol import SymbolLib, Symbol
    from kiutils.items.common import Position
    KIUTILS_AVAILABLE = True
except ImportError:
    print("WARNING: kiutils library not found. Symbol parsing and accurate footprint analysis disabled.")
    print("Install using: pip install kiutils")
    KIUTILS_AVAILABLE = False
    class Footprint: pass
    class SymbolLib: pass
    class Symbol: pass
    class Position: pass
    class KiutilsParseError(Exception): pass

from data_models.component import ParsedFootprintData # Use relative import

class LibraryManager:
    """Handles interactions with KiCad libraries using kiutils if available."""
    def __init__(self, config, project_root: Union[str, Path]):
        self.config = config
        self.project_root = Path(project_root)
        self.project_libs_dir = self.project_root / "libs"
        self.project_footprint_dir = self.project_libs_dir
        self.project_symbol_dir = self.project_libs_dir
        self.project_footprint_dir.mkdir(parents=True, exist_ok=True)
        self.project_symbol_dir.mkdir(parents=True, exist_ok=True)
        # Use validated paths from config object
        self.standard_symbol_libs_paths = config.validated_kicad_symbol_libs
        self.standard_footprint_libs_paths = config.validated_kicad_footprint_libs
        print(f"LibraryManager Initialized. Project libs: {self.project_libs_dir}")

    def find_asset_file_path(self, asset_ref: str, asset_type: Literal['symbol', 'footprint']) -> Optional[Path]:
        # (Search logic from Iteration 3 - seems okay)
        if not asset_ref or ':' not in asset_ref: return None
        lib_name, asset_name = asset_ref.split(':', 1)
        search_dirs: List[Path] = []
        target_lib_name = ""; is_dir_lib = False

        if asset_type == 'footprint':
            search_dirs.append(self.project_footprint_dir)
            search_dirs.extend(self.standard_footprint_libs_paths)
            target_lib_name = f"{lib_name}.pretty"; is_dir_lib = True
        elif asset_type == 'symbol':
            search_dirs.append(self.project_symbol_dir)
            search_dirs.extend(self.standard_symbol_libs_paths)
            target_lib_name = f"{lib_name}.kicad_sym"; is_dir_lib = False
        else: return None

        for base_dir in search_dirs:
            potential_lib_path = base_dir / target_lib_name
            if is_dir_lib: # Footprint lib (.pretty dir)
                if potential_lib_path.is_dir():
                    asset_file = potential_lib_path / f"{asset_name}.kicad_mod"
                    if asset_file.is_file(): return asset_file
            else: # Symbol lib (.kicad_sym file)
                if potential_lib_path.is_file(): return potential_lib_path # Return lib path
        return None

    def footprint_exists(self, footprint_ref: Optional[str]) -> bool:
        return self.find_asset_file_path(footprint_ref, 'footprint') is not None if footprint_ref else False

    def symbol_definition_exists(self, symbol_ref: Optional[str]) -> Tuple[bool, bool, bool]:
        """Checks lib file existence, parse success, and symbol definition presence."""
        if not KIUTILS_AVAILABLE: return False, False, False
        if not symbol_ref: return False, False, False

        lib_path = self.find_asset_file_path(symbol_ref, 'symbol')
        if not lib_path: return False, False, False

        lib_found = True; parsed_ok = False; definition_found = False
        try:
            lib = SymbolLib.from_file(str(lib_path))
            parsed_ok = True
            _, symbol_name = symbol_ref.split(':', 1)
            definition_found = any(symbol.entryName == symbol_name for symbol in lib.symbols)
        except KiutilsParseError as e: print(f"WARN: kiutils parsing error for {lib_path}: {e}")
        except Exception as e: print(f"WARN: Unexpected error reading symbol library {lib_path}: {e}")
        return lib_found, parsed_ok, definition_found

    def get_footprint_details(self, footprint_ref: Optional[str]) -> ParsedFootprintData:
        """Parses footprint using kiutils to get area and pin count."""
        results = ParsedFootprintData()
        if not KIUTILS_AVAILABLE: results.errors.append("kiutils library not installed."); return results
        if not footprint_ref: results.errors.append("Missing footprint reference"); return results

        fp_path = self.find_asset_file_path(footprint_ref, 'footprint')
        if not fp_path: results.errors.append(f"Footprint file not found: '{footprint_ref}'"); return results

        try:
            fp = Footprint.from_file(str(fp_path))
            results.pin_count = len(fp.pads)
            # Only attempt area calculation if getBoundingBox exists
            if hasattr(fp, 'getBoundingBox'):
                layers_cy = ["F.CrtYd", "B.CrtYd"]
                bbox_cy = fp.getBoundingBox(includeText=False, layers=layers_cy)
                if bbox_cy.width is not None and bbox_cy.height is not None and bbox_cy.width > 0 and bbox_cy.height > 0:
                    results.courtyard_area = round(bbox_cy.width * bbox_cy.height, 2)
                    results.bounding_box_area = results.courtyard_area
                else: # Fallback to overall bounding box
                    bbox_all = fp.getBoundingBox(includeText=False)
                    if bbox_all.width is not None and bbox_all.height is not None and bbox_all.width > 0 and bbox_all.height > 0:
                        results.bounding_box_area = round(bbox_all.width * bbox_all.height, 2)
                        if results.courtyard_area is None: results.errors.append("Courtyard area missing/invalid, used overall bounding box.")
                    else: results.errors.append("Could not determine valid bounding box.")
            else:
                results.errors.append("getBoundingBox not available in kiutils; area calculation skipped.")
        except Exception as e:
            error_msg = f"Unexpected parse error: {e}"
            print(f"WARN: {error_msg} for {footprint_ref}")
            results.errors.append(error_msg)
        return results