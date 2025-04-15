from pydantic import BaseModel, Field, FilePath, DirectoryPath, HttpUrl, ValidationError
from typing import List, Dict, Optional, Union
import yaml
import os
from pathlib import Path

# --- Pydantic Models for Config Structure ---

class ApiKeys(BaseModel):
    openai: Optional[str] = None
    google_ai: Optional[str] = None
    snapeda: Optional[str] = None
    # Add other keys as needed

class KicadPaths(BaseModel):
    standard_symbol_libs: List[DirectoryPath] = []
    standard_footprint_libs: List[DirectoryPath] = []

class HealthPoints(BaseModel):
    datasheet_local: float = 1.0
    datasheet_url: float = 0.5
    footprint_project_manual: float = 2.0
    footprint_project_apiverified: float = 1.8
    footprint_project_inventory: float = 1.5
    footprint_kicad_lib: float = 1.0
    footprint_inventory_api: float = 0.8
    footprint_inventory_llm: float = 0.3
    footprint_bom_apireview: float = 0.2
    footprint_bom_llmsuggest: float = 0.1
    symbol_project_lib: float = 1.0
    symbol_kicad_lib: float = 0.5
    mpn_exists: float = 0.5
    # Optional checks can be added here or handled dynamically

class HealthThresholds(BaseModel):
    needs_review_below: float = 4.0

class HealthRules(BaseModel):
    points: HealthPoints = Field(default_factory=HealthPoints)
    thresholds: HealthThresholds = Field(default_factory=HealthThresholds)

class LlmSettings(BaseModel):
    default_provider: str = "openai"
    default_text_model: str = "gpt-4"
    default_vision_model: str = "gpt-4-vision-preview"
    # Add model specific settings if needed

class Defaults(BaseModel):
    quantity_per_kit_value: int = 10

class AppConfig(BaseModel):
    api_keys: ApiKeys = Field(default_factory=ApiKeys)
    kicad_paths: KicadPaths = Field(default_factory=KicadPaths)
    health_rules: HealthRules = Field(default_factory=HealthRules)
    llm_settings: LlmSettings = Field(default_factory=LlmSettings)
    defaults: Defaults = Field(default_factory=Defaults)

# --- Config Loading Function ---

CONFIG_FILENAME = "config.yaml"
TEMPLATE_FILENAME = "config.yaml.template"

def load_config(config_path: Union[str, Path] = CONFIG_FILENAME) -> AppConfig:
    """Loads the application configuration from config.yaml."""
    config_file = Path(config_path)
    if not config_file.exists():
        template_file = Path(TEMPLATE_FILENAME)
        if template_file.exists():
             print(f"Warning: '{CONFIG_FILENAME}' not found. Using defaults from '{TEMPLATE_FILENAME}'.")
             print(f"Please copy '{TEMPLATE_FILENAME}' to '{CONFIG_FILENAME}' and add your API keys.")
             config_file = template_file
        else:
            print(f"Error: Neither '{CONFIG_FILENAME}' nor '{TEMPLATE_FILENAME}' found.")
            print("Proceeding with empty/default configuration.")
            return AppConfig() # Return default config

    try:
        with open(config_file, 'r') as f:
            raw_config = yaml.safe_load(f)
        if raw_config is None: # Handle empty file case
             print(f"Warning: '{config_file}' is empty. Using default configuration.")
             return AppConfig()
        return AppConfig(**raw_config)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file '{config_file}': {e}")
        raise
    except ValidationError as e:
        print(f"Configuration validation error in '{config_file}':")
        print(e)
        raise
    except Exception as e:
        print(f"Error loading configuration from '{config_file}': {e}")
        raise

if __name__ == '__main__':
    # Example usage: Load config when script is run directly
    try:
        config = load_config()
        print("Configuration loaded successfully!")
        # print("\nAPI Keys (example):", config.api_keys.openai[:5] + "..." if config.api_keys.openai else "Not Set")
        # print("KiCad Symbol Libs:", config.kicad_paths.standard_symbol_libs)
        # print("Health Threshold:", config.health_rules.thresholds.needs_review_below)
    except Exception as e:
        print(f"\nFailed to load configuration.")

