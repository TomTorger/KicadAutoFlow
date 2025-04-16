# data_models/inventory_item.py
from pydantic import BaseModel, Field, FilePath, field_validator, model_validator, ConfigDict
from typing import Optional, Literal, Union, Dict, Any
from pathlib import Path
from datetime import datetime

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
    # Footprint information (optional)
    footprint: Optional[str] = None
    footprint_source: Optional[str] = None
    mpn: Optional[str] = None
    quantity: int = 0 # How many are physically available
    storage_location: Optional[str] = None # e.g., "Bin A3"
    datasheet_local: Optional[str] = None # Relative path
    image_path: Optional[str] = None # Relative path
    mounting_type: Optional[str] = None  # 'Surface Mount', 'Through-Hole', or 'Unknown'
    analysis_confidence: Optional[str] = None  # AI confidence level: "High", "Medium", "Low"

    model_config = ConfigDict(validate_assignment=True, extra='ignore')

    @model_validator(mode='before')
    @classmethod
    def set_default_date(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Set default added_date if not present."""
        if isinstance(values, dict) and 'added_date' not in values:
            values['added_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return values

    @field_validator('part_id', 'description')
    @classmethod
    def check_non_empty(cls, v: str, info): # info includes field name
        if not v or not v.strip():
            raise ValueError(f'{info.field_name} cannot be empty')
        return v.strip()

    # Use the validator for path fields
    validate_datasheet_path = field_validator('datasheet_local', mode='before')(_validate_relative_path_str)
    validate_image_path = field_validator('image_path', mode='before')(_validate_relative_path_str)

    def pretty_print(self) -> str:
        """Format component information for nice display."""
        output = []
        output.append(f"Component ID: {self.part_id}")
        output.append(f"Description:  {self.description}")
        output.append(f"Value:        {self.value}")
        output.append(f"Package:      {self.package}")
        output.append(f"Footprint:    {self.footprint}")
        output.append(f"Mounting:     {self.mounting_type}")
        output.append(f"Quantity:     {self.quantity}")
        
        if self.mpn:
            output.append(f"MPN:          {self.mpn}")
        if self.storage_location:
            output.append(f"Storage:      {self.storage_location}")
        if self.analysis_confidence:
            output.append(f"AI Confidence: {self.analysis_confidence}")
            
        return "\n".join(output)

    def __str__(self) -> str:
        """String representation of the inventory item."""
        return self.pretty_print()
        return f"{self.part_id}: {self.description} {self.value} ({self.package}) - Qty: {self.quantity}"