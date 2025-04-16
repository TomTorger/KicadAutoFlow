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

# --- Fixtures ---

@pytest.fixture(scope="session")
def project_root_dir():
    """Provides the calculated repository root directory."""
    return Path(__file__).parent.parent

@pytest.fixture
def temp_test_dir(tmp_path):
    """Creates a temporary directory managed by pytest."""
    return tmp_path

@pytest.fixture(scope="session")
def mock_config_obj(tmp_path_factory):
    """Provides a basic, default AppConfig object for tests, with a real prompts file."""
    print("Creating mock AppConfig fixture")
    tmp_dir = tmp_path_factory.mktemp("mock_config")
    prompts_path = tmp_dir / "prompts.yaml"
    prompts_path.write_text("""
suggest_footprint: Suggest: {package_desc}
analyze_component_image: Analyze image
check_pin_count: Check pins: {expected_pin_count}
check_package_match: Check pkg: {package}
""")
    conf = AppConfig(
        kicad_paths={'standard_symbol_libs': [], 'standard_footprint_libs': []},
        prompts_file=str(prompts_path),
        health_rules=HealthRules(points=HealthPoints(), thresholds={'needs_review_below': 4.0})
    )
    conf.prompts = {'suggest_footprint': 'Suggest: {package_desc}', 'analyze_component_image': 'Analyze image', 'check_pin_count': 'Check pins: {expected_pin_count}', 'check_package_match': 'Check pkg: {package}'}
    # Patch for utils/test_kicad_utils.py
    return conf


@pytest.fixture
def sample_component_obj():
    """Provides a basic Component object."""
    return Component(ref="/R1", value="10k", description="Test Resistor", qty=1)

@pytest.fixture
def sample_inventory_item_obj():
    """Provides a basic InventoryItem object."""
    return InventoryItem(
        part_id="INV_TEST001",
        description="Test Inv Item 4k7 0603",
        value="4k7",
        package="0603",
        footprint="Resistor_SMD:R_0603_1608Metric",
        footprint_source="manual",
        mpn="RC0805JR-0710KL",  # Added MPN for matching test
        quantity=100
    )

# --- Mocked Clients (using MagicMock for flexibility) ---

@pytest.fixture
def mock_llm_capability(mocker) -> LLMCapability:
    """Provides a mocked LLM Capability using MagicMock."""
    mock = mocker.MagicMock(spec=LLMCapability)
    mock.suggest_footprint.return_value = None
    mock.analyze_image_for_component.return_value = None
    mock.check_datasheet_consistency.return_value = {'notes': 'LLM Check Mocked'}
    mock.get_default_text_model_name.return_value = "mock-text-model"
    return mock

@pytest.fixture
def mock_fp_api_capability(mocker) -> FootprintAPICapability:
    """Provides a mocked Footprint API Capability using MagicMock."""
    mock = mocker.MagicMock(spec=FootprintAPICapability)
    mock.search_by_mpn.return_value = [] # Default to no results
    mock.download_asset.return_value = None # Default to download failure
    return mock

# --- Mocked Managers ---

@pytest.fixture
def mock_library_manager(mocker, mock_config_obj, project_root_dir):
    """Provides a LibraryManager instance, mocking filesystem checks."""
    mock = mocker.MagicMock(spec=LibraryManager)
    mock.footprint_exists.return_value = False # Default mock behavior
    mock.symbol_definition_exists.return_value = (False, False, False) # lib_found, parsed_ok, def_found
    mock.get_footprint_details.return_value = ParsedFootprintData(errors=["Mocked: Details not parsed"])
    mock.project_root = project_root_dir
    mock.standard_footprint_libs_paths = [Path(p) for p in mock_config_obj.kicad_paths.standard_footprint_libs]
    mock.project_footprint_dir = project_root_dir / "libs"
    mock.project_symbol_dir = project_root_dir / "libs"
    return mock

@pytest.fixture
def mock_datasheet_manager(mocker, mock_config_obj, project_root_dir):
    """Provides a DatasheetManager instance, mocking download."""
    mock = mocker.MagicMock(spec=DatasheetManager)
    mock.check_local.return_value = False
    mock.download.return_value = False
    mock.extract_text.return_value = None
    mock.project_root = project_root_dir
    mock.datasheet_dir = project_root_dir / "docs" / "datasheets"
    # Mock internal helper to avoid actual download attempts within check/download methods
    mocker.patch('utils.file_utils.DatasheetManager._download_file_util', return_value=False)
    return mock

@pytest.fixture
def mock_health_calculator(mocker, mock_config_obj):
    """Provides a mocked HealthCalculator."""
    mock = mocker.MagicMock(spec=HealthCalculator)
    mock.calculate.return_value = HealthScore(score=5.0, max_possible=10.0, details=["Mock Score"]).model_dump() # Return dict
    # Mock the max score property used by engine/tests
    type(mock).max_possible_score = mocker.PropertyMock(return_value=10.0)
    return mock


# --- Sample Data Files/Instances ---

@pytest.fixture
def sample_inventory(tmp_path, sample_inventory_item_obj):
    """Provides an Inventory instance loaded from a temporary file."""
    inv_file = tmp_path / "test_inventory.yaml"
    # Ensure the InventoryItem is converted to a plain dict for PyYAML dump
    inv_data = {'inventory_parts': [sample_inventory_item_obj.model_dump(mode='json')]}
    with open(inv_file, 'w', encoding='utf-8') as f:
        yaml.dump(inv_data, f)
    inv = Inventory(inv_file)
    inv.load()
    return inv

@pytest.fixture
def sample_bom(tmp_path, sample_component_obj):
    """Provides a BoM instance loaded from a temporary canonical file."""
    bom_file = tmp_path / "test_bom.yaml"
    comp2 = Component(ref="/C1", value="100nF", description="Bypass Cap", qty=1, footprint="Cap:C_0603")
    # Convert components to plain dicts for PyYAML dump
    bom_data = {'components': [sample_component_obj.model_dump(mode='json'), comp2.model_dump(mode='json')]}
    with open(bom_file, 'w', encoding='utf-8') as f:
        yaml.dump(bom_data, f)
    bom = BoM(bom_file)
    bom.load_canonical()
    return bom

@pytest.fixture(scope='session')
def sample_pdf_path_fixture(project_root_dir):
    """Provides the path to the sample PDF in tests/data"""
    path = project_root_dir / "tests" / "data" / "sample.pdf"
    if not path.exists():
         # Create the tiny valid PDF if it doesn't exist
         pdf_content = b'%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 60 80]/Resources<<>>/Contents 4 0 R>>endobj 4 0 obj<</Length 35>>stream\nBT /F1 12 Tf 10 70 Td (Test PDF Text) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000111 00000 n \n0000000194 00000 n \ntrailer<</Size 5/Root 1 0 R>>\nstartxref\n270\n%%EOF'
         path.parent.mkdir(exist_ok=True)
         path.write_bytes(pdf_content)
         print(f"Created dummy PDF at {path}")
    return path

@pytest.fixture(scope='session')
def temp_kicad_libs_fixture(project_root_dir):
    """Creates a temporary directory simulating KiCad libs."""
    # Using a fixed temp dir name within tests for easier debugging? Or use pytest tmp_path_factory
    libs_dir = project_root_dir / "tests" / "temp_kicad_libs_session"
    fp_libs = libs_dir / "footprints"
    sym_libs = libs_dir / "symbols"

    shutil.rmtree(libs_dir, ignore_errors=True) # Clean up from previous runs

    # Create sample footprint lib/file
    fp_lib_dir = fp_libs / "Resistor_SMD.pretty"
    fp_lib_dir.mkdir(parents=True, exist_ok=True)
    # Use robust S-expression for KiCad 6/7 footprint with 2 pads
    fp_content = '''(module R_0805_2012Metric (layer F.Cu) (tedit 0)
  (fp_text reference REF** (at 0 0.5) (layer F.SilkS))
  (fp_text value VALUE (at 0 -0.5) (layer F.Fab))
  (pad 1 smd rect (at -1.1 0) (size 0.95 1.3) (layers F.Cu F.Paste F.Mask))
  (pad 2 smd rect (at 1.1 0) (size 0.95 1.3) (layers F.Cu F.Paste F.Mask))
)'''
    (fp_lib_dir / "R_0805_2012Metric.kicad_mod").write_text(fp_content, encoding='utf-8')
    # Create sample symbol lib/file
    sym_libs.mkdir(parents=True, exist_ok=True)
    (sym_libs / "Device.kicad_sym").write_text('(kicad_symbol_lib (version 20211014) (generator kicad) (symbol "R" (power) (pin_names (offset 0)) (pin_numbers (offset 0)) (property "Reference" "R" (at 0 1.27 0) (effects (font (size 1.27 1.27)))) (property "Value" "R" (at 0 -1.27 0) (effects (font (size 1.27 1.27)))) (symbol "R_0_1" (rectangle (start -1.016 -2.54) (end 1.016 2.54) (stroke (width 0.254) (type default)) (fill (type none)))) (symbol "R_1_1" (pin passive line (at 0 3.81 270) (length 1.27) (name "~") (number "1")) (pin passive line (at 0 -3.81 90) (length 1.27) (name "~") (number "2")))))', encoding='utf-8')
    print(f"Created temp KiCad libs at {libs_dir}")

    yield {'footprint': fp_libs, 'symbol': sym_libs} # Provide paths to tests

    # Teardown (optional, pytest usually handles temp dirs)
    # shutil.rmtree(libs_dir, ignore_errors=True)
    # print(f"Cleaned up temp KiCad libs at {libs_dir}")


