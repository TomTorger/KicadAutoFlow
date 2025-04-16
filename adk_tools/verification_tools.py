# adk_tools/verification_tools.py
import google.adk as adk
from typing import Dict, Any, Optional, List, Literal
from pathlib import Path

# Assume these imports work based on structure
from utils.kicad_utils import LibraryManager
from utils.file_utils import DatasheetManager
from utils.health_calculator import HealthCalculator
from data_models.component import Component, ParsedFootprintData # For type hints and recreating objects
from adk_capabilities.footprint_api_capability import FootprintAPICapability # Use the capability

class CheckLibraryAssetTool(adk.tools.BaseTool):
    """Checks for footprint or symbol existence in local/KiCad libraries."""
    def __init__(self, lib_manager: LibraryManager, name="CheckLibraryAsset", description="Checks if KiCad symbol/footprint exists."):
        super().__init__(name=name, description=description)
        self._lib_manager = lib_manager

    async def run_async(self, *, asset_ref: str, asset_type: Literal['symbol', 'footprint'], tool_context: adk.ToolContext) -> Dict[str, Any]:
        print(f"TOOL: Checking library for {asset_type}: {asset_ref}")
        exists = False
        lib_found = False
        definition_found = False # Specific to symbols
        parsed_ok = False # Specific to footprints (can we parse it?)
        details = ParsedFootprintData() # Specific to footprints

        try:
            if asset_type == 'footprint':
                exists = self._lib_manager.footprint_exists(asset_ref)
                if exists:
                     # Try parsing details if it exists
                     details = self._lib_manager.get_footprint_details(asset_ref)
                     parsed_ok = not details.errors
            elif asset_type == 'symbol':
                lib_found, definition_found = self._lib_manager.symbol_definition_exists(asset_ref)
                exists = definition_found # Consider 'exists' only if definition is found
            else:
                return {'error': f"Unknown asset_type: {asset_type}"}

            return {
                'asset_ref': asset_ref,
                'asset_type': asset_type,
                'exists': exists, # True only if file/definition found AND parsed OK for FP
                'lib_found': lib_found, # Symbol specific: lib file exists
                'definition_found': definition_found, # Symbol specific: def found in lib
                'parsed_ok': parsed_ok, # Footprint specific
                'parsed_details': details.model_dump(mode='json') if asset_type == 'footprint' else None
            }
        except Exception as e:
            print(f"ERROR in CheckLibraryAssetTool for {asset_ref}: {e}")
            return {'error': str(e), 'asset_ref': asset_ref, 'asset_type': asset_type, 'exists': False}


class DownloadDatasheetTool(adk.tools.BaseTool):
    """Downloads a datasheet if URL is provided and not already local."""
    def __init__(self, ds_manager: DatasheetManager, name="DownloadDatasheet", description="Downloads component datasheet."):
        super().__init__(name=name, description=description)
        self._ds_manager = ds_manager

    async def run_async(self, *, component_data: Dict, tool_context: adk.ToolContext) -> Dict[str, Any]:
        print(f"TOOL: Checking/Downloading datasheet for {component_data.get('ref', 'N/A')}")
        # Recreate component object to use manager's methods easily
        # Pass only necessary fields if preferred
        try:
            component_obj = Component(**component_data)
            local_exists = self._ds_manager.check_local(component_obj)
            downloaded = False
            if not local_exists and component_obj.datasheet_url:
                downloaded = self._ds_manager.download(component_obj)

            return {
                'datasheet_downloaded': downloaded,
                'datasheet_local_path_valid': local_exists or downloaded,
                'datasheet_local': component_obj.datasheet_local # Path updated by manager
            }
        except Exception as e:
             print(f"ERROR in DownloadDatasheetTool: {e}")
             return {'datasheet_downloaded': False, 'datasheet_local_path_valid': False, 'datasheet_local': None, 'error': str(e)}


class SearchFootprintApiTool(adk.tools.BaseTool):
    """Searches a footprint API (e.g., SnapEDA) using MPN."""
    def __init__(self, fp_capability: FootprintAPICapability, name="SearchFootprintApi", description="Searches footprint API by MPN."):
        super().__init__(name=name, description=description)
        self._fp_capability = fp_capability

    async def run_async(self, *, mpn: str, tool_context: adk.ToolContext) -> Dict[str, Any]:
        print(f"TOOL: Searching footprint API for MPN: {mpn}")
        if not mpn:
             return {'api_results': [], 'error': 'MPN not provided'}
        try:
            results = self._fp_capability.search_by_mpn(mpn)
            return {'api_results': results} # List of dicts from capability
        except Exception as e:
             print(f"ERROR in SearchFootprintApiTool: {e}")
             return {'api_results': [], 'error': str(e)}


class DownloadApiAssetTool(adk.tools.BaseTool):
    """Downloads a specific asset found via API search to the review directory."""
    def __init__(self, fp_capability: FootprintAPICapability, project_root: Path, name="DownloadApiAsset", description="Downloads API asset to review dir."):
        super().__init__(name=name, description=description)
        self._fp_capability = fp_capability
        self._review_dir_base = project_root / "libs" / "review"

    async def run_async(self, *, asset_info: Dict, asset_type: Literal['symbol', 'footprint'], tool_context: adk.ToolContext) -> Dict[str, Any]:
        mpn = asset_info.get('mpn', 'UnknownMPN')
        print(f"TOOL: Attempting download of {asset_type} for {mpn} to review dir.")
        # Create a specific review subdirectory for this component
        # Use MPN if available, otherwise maybe ref from context? Need consistent ID.
        component_review_dir = self._review_dir_base / mpn
        component_review_dir.mkdir(parents=True, exist_ok=True)

        try:
            download_path = self._fp_capability.download_asset(asset_info, asset_type, component_review_dir)
            if download_path:
                 return {
                     'success': True,
                     'downloaded_path': str(download_path.relative_to(self._review_dir_base.parent.parent)), # Relative path
                     'review_dir': str(component_review_dir.relative_to(self._review_dir_base.parent.parent))
                 }
            else:
                 return {'success': False, 'error': f'Download failed via capability for {mpn} ({asset_type})'}
        except Exception as e:
             print(f"ERROR in DownloadApiAssetTool: {e}")
             return {'success': False, 'error': str(e)}

class CalculateHealthScoreTool(adk.tools.BaseTool):
    """Calculates the health score for a component based on its status."""
    def __init__(self, health_calculator: HealthCalculator, name="CalculateHealthScore", description="Calculates component health score."):
        super().__init__(name=name, description=description)
        self._calculator = health_calculator

    async def run_async(self, *, component_data: Dict, tool_context: adk.ToolContext) -> Dict[str, Any]:
        # print(f"TOOL: Calculating health score for {component_data.get('ref', 'N/A')}")
        try:
            # Recreate component to ensure status types are correct
            component_obj = Component(**component_data)
            health_data = self._calculator.calculate(component_obj) # Returns dict
            return {'health_score': health_data}
        except Exception as e:
            print(f"ERROR in CalculateHealthScoreTool: {e}")
            return {'health_score': None, 'error': str(e)}