# data_models/inventory_item.py
from pydantic import BaseModel, Field, FilePath, field_validator, ConfigDict
from typing import Optional, Literal, Union
from pathlib import Path

# Reusable path validator (can be moved to utils if used more widely)
def _validate_relative_path_str(v: Optional[str]) -> Optional[str]:
    if v is None: return None
    try:
        p = Path(str(v))
        if p.is_absolute() or '..' in p.parts:
            raise ValueError("Local path must be relative and within project structure")
        return str(p).replace('\\', '/')
    except Exception as e:
        raise ValueError(f"Invalid path format: {v} ({e})")

class InventoryItem(BaseModel):
    """Represents a component type available in local inventory."""
    part_id: str = Field(..., description="Unique ID (e.g., INV001)")
    description: str
    value: Optional[str] = None # Can be helpful for passives
    package: Optional[str] = None
    # Footprint MUST be defined and VERIFIED for inventory items
    footprint: str = Field(..., description="Verified KiCad Footprint (Lib:Name)")
    footprint_source: Literal['manual', 'api_verified', 'kit_ingest_verified', 'unknown'] = 'unknown'
    mpn: Optional[str] = None
    quantity: int = 0 # How many are physically available
    storage_location: Optional[str] = None # e.g., "Bin A3"
    datasheet_local: Optional[str] = None # Relative path
    image_path: Optional[str] = None # Relative path

    model_config = ConfigDict(validate_assignment=True, extra='ignore')

    @field_validator('part_id', 'footprint', 'description')
    @classmethod
    def check_non_empty(cls, v: str, info): # info includes field name
        if not v or not v.strip():
            raise ValueError(f'{info.field_name} cannot be empty')
        return v.strip()

    @field_validator('footprint')
    @classmethod
    def check_footprint_format(cls, v: str):
        if ':' not in v:
            raise ValueError('Footprint must be in Library:Name format')
        return v.strip()

    # Use the validator for path fields
    validate_datasheet_path = field_validator('datasheet_local', mode='before')(_validate_relative_path_str)
    validate_image_path = field_validator('image_path', mode='before')(_validate_relative_path_str)