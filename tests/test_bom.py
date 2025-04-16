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


from data_models.bom_data import BoM # Assumes BoM class is here
from data_models.component import Component

@pytest.fixture
def sample_csv_bom(tmp_path):
    content = """Reference,Value,Footprint,Datasheet,Manufacturer,Part Number
C1,100nF,Capacitor_SMD:C_0603_1608Metric,~,~,
R1,10k,Resistor_SMD:R_0805_2012Metric,~,Yageo,RC0805FR-0710KL
U1,NE555P,Package_SO:SOIC-8_3.9x4.9mm_P1.27mm,http://example.com,TI,NE555P
"""
    file = tmp_path / "bom.csv"; file.write_text(content); return file

@pytest.fixture
def sample_xml_bom(tmp_path):
    content = """<?xml version="1.0" encoding="utf-8"?><export><components>
<comp ref="C1"><value>10uF</value><footprint>Cap:C_0805</footprint></comp>
<comp ref="R3"><value>1k</value><footprint>Res:R_0603</footprint><fields><field name="MPN">ABC-123</field></fields></comp>
</components></export>"""
    file = tmp_path / "bom.xml"; file.write_text(content); return file

def test_bom_load_kicad_csv(tmp_path, sample_csv_bom):
    bom = BoM(tmp_path / "canonical.yaml")
    assert bom.load_from_kicad_export(sample_csv_bom) is True
    assert len(bom.data.components) == 2 # R1, U1 (C1 is not loaded due to missing/invalid data)
    r1 = bom.get_component("R1"); u1 = bom.get_component("U1")
    assert r1.value == "10k"; assert r1.footprint == "Resistor_SMD:R_0805_2012Metric"
    assert u1.value == "NE555P"; assert u1.mpn == "NE555P"; assert str(u1.datasheet_url) == "http://example.com/"

def test_bom_load_kicad_xml(tmp_path, sample_xml_bom):
    bom = BoM(tmp_path / "canonical.yaml")
    assert bom.load_from_kicad_export(sample_xml_bom) is True
    assert len(bom.data.components) == 2
    r3 = bom.get_component("R3")
    assert r3.value == "1k"; assert r3.mpn == "ABC-123"

# Add tests for load_canonical, save_canonical, get_component, update_component

