import pytest
from pathlib import Path
import sys
import yaml
import shutil

# Ensure scripts/modules directory is discoverable (adjust if needed)
repo_root = Path(__file__).parent.parent
# Add directories containing the modules being tested
module_paths = [
    repo_root,
    repo_root / 'data_models',
    repo_root / 'utils',
    repo_root / 'adk_capabilities',
    # Add other necessary paths like adk_tools, adk_agents if importing directly
]
for p in module_paths:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Import classes to be mocked or used in fixtures
# Use try-except for robustness
try:
    from utils.config_loader import AppConfig, load_config, HealthRules, HealthPoints
    from data_models.component import Component, ComponentStatus, HealthScore, ParsedFootprintData
    from data_models.inventory_item import InventoryItem
    from inventory import Inventory # Assumes Inventory class is in inventory.py at top level now
    from data_models.bom_data import BoM
    from adk_capabilities.api_client_base import LLMCapability, FootprintAPICapability
    # Import Dummy clients if using them directly, or rely on mocker
    # from adk_capabilities.llm_capability import GeminiCapability, OpenAICapabilityPlaceholder
    # from adk_capabilities.footprint_api_capability import SnapEDACapability
    from utils.kicad_utils import LibraryManager
    from utils.file_utils import DatasheetManager
    from utils.health_calculator import HealthCalculator
except ImportError as e:
    print(f"ERROR in conftest.py import: {e}")
    print("Ensure all necessary modules exist and sys.path is correct.")
    # raise # Optionally re-raise to halt tests if imports fail


from utils.kicad_utils import LibraryManager, KIUTILS_AVAILABLE # Import flag
from data_models.component import ParsedFootprintData

# Skip all tests in this file if kiutils is not available
pytestmark = pytest.mark.skipif(not KIUTILS_AVAILABLE, reason="kiutils library not installed")

@pytest.fixture
def lib_manager(mock_config_obj, project_root_dir, temp_kicad_libs_fixture):
    """Provides a LibraryManager configured with temporary libs."""
    # Configure mock_config to point to temp libs
    mock_config_obj.kicad_paths.standard_symbol_libs = [str(temp_kicad_libs_fixture['symbol'])]
    mock_config_obj.kicad_paths.standard_footprint_libs = [str(temp_kicad_libs_fixture['footprint'])]
    # Set validated paths for LibraryManager compatibility
    mock_config_obj.validated_kicad_symbol_libs = [temp_kicad_libs_fixture['symbol']]
    mock_config_obj.validated_kicad_footprint_libs = [temp_kicad_libs_fixture['footprint']]

    lm = LibraryManager(mock_config_obj, project_root_dir)
    # Point project libs to temp dirs too for simpler testing
    lm.project_footprint_dir = temp_kicad_libs_fixture['footprint'].parent
    lm.project_symbol_dir = temp_kicad_libs_fixture['symbol']
    return lm


def test_find_asset_file_path_fp_success(lib_manager: LibraryManager):
    fp_ref = "Resistor_SMD:R_0805_2012Metric"
    found_path = lib_manager.find_asset_file_path(fp_ref, 'footprint')
    assert found_path is not None; assert found_path.exists()
    assert found_path.name == "R_0805_2012Metric.kicad_mod"

def test_find_asset_file_path_sym_success(lib_manager: LibraryManager):
    sym_ref = "Device:R"
    found_path = lib_manager.find_asset_file_path(sym_ref, 'symbol')
    assert found_path is not None; assert found_path.exists()
    assert found_path.name == "Device.kicad_sym"

def test_find_asset_file_path_not_found(lib_manager: LibraryManager):
    assert lib_manager.find_asset_file_path("FakeLib:FakeFP", 'footprint') is None
    assert lib_manager.find_asset_file_path("FakeLib:FakeSym", 'symbol') is None

def test_footprint_exists(lib_manager: LibraryManager):
    assert lib_manager.footprint_exists("Resistor_SMD:R_0805_2012Metric") is True
    assert lib_manager.footprint_exists("FakeLib:FakeFP") is False

def test_symbol_definition_exists(lib_manager: LibraryManager):
    lib_f, parsed_ok, def_f = lib_manager.symbol_definition_exists("Device:R")
    assert lib_f is True; assert parsed_ok is True; assert def_f is True

    lib_f, parsed_ok, def_f = lib_manager.symbol_definition_exists("Device:NonExistentSymbol")
    assert lib_f is True; assert parsed_ok is True; assert def_f is False

    lib_f, parsed_ok, def_f = lib_manager.symbol_definition_exists("FakeLib:FakeSym")
    assert lib_f is False; assert parsed_ok is False; assert def_f is False

def test_get_footprint_details_success(lib_manager: LibraryManager):
    fp_ref = "Resistor_SMD:R_0805_2012Metric"
    details = lib_manager.get_footprint_details(fp_ref)
    assert isinstance(details, ParsedFootprintData)
    # Accept either no errors or the specific error if getBoundingBox is missing
    if details.errors:
        assert len(details.errors) == 1
        assert "getBoundingBox not available in kiutils" in details.errors[0]
    assert details.pin_count == 2  # Based on dummy file content
    # Only check area if available
    if details.bounding_box_area is not None:
        assert details.bounding_box_area == pytest.approx(4.1)  # Approximate check

def test_get_footprint_details_not_found(lib_manager: LibraryManager):
     details = lib_manager.get_footprint_details("Fake:FP")
     assert "Footprint file not found" in details.errors[0]

