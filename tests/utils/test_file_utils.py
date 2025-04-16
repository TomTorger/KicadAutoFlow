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


from pathlib import Path
import requests
import shutil
# Use relative imports
from utils.file_utils import DatasheetManager
from data_models.component import Component

def test_datasheet_manager_init(tmp_path, mock_config_obj):
    ds_dir = tmp_path / "docs" / "datasheets"
    assert not ds_dir.exists()
    manager = DatasheetManager(mock_config_obj, project_root=tmp_path)
    assert ds_dir.is_dir()

def test_datasheet_manager_get_local_path(tmp_path, mock_config_obj):
    manager = DatasheetManager(mock_config_obj, project_root=tmp_path)
    comp_mpn = Component(ref="/U1", mpn="SN/74LS00N") # Test sanitizing
    comp_ref = Component(ref="/R10:Input", value="4k7_1%")
    comp_local = Component(ref="/C1", datasheet_local="docs/datasheets/my cap.pdf") # Test space
    expected_mpn = tmp_path / "docs" / "datasheets" / "SN_74LS00N.pdf"
    expected_ref = tmp_path / "docs" / "datasheets" / "R10_Input_4k7_1%.pdf"
    expected_local = tmp_path / "docs" / "datasheets" / "my cap.pdf"
    assert manager._get_local_path(comp_mpn) == expected_mpn
    assert manager._get_local_path(comp_ref) == expected_ref
    assert manager._get_local_path(comp_local) == expected_local

def test_datasheet_manager_check_local(tmp_path, mock_config_obj):
     manager = DatasheetManager(mock_config_obj, project_root=tmp_path)
     comp = Component(ref="/R1", mpn="TEST_MPN_LOCAL")
     local_path = manager._get_local_path(comp)
     assert manager.check_local(comp) is False; assert comp.datasheet_local is None
     local_path.parent.mkdir(parents=True, exist_ok=True); local_path.touch() # Create file
     assert manager.check_local(comp) is True
     assert comp.datasheet_local == str(local_path.relative_to(tmp_path)).replace('\\','/')

def test_datasheet_manager_download_success(tmp_path, mock_config_obj, mocker):
     manager = DatasheetManager(mock_config_obj, project_root=tmp_path)
     comp = Component(ref="/U2", mpn="TEST_DL", datasheet_url="http://example.com/test.pdf")
     local_path = manager._get_local_path(comp)
     mock_download = mocker.patch.object(manager, '_download_file_util', return_value=True)
     assert manager.download(comp) is True
     assert comp.datasheet_local == str(local_path.relative_to(tmp_path)).replace('\\','/')
     mock_download.assert_called_once_with(str(comp.datasheet_url), local_path)

def test_datasheet_manager_download_fail(tmp_path, mock_config_obj, mocker):
     manager = DatasheetManager(mock_config_obj, project_root=tmp_path)
     comp = Component(ref="/U3", mpn="TEST_FAIL", datasheet_url="http://example.com/fail.pdf")
     mock_download = mocker.patch.object(manager, '_download_file_util', return_value=False)
     assert manager.download(comp) is False; assert comp.datasheet_local is None
     mock_download.assert_called_once()

def test_datasheet_manager_extract_text_success(tmp_path, mock_config_obj, sample_pdf_path_fixture):
     manager = DatasheetManager(mock_config_obj, project_root=tmp_path)
     comp = Component(ref="/T1", mpn="SamplePDF")
     expected_path = manager._get_local_path(comp)
     shutil.copy(sample_pdf_path_fixture, expected_path) # Copy sample to expected location
     comp.datasheet_local = str(expected_path.relative_to(tmp_path)).replace('\\','/') # Set relative path
     text = manager.extract_text(comp)
     assert text is not None; assert "Test PDF Text" in text # Check content

