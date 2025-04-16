from pydantic import BaseModel, Field, FilePath, DirectoryPath, HttpUrl, ValidationError
from typing import List, Dict, Optional, Union, Any
import yaml
import os
from pathlib import Path

# --- Pydantic Models for Config Structure ---

class ApiKeys(BaseModel):
    openai: Optional[str] = None
    google_ai: Optional[str] = None
    snapeda: Optional[str] = None

class KicadPaths(BaseModel):
    standard_symbol_libs: List[Union[DirectoryPath, str]] = [] # Allow str initially
    standard_footprint_libs: List[Union[DirectoryPath, str]] = [] # Allow str initially

class HealthPoints(BaseModel):
    datasheet_local: float = 1.0; datasheet_url: float = 0.5
    footprint_project_manual: float = 2.0; footprint_project_apiverified: float = 1.8
    footprint_project_inventory: float = 1.5; footprint_kicad_lib: float = 1.0
    footprint_inventory_api: float = 0.8; footprint_inventory_llm: float = 0.3
    footprint_bom_apireview: float = 0.2; footprint_bom_llmsuggest: float = 0.1
    footprint_parsed_ok: float = 0.2
    symbol_definition_found: float = 1.0; symbol_library_found: float = 0.2
    mpn_exists: float = 0.5
    # llm_doc_check_ok: float = 0.5 # Example placeholder for optional scores
    # lmm_footprint_check_ok: float = 0.5

class HealthThresholds(BaseModel):
    needs_review_below: float = 4.0

class HealthRules(BaseModel):
    points: HealthPoints = Field(default_factory=HealthPoints)
    thresholds: HealthThresholds = Field(default_factory=HealthThresholds)
    version: str = "1.0" # Default rule version

class LlmSettings(BaseModel):
    default_provider: str = "google_ai"
    default_text_model: str = "gemini-1.5-flash-latest"
    default_vision_model: str = "gemini-1.5-flash-latest"
    gemini_generation_config: Optional[Dict[str, Any]] = None # For temp, top_k etc.

class Defaults(BaseModel):
    quantity_per_kit_value: int = 10

class AppConfig(BaseModel):
    api_keys: ApiKeys = Field(default_factory=ApiKeys)
    kicad_paths: KicadPaths = Field(default_factory=KicadPaths)
    prompts_file: FilePath = Field(default_factory=lambda: Path("prompts.yaml")) # Default prompts file
    health_rules: HealthRules = Field(default_factory=HealthRules)
    llm_settings: LlmSettings = Field(default_factory=LlmSettings)
    defaults: Defaults = Field(default_factory=Defaults)
    prompts: Dict[str, str] = Field(default_factory=dict) # Loaded prompts
    # Add validated paths for KiCad libraries (used by LibraryManager and tests)
    validated_kicad_symbol_libs: List[Path] = Field(default_factory=list)
    validated_kicad_footprint_libs: List[Path] = Field(default_factory=list)
    # Add validation for paths after model initialization if needed

# --- Config Loading Function ---

CONFIG_FILENAME = "config.yaml"
TEMPLATE_FILENAME = "config.yaml.template"

def load_prompts(prompts_file_path: Path) -> Dict[str, str]:
    """Loads prompts from a YAML file."""
    if not prompts_file_path.is_file():
        print(f"Warning: Prompts file '{prompts_file_path}' not found. LLM features may fail.")
        return {}
    try:
        with open(prompts_file_path, 'r', encoding='utf-8') as f:
            prompts = yaml.safe_load(f)
        if isinstance(prompts, dict):
            return prompts
        else:
            print(f"Warning: Prompts file '{prompts_file_path}' does not contain a valid dictionary.")
            return {}
    except yaml.YAMLError as e:
        print(f"Error parsing prompts YAML file '{prompts_file_path}': {e}")
        return {}
    except Exception as e:
        print(f"Error loading prompts file '{prompts_file_path}': {e}")
        return {}


def load_config(config_path: Union[str, Path] = CONFIG_FILENAME) -> AppConfig:
    """Loads the application configuration from config.yaml and associated prompts."""
    config_file = Path(config_path)
    using_template = False
    if not config_file.is_file():
        template_file = Path(TEMPLATE_FILENAME)
        if template_file.is_file():
             print(f"Warning: '{CONFIG_FILENAME}' not found. Using defaults from '{TEMPLATE_FILENAME}'.")
             print(f"Please copy '{TEMPLATE_FILENAME}' to '{CONFIG_FILENAME}' and add your API keys.")
             config_file = template_file
             using_template = True
        else:
            print(f"Error: Neither '{CONFIG_FILENAME}' nor '{TEMPLATE_FILENAME}' found.")
            print("Proceeding with empty/default configuration.")
            return AppConfig() # Return default config

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)
        if raw_config is None:
             print(f"Warning: '{config_file}' is empty. Using default configuration.")
             config = AppConfig()
        else:
             # Validate main config structure
             config = AppConfig(**raw_config)

        # Resolve relative prompts file path from config location
        prompts_file_path_rel = config.prompts_file or Path("prompts.yaml") # Use default if missing
        # Make path relative to the *config file's* directory if it's relative
        if not prompts_file_path_rel.is_absolute():
             prompts_file_path = config_file.parent / prompts_file_path_rel
        else:
             prompts_file_path = prompts_file_path_rel

        # Load prompts from template if using config template, else from specified/default
        prompts_source = prompts_file_path if not using_template else Path(f"{prompts_file_path}.template")
        config.prompts = load_prompts(prompts_source)

        # Validate KiCad paths exist after loading
        valid_sym_paths = [Path(p) for p in config.kicad_paths.standard_symbol_libs if Path(p).is_dir()]
        valid_fp_paths = [Path(p) for p in config.kicad_paths.standard_footprint_libs if Path(p).is_dir()]
        if len(valid_sym_paths) != len(config.kicad_paths.standard_symbol_libs):
             print("Warning: Some configured KiCad standard symbol library paths do not exist.")
        if len(valid_fp_paths) != len(config.kicad_paths.standard_footprint_libs):
             print("Warning: Some configured KiCad standard footprint library paths do not exist.")
        config.kicad_paths.standard_symbol_libs = [str(p) for p in valid_sym_paths]
        config.kicad_paths.standard_footprint_libs = [str(p) for p in valid_fp_paths]
        # Set validated paths for compatibility with LibraryManager/tests
        config.validated_kicad_symbol_libs = valid_sym_paths
        config.validated_kicad_footprint_libs = valid_fp_paths

        return config

    except yaml.YAMLError as e:
        print(f"Error parsing YAML file '{config_file}': {e}"); raise
    except ValidationError as e:
        print(f"Configuration validation error in '{config_file}':\n{e}"); raise
    except Exception as e:
        print(f"Error loading configuration from '{config_file}': {e}"); raise

if __name__ == '__main__':
    try:
        # Create dummy template files if they don't exist for testing
        if not Path(TEMPLATE_FILENAME).exists(): Path(TEMPLATE_FILENAME).touch()
        if not Path("prompts.yaml.template").exists(): Path("prompts.yaml.template").write_text("suggest_footprint: Test prompt")
        config = load_config()
        print("\nConfiguration loaded successfully!")
        print(f"  Loaded {len(config.prompts)} prompts.")
        # Clean up dummies
        # if Path(TEMPLATE_FILENAME).stat().st_size == 0: Path(TEMPLATE_FILENAME).unlink()
        # if Path("prompts.yaml.template").read_text() == "suggest_footprint: Test prompt": Path("prompts.yaml.template").unlink()

    except Exception as e:
        print(f"\nFailed to load configuration during test.")

