# adk_tools/interactive_tools.py
import google.adk as adk
from typing import Dict, Any, Optional, List, Literal
from pathlib import Path
import shutil

# Assume imports work
# from utils.kicad_utils import LibraryManager # Needed? Or just move files?

class ProcessAcceptedAssetsTool(adk.tools.BaseTool):
    """Moves verified assets from review dir to main libs and updates BoM state."""
    def __init__(self, project_root: Path, name="ProcessAcceptedAssets", description="Promotes reviewed assets."):
        super().__init__(name=name, description=description)
        self._project_root = project_root
        self._review_dir_base = project_root / "libs" / "review"
        self._project_fp_lib_dir = project_root / "libs" # Dir containing .pretty dirs
        self._project_sym_lib_dir = project_root / "libs" # Dir containing .kicad_sym files

    def _move_asset(self, asset_relative_path: str, asset_type: Literal['symbol', 'footprint']) -> Optional[str]:
        """Moves a verified asset file, returning its new Lib:Name reference."""
        review_asset_path = self._review_dir_base.parent.parent / asset_relative_path # Make absolute from root
        if not review_asset_path.is_file():
            print(f"  ERROR: Asset file to promote not found: {review_asset_path}")
            return None

        filename = review_asset_path.name
        new_ref = None

        try:
            if asset_type == 'footprint' and filename.endswith('.kicad_mod'):
                # Footprints go into LibraryName.pretty/
                # We need to know the target library name. Assume MPN or Ref used for review dir name?
                # Let's assume the review dir was named like 'libs/review/MPN/'
                # And we want to create 'libs/footprints.pretty/MPN.pretty/' or similar structure.
                # This logic needs refinement based on desired project lib structure.
                # Simple version: Put all accepted FPs into a single project .pretty lib?
                target_pretty_lib_name = "Project_Footprints.pretty" # Example name
                target_dir = self._project_fp_lib_dir / target_pretty_lib_name
                target_dir.mkdir(exist_ok=True)
                target_path = target_dir / filename
                shutil.move(str(review_asset_path), str(target_path))
                new_ref = f"{target_pretty_lib_name.replace('.pretty','')}:{filename.replace('.kicad_mod','')}"
                print(f"  Moved footprint {filename} to {target_pretty_lib_name}")

            elif asset_type == 'symbol' and filename.endswith('.kicad_sym'):
                # Symbols can be individual files in the target dir
                target_dir = self._project_sym_lib_dir
                target_path = target_dir / filename
                shutil.move(str(review_asset_path), str(target_path))
                # Symbol ref needs parsing from file or standard Lib:Name format assumed?
                # Assume Lib name is filename stem for now
                lib_name = filename.replace('.kicad_sym', '')
                # Symbol name would need to be extracted or passed in. How to know?
                # This tool might need more input (expected symbol name).
                # For now, just confirm move. The user needs to ensure the BoM uses correct ref.
                print(f"  Moved symbol library {filename} to {target_dir}")
                # Returning just confirmation, actual Ref needs separate handling maybe
                new_ref = f"Moved:{lib_name}" # Indicate moved, user updates BoM manually?

            # Clean up empty review subdirectory?
            try:
                review_asset_path.parent.rmdir() # Only removes if empty
            except OSError:
                pass # Ignore if not empty

            return new_ref # Return new Lib:Name or confirmation

        except Exception as e:
            print(f"ERROR moving asset {review_asset_path}: {e}")
            # Should we try to move it back?
            return None


    async def run_async(self, *, accepted_assets: List[Dict], tool_context: adk.ToolContext) -> Dict[str, Any]:
        """
        Input: accepted_assets (List of dicts, e.g., [{'ref': 'U1', 'asset_type': 'footprint', 'review_path': 'libs/review/MPN123/fp.kicad_mod'}])
        Output: {'processed_refs': Dict[str, Dict], 'errors': List[str]}
                 processed_refs maps original ref to {'new_footprint': 'Lib:Name', 'new_symbol': 'Lib:Name'} if applicable
        """
        print(f"TOOL: Processing {len(accepted_assets)} accepted assets...")
        processed = {}
        errors = []

        for item in accepted_assets:
            ref = item.get('ref')
            asset_type = item.get('asset_type')
            review_path = item.get('review_path') # Relative path stored during download

            if not all([ref, asset_type, review_path]):
                errors.append(f"Invalid item format in accepted_assets: {item}")
                continue

            print(f"  Processing {ref} ({asset_type})...")
            new_ref_or_confirmation = self._move_asset(review_path, asset_type)

            if new_ref_or_confirmation:
                if ref not in processed: processed[ref] = {}
                if asset_type == 'footprint' and ':' in new_ref_or_confirmation:
                     processed[ref]['new_footprint'] = new_ref_or_confirmation
                elif asset_type == 'symbol':
                     processed[ref]['symbol_moved'] = True # Indicate symbol moved
            else:
                errors.append(f"Failed to process accepted {asset_type} for {ref}")

        print("TOOL: Finished processing accepted assets.")
        return {'processed_refs': processed, 'errors': errors}