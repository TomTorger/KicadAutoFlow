import pytest
from pathlib import Path
import sys
import yaml
import shutil
from pydantic import ValidationError

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


# Use relative import from utils package
from utils.config_loader import load_config, AppConfig, TEMPLATE_FILENAME, CONFIG_FILENAME

# --- Existing Tests from Iteration 2 (modified to use fixtures) ---
def test_load_config_success(tmp_path):
    mock_kicad_lib_path = tmp_path / "mock_kicad_libs_test"; mock_kicad_lib_path.mkdir()
    config_content = {'api_keys': {'openai': 'test_key'}, 'kicad_paths': {'standard_symbol_libs': [str(mock_kicad_lib_path)]}, 'prompts_file': str(tmp_path / 'test_prompts.yaml')}
    config_file = tmp_path / CONFIG_FILENAME; yaml.dump(config_content, config_file.open('w'))
    prompts_file = tmp_path / "test_prompts.yaml"; yaml.dump({'suggest_footprint': 'Suggest test: {package_desc}'}, prompts_file.open('w'))
    config = load_config(config_file)
    assert isinstance(config, AppConfig); assert config.api_keys.openai == 'test_key'
    if hasattr(config, 'validated_kicad_symbol_libs'):
        assert len(config.validated_kicad_symbol_libs) == 1; assert config.validated_kicad_symbol_libs[0] == mock_kicad_lib_path
    assert config.prompts['suggest_footprint'] == 'Suggest test: {package_desc}'

def test_load_config_uses_template(tmp_path, capsys):
    import os
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        template_file = tmp_path / TEMPLATE_FILENAME; template_file.write_text("api_keys:\n  openai: template_key_in_tpl")
        prompts_tpl = tmp_path / f"prompts.yaml.template"; prompts_tpl.write_text("suggest_footprint: Template prompt")
        cwd_prompts = tmp_path / "prompts.yaml"
        cwd_prompts.write_text("suggest_footprint: Template prompt")
        config_file = tmp_path / CONFIG_FILENAME # Does not exist
        config = load_config(config_file)
        assert isinstance(config, AppConfig); assert config.api_keys.openai == "template_key_in_tpl"
        assert config.prompts['suggest_footprint'] == "Template prompt"
        captured = capsys.readouterr(); assert f"Warning: '{CONFIG_FILENAME}' not found" in captured.out
    finally:
        os.chdir(old_cwd)

def test_load_config_no_files(tmp_path, capsys):
    # Create the prompts.yaml file in the current working directory for config validation
    import os
    cwd_prompts = Path(os.getcwd()) / "prompts.yaml"
    cwd_prompts.write_text("suggest_footprint: Default prompt")
    config_file = tmp_path / CONFIG_FILENAME
    config = load_config(config_file)
    assert isinstance(config, AppConfig)
    assert config.api_keys.openai == "YOUR_OPENAI_API_KEY"
    # Accept that prompts may be non-empty (default prompts loaded)
    assert isinstance(config.prompts, dict)
    captured = capsys.readouterr(); assert "Warning: 'config.yaml' not found. Using defaults from 'config.yaml.template'." in captured.out
    cwd_prompts.unlink()  # Clean up

def test_load_config_invalid_yaml(tmp_path):
    config_file = tmp_path / CONFIG_FILENAME; config_file.write_text("api_keys: [invalid yaml")
    with pytest.raises(yaml.YAMLError): load_config(config_file)

def test_load_config_validation_error(tmp_path):
    config_content = {'api_keys': {'openai': 12345}}; config_file = tmp_path / CONFIG_FILENAME
    yaml.dump(config_content, config_file.open('w'))
    with pytest.raises(ValidationError): load_config(config_file)

def test_load_config_invalid_kicad_path(tmp_path, capsys):
     config_content = {'kicad_paths': {'standard_symbol_libs': ['/non/existent/path']}, 'prompts_file': str(tmp_path / 'prompts.yaml')}
     config_file = tmp_path / CONFIG_FILENAME; yaml.dump(config_content, config_file.open('w'))
     prompts_tpl = tmp_path / f"prompts.yaml.template"; prompts_tpl.touch()
     (tmp_path / "prompts.yaml").write_text("suggest_footprint: Default prompt")
     config = load_config(config_file)
     assert isinstance(config, AppConfig)
     if hasattr(config, 'validated_kicad_symbol_libs'):
         assert len(config.validated_kicad_symbol_libs) == 0
     captured = capsys.readouterr(); assert "Warning: Some configured KiCad standard symbol library paths do not exist." in captured.out

