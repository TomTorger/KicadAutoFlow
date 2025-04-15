from pathlib import Path
from typing import Optional, List, Tuple, Union
import os
import re

# Simple S-expression parser helper (basic implementation)
# A more robust parser like 'sexpdata' might be needed for complex footprints
def find_closing_paren(text: str, start: int) -> int:
    """Finds the matching closing parenthesis for an opening one at 'start'."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return i
    return -1 # Not found

def parse_sexp_value(sexp_text: str, key: str) -> Optional[str]:
    """Very basic parser to find a simple key-value pair like '(key value)'."""
    # This is simplified - won't handle nested structures with the same key well
    # or keys/values with spaces without quotes. KiCad format is complex.
    pattern = re.compile(r'\(\s*' + re.escape(key) + r'\s+([^)\s]+)\s*\)')
    match = pattern.search(sexp_text)
    if match:
        return match.group(1).strip('"') # Strip quotes if present

    # Try harder for quoted values potentially containing spaces
    pattern_quoted = re.compile(r'\(\s*' + re.escape(key) + r'\s+"([^"]+)"\s*\)')
    match_quoted = pattern_quoted.search(sexp_text)
    if match_quoted:
        return match_quoted.group(1)

    return None

def find_kicad_asset_path(
    asset_ref: str, # e.g., "Resistor_SMD:R_0805_2012Metric" or "Device:R"
    asset_type: str, # 'footprint' or 'symbol'
    project_lib_dirs: Dict[str, Path], # e.g., {'symbol': Path('libs/'), 'footprint': Path('libs/')}
    standard_lib_dirs: List[Path]
    ) -> Optional[Path]:
    """Searches for a KiCad asset (symbol or footprint) in project and standard libraries."""

    if not asset_ref or ':' not in asset_ref:
        # print(f"Warning: Invalid asset reference format: '{asset_ref}'. Expected 'Lib:Name'.")
        return None

    lib_name, asset_name = asset_ref.split(':', 1)

    # Determine file extension based on asset type
    if asset_type == 'footprint':
        asset_dir_suffix = ".pretty"
        asset_file_suffix = ".kicad_mod"
        project_base_dir = project_lib_dirs.get('footprint')
    elif asset_type == 'symbol':
        asset_dir_suffix = ".kicad_sym" # KiCad 6+ uses .kicad_sym for lib files
        asset_file_suffix = "" # Symbols are inside the library file itself
        project_base_dir = project_lib_dirs.get('symbol')
    else:
        print(f"Error: Unknown asset type '{asset_type}'.")
        return None

    search_paths: List[Tuple[str, Path]] = [] # List of (type, directory)

    # 1. Check Project Libraries first
    if project_base_dir and project_base_dir.is_dir():
        # Footprint libs are directories ending in .pretty
        if asset_type == 'footprint':
            proj_lib_path = project_base_dir / (lib_name + asset_dir_suffix)
            if proj_lib_path.is_dir():
                search_paths.append(("project", proj_lib_path))
        # Symbol libs are files ending in .kicad_sym
        elif asset_type == 'symbol':
            # Assume symbols are directly in libs/ or in subdirs matching lib name?
            # KiCad's logic is complex here; let's keep it simple for now.
            # Check if the symbol lib file exists directly under the project base
            proj_lib_path = project_base_dir / (lib_name + asset_dir_suffix)
            if proj_lib_path.is_file():
                 search_paths.append(("project", proj_lib_path))
            # Maybe also check subdirectories named like the lib?
            # proj_lib_subdir = project_base_dir / lib_name
            # if proj_lib_subdir.is_dir():
            #      potential_file = proj_lib_subdir / (lib_name + asset_dir_suffix)
            #      if potential_file.is_file():
            #           search_paths.append(("project", potential_file))


    # 2. Check Standard KiCad Libraries
    for std_dir in standard_lib_dirs:
        if std_dir.is_dir():
            if asset_type == 'footprint':
                std_lib_path = std_dir / (lib_name + asset_dir_suffix)
                if std_lib_path.is_dir():
                    search_paths.append(("standard", std_lib_path))
            elif asset_type == 'symbol':
                 std_lib_path = std_dir / (lib_name + asset_dir_suffix)
                 if std_lib_path.is_file():
                      search_paths.append(("standard", std_lib_path))

    # 3. Search within the identified paths
    for lib_type, lib_path in search_paths:
        if asset_type == 'footprint':
            asset_file = lib_path / (asset_name + asset_file_suffix)
            if asset_file.is_file():
                # print(f"Found {asset_type} '{asset_ref}' in {lib_type} lib: {asset_file}")
                return asset_file
        elif asset_type == 'symbol':
            # Need to parse the .kicad_sym file to see if the symbol 'asset_name' is defined within
            # This requires a proper S-expression parser or careful regex
            try:
                with open(lib_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # VERY basic check: look for '(symbol "{asset_name}"' - highly unreliable
                # A robust solution needs parsing. Using basic check for now.
                symbol_def_start = f'(symbol "{asset_name}"'
                if symbol_def_start in content:
                     # print(f"Found {asset_type} '{asset_name}' in {lib_type} lib file: {lib_path}")
                     return lib_path # Return the library file path itself for symbols
            except Exception as e:
                print(f"Warning: Error reading symbol library {lib_path}: {e}")
                continue


    # print(f"Warning: Asset '{asset_ref}' ({asset_type}) not found in project or standard libs.")
    return None


def footprint_exists(footprint_ref: Optional[str], kicad_project, config) -> bool:
    """Checks if a footprint reference exists in configured libraries."""
    if not footprint_ref: return False
    project_libs = {'footprint': Path(kicad_project.libs_dir / "footprints.pretty").parent } # Path to dir containing .pretty dirs
    std_libs = config.kicad_paths.standard_footprint_libs
    return find_kicad_asset_path(footprint_ref, 'footprint', project_libs, std_libs) is not None

def symbol_exists(symbol_ref: Optional[str], kicad_project, config) -> bool:
    """Checks if a symbol reference exists in configured libraries (basic check)."""
    if not symbol_ref: return False
    project_libs = {'symbol': Path(kicad_project.libs_dir / "symbols.kicad_sym").parent } # Path to dir containing .kicad_sym files
    std_libs = config.kicad_paths.standard_symbol_libs
    # Note: This check is basic and might yield false positives/negatives without proper parsing
    return find_kicad_asset_path(symbol_ref, 'symbol', project_libs, std_libs) is not None


def parse_footprint_area(footprint_path: Union[str, Path]) -> Optional[float]:
    """Parses a .kicad_mod file to estimate footprint area (courtyard or bounding box).
       NOTE: This is a placeholder and needs a robust implementation.
    """
    fp_file = Path(footprint_path)
    if not fp_file.is_file():
        return None

    # --- Robust S-expression parsing is needed here ---
    # Example using basic regex (HIGHLY simplified and likely to fail on complex footprints)
    # This looks for '(layer F.CrtYd)' or '(layer B.CrtYd)' then coords in '(fp_line ... (xy x y) (xy x y)))'
    # Or a simple bounding box from all graphic elements.
    # A full implementation is complex. Returning placeholder value.

    min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
    found_coords = False

    try:
        with open(fp_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Try to find courtyard bounds first
        courtyard_layers = ['F.CrtYd', 'B.CrtYd']
        for layer in courtyard_layers:
             layer_pattern = re.compile(r'\(\s*layer\s+"?' + re.escape(layer) + r'?"?\s*\)(.*?)\s*\)\s*\)', re.DOTALL)
             # This nested regex is tricky... find layer block first
             # Simplified search for fp_line etc inside:
             coords_pattern = re.compile(r'\(xy\s+([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\)')
             for match in coords_pattern.finditer(content): # Search whole file for now (inaccurate)
                  # This needs to be scoped to the specific layer block!
                  # For now, just find bounding box of *all* coordinates
                  try:
                    x, y = float(match.group(1)), float(match.group(2))
                    min_x, min_y = min(min_x, x), min(min_y, y)
                    max_x, max_y = max(max_x, x), max(max_y, y)
                    found_coords = True
                  except ValueError:
                      continue # Ignore if conversion fails

        if found_coords:
            width = max_x - min_x
            height = max_y - min_y
            # print(f"Estimated bounding box area for {fp_file.name}: {width * height:.2f} mm^2")
            return width * height
        else:
            # print(f"Warning: Could not extract coordinates to estimate area for {fp_file.name}")
            return None # Indicate area couldn't be calculated

    except Exception as e:
        print(f"Error parsing footprint '{fp_file}' for area: {e}")
        return None


if __name__ == '__main__':
     # Example Usage (requires config loader and kicad_project setup)
     print("--- Testing kicad_utils ---")
     # Needs mock config/project or integration test setup
     # Example (conceptual):
     # config = load_config('../../config.yaml') # Adjust path if running directly
     # project = KiCadProject(project_root='../..') # Adjust path
     #
     # test_fp = "Resistor_SMD:R_0805_2012Metric"
     # exists = footprint_exists(test_fp, project, config)
     # print(f"Footprint '{test_fp}' exists: {exists}")
     # if exists:
     #     fp_path = find_kicad_asset_path(test_fp, 'footprint', {'footprint': project.libs_dir}, config.kicad_paths.standard_footprint_libs)
     #     if fp_path:
     #         area = parse_footprint_area(fp_path)
     #         print(f"Estimated area: {area} mm^2")
     #
     # test_sym = "Device:R"
     # exists = symbol_exists(test_sym, project, config)
     # print(f"Symbol '{test_sym}' exists (basic check): {exists}")
     pass
