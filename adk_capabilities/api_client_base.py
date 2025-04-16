# adk_capabilities/api_client_base.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple, Literal
from pathlib import Path
# from pydantic import BaseModel # Optional: For structuring complex return types

class LLMCapability(ABC):
    """Abstract Base Class for LLM interaction capabilities."""

    @abstractmethod
    def suggest_footprint(self, package_desc: str, component_desc: str) -> Optional[str]:
        """Suggests a KiCad footprint string (Lib:Name) based on descriptions."""
        pass

    @abstractmethod
    def analyze_image_for_component(self, image_data: bytes) -> Optional[Dict[str, Any]]:
        """Analyzes component image, returns structured data (text, package, value guess)."""
        pass

    @abstractmethod
    def check_datasheet_consistency(self, datasheet_text: str, expected_params: Dict) -> Dict[str, Any]:
        """Checks datasheet text against expected parameters (pin_count, package).
           Returns structured results, e.g., {'pin_match': bool/None, 'pkg_match': bool/None, 'notes': str}.
        """
        pass

    @abstractmethod
    def get_default_text_model_name(self) -> str:
        """Returns the configured default model name for text tasks."""
        pass

    # Add other LLM tasks as needed, e.g., summarize_text

class FootprintAPICapability(ABC):
    """Abstract Base Class for Footprint Database API interaction capabilities."""

    @abstractmethod
    def search_by_mpn(self, mpn: str) -> List[Dict[str, Any]]:
        """Searches API by Manufacturer Part Number.
           Returns list of potential matches, including download info/IDs and availability flags.
           Example item: {'mpn': ..., 'manufacturer': ..., 'description': ..., 'has_kicad_fp': bool, 'has_kicad_sym': bool, 'api_specific_data': ...}
        """
        pass

    @abstractmethod
    def download_asset(self, asset_info: Dict, asset_type: Literal['symbol', 'footprint'], download_dir: Path) -> Optional[Path]:
        """Downloads a specific asset to the specified directory (e.g., libs/review/).
           Takes info dict from search_by_mpn result.
           Returns the path to the downloaded file on success, None otherwise.
        """
        pass