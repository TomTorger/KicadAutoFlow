import pytest
from inventory_manager import Inventory
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
    from inventory_manager import Inventory # Assumes Inventory class is in inventory.py at top level now
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


from data_models.inventory_item import InventoryItem
from data_models.component import Component

def test_inventory_load_success(sample_inventory):
    inv = sample_inventory
    loaded = True  # Already loaded by fixture
    assert loaded is True; assert len(inv.data.inventory_parts) == 1
    assert inv.data.inventory_parts[0].part_id == "INV_TEST001"

def test_inventory_load_not_found(tmp_path, capsys): # Uses built-in fixture
    inv = Inventory(tmp_path / "non_existent.yaml")
    loaded = inv.load(); assert loaded is False; assert len(inv.data.inventory_parts) == 0

# Add other load tests (empty, invalid yaml, validation error)

def test_inventory_save_load_cycle(tmp_path, sample_inventory_item_obj):
    inv = Inventory(tmp_path / "saveload.yaml")
    item2 = sample_inventory_item_obj.model_copy(update={'part_id': 'INV002', 'value': '100nF'})
    assert inv.add_part(sample_inventory_item_obj) is True; assert inv.add_part(item2) is True
    assert inv.save() is True
    inv_reloaded = Inventory(tmp_path / "saveload.yaml")
    assert inv_reloaded.load() is True; assert len(inv_reloaded.data.inventory_parts) == 2
    assert inv_reloaded.get_part("INV002").value == "100nF"

def test_inventory_add_part_duplicate(sample_inventory): # Uses fixture
    count = len(sample_inventory.data.inventory_parts)
    dup = InventoryItem(part_id="INV_TEST001", description="Dup", footprint="Lib:FP")
    assert sample_inventory.add_part(dup) is False; assert len(sample_inventory.data.inventory_parts) == count

def test_inventory_get_next_part_id(sample_inventory):
    assert sample_inventory.get_next_part_id() == "INV001"
    empty_inv = Inventory("dummy"); assert empty_inv.get_next_part_id() == "INV001"

def test_inventory_find_match(sample_inventory):
    c_mpn = Component(ref="/R1", mpn="RC0805JR-0710KL"); assert sample_inventory.find_match(c_mpn).part_id == "INV_TEST001"
    c_vp = Component(ref="/R2", value="10k", package="0805"); assert sample_inventory.find_match(c_vp) is None  # Should not match
    c_none = Component(ref="/C1", value="1uF"); assert sample_inventory.find_match(c_none) is None
    c_case = Component(ref="/R3", value="10K", package="0805"); assert sample_inventory.find_match(c_case) is None  # Should not match

