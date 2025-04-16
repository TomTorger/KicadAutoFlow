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


from utils.health_calculator import HealthCalculator
from data_models.component import Component, ComponentStatus, HealthScore
from utils.config_loader import HealthRules # Import for type hint

@pytest.fixture
def calculator(mock_config_obj): # Uses fixture
    return HealthCalculator(mock_config_obj.health_rules)

# Simplified test cases from before
@pytest.mark.parametrize("status_updates, source_info, footprint_source, expected_details_contain", [
    ({}, "Unknown", "unknown", ["Datasheet Missing", "[FAIL] Footprint Missing", "[FAIL] Symbol", "[INFO] MPN Missing"]),
    ({'datasheet_local_path_valid': True}, "Unknown", "unknown", ["[+1.0] Datasheet Local Valid"]),
    ({'footprint_verified': True, 'footprint_parsed_ok': True}, "ProjectLib-Manual", "manual", ["[+2.0] Footprint Verified (ProjectLib-Manual)", "[+0.2] Footprint Parsable"]),
    ({'symbol_definition_found': True, 'symbol_found_libs': True, 'symbol_parsed_ok': True}, "Unknown", "unknown", ["[+1.0] Symbol Definition Found"]),
])
def test_health_calculation_scenarios(calculator: HealthCalculator, sample_component_obj: Component, status_updates: dict, source_info: str, footprint_source: str, expected_details_contain: list):
    comp = sample_component_obj.model_copy(deep=True); comp.source_info = source_info
    if "[+] MPN Provided" in expected_details_contain: comp.mpn = "TestMPN123"
    if "Inventory" in source_info: setattr(comp, 'footprint_source', footprint_source)
    comp.update_status_fields(status_updates)
    score_data = calculator.calculate(comp)
    if isinstance(score_data, dict):
        health_score_obj = HealthScore(**score_data)
    else:
        health_score_obj = score_data
    assert health_score_obj.score >= 0
    for detail_substring in expected_details_contain:
        assert any(detail_substring in d for d in health_score_obj.details), f"'{detail_substring}' not found in {health_score_obj.details}"

