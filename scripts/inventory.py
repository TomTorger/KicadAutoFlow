from pydantic import BaseModel, Field, ValidationError, FilePath
from typing import List, Dict, Optional, Literal
import yaml
from pathlib import Path
import pandas as pd

# Assuming component_base.py is in the same directory level or PYTHONPATH includes scripts/
from component_base import Component

class InventoryComponent(Component):
    """Represents a component stored in the local inventory."""
    part_id: str # Unique ID within the inventory file, e.g., "INV001"
    quantity: Optional[int] = None # How many are physically available
    storage_location: Optional[str] = None # e.g., "Bin A3", "Resistor Kit Box"
    image_path: Optional[FilePath] = None # Path relative to project root (e.g., docs/inventory_images/...)
    footprint_source: Literal['manual', 'api', 'llm', 'kit_ingest_verified', 'unknown'] = 'unknown'

    # Override fields that MUST be present and verified for inventory items
    footprint: str # Non-optional and assumed verified for inventory parts

    class Config:
        arbitrary_types_allowed = True
        validate_assignment = True

class InventoryData(BaseModel):
    """Pydantic model for the structure of inventory.yaml."""
    inventory_parts: List[InventoryComponent] = Field(default_factory=list)

class Inventory:
    """Manages the inventory of components."""
    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path)
        self.data = InventoryData()

    def load(self):
        """Loads inventory from the YAML file."""
        if not self.file_path.exists():
            print(f"Inventory file '{self.file_path}' not found. Starting with empty inventory.")
            self.data = InventoryData()
            return False

        try:
            with open(self.file_path, 'r') as f:
                raw_data = yaml.safe_load(f)
            if raw_data and 'inventory_parts' in raw_data:
                 # Use Pydantic to parse and validate the list
                 self.data = InventoryData(inventory_parts=raw_data['inventory_parts'])
                 print(f"Loaded {len(self.data.inventory_parts)} items from '{self.file_path}'.")
                 return True
            else:
                print(f"Inventory file '{self.file_path}' is empty or invalid format. Starting empty.")
                self.data = InventoryData()
                return False
        except yaml.YAMLError as e:
            print(f"Error parsing inventory YAML file '{self.file_path}': {e}")
            self.data = InventoryData() # Reset to empty on error
            return False
        except ValidationError as e:
            print(f"Inventory data validation error in '{self.file_path}':")
            print(e)
            self.data = InventoryData() # Reset to empty on error
            return False
        except Exception as e:
             print(f"Error loading inventory from '{self.file_path}': {e}")
             self.data = InventoryData()
             return False

    def save(self):
        """Saves the current inventory to the YAML file."""
        try:
            # Use Pydantic's dict() method for clean export respecting defaults etc.
            export_data = self.data.model_dump(exclude_none=True) # Exclude fields that are None
            with open(self.file_path, 'w') as f:
                yaml.dump(export_data, f, sort_keys=False, indent=2)
            print(f"Saved {len(self.data.inventory_parts)} items to '{self.file_path}'.")
            return True
        except Exception as e:
            print(f"Error saving inventory to '{self.file_path}': {e}")
            return False

    def add_part(self, part: InventoryComponent):
        """Adds a new part to the inventory, checking for duplicate part_id."""
        if any(p.part_id == part.part_id for p in self.data.inventory_parts):
            print(f"Warning: Part with ID '{part.part_id}' already exists. Skipping add.")
            return False
        self.data.inventory_parts.append(part)
        return True

    def get_part(self, part_id: str) -> Optional[InventoryComponent]:
        """Retrieves a part by its unique inventory ID."""
        for part in self.data.inventory_parts:
            if part.part_id == part_id:
                return part
        return None

    def find_match(self, bom_comp: Component) -> Optional[InventoryComponent]:
        """Tries to find a suitable match in inventory for a BoM component.
           Returns the best match found based on criteria (MPN > Value+Package > Desc).
           (Simple implementation - can be made more sophisticated)
        """
        best_match: Optional[InventoryComponent] = None
        match_level = 0 # 3=MPN, 2=Value+Package, 1=Desc

        # Check based on MPN first (highest confidence)
        if bom_comp.mpn and match_level < 3:
            for part in self.data.inventory_parts:
                if part.mpn and part.mpn == bom_comp.mpn:
                    best_match = part
                    match_level = 3
                    break # Found exact MPN match

        # Check based on Value + Package (medium confidence)
        if bom_comp.value and bom_comp.package and match_level < 2:
            for part in self.data.inventory_parts:
                # Need case-insensitive compare? Normalization?
                if (part.value and part.value.lower() == bom_comp.value.lower() and
                    part.package and part.package.lower() == bom_comp.package.lower()):
                     best_match = part
                     match_level = 2
                     # Don't break, might find MPN match later if this loop was entered first

        # Check based on Description (lowest confidence - heuristic)
        # Implement simple substring check or more advanced matching if needed
        # if bom_comp.description and match_level < 1:
        #     for part in self.data.inventory_parts:
        #         if part.description and bom_comp.description.lower() in part.description.lower():
        #              best_match = part
        #              match_level = 1

        # print(f"Match search for {bom_comp.ref or bom_comp.description}: Found {best_match.part_id if best_match else 'None'} at level {match_level}")
        return best_match

    def to_dataframe(self) -> pd.DataFrame:
        """Converts inventory data to a pandas DataFrame."""
        if not self.data.inventory_parts:
            return pd.DataFrame(columns=['part_id', 'description', 'value', 'package', 'footprint', 'quantity', 'storage_location', 'mpn']) # etc.
        # Pydantic v2 uses model_dump
        dict_list = [part.model_dump() for part in self.data.inventory_parts]
        return pd.DataFrame(dict_list)

    def get_next_part_id(self) -> str:
        """Generates the next sequential inventory ID (e.g., INV001 -> INV002)."""
        if not self.data.inventory_parts:
            return "INV001"
        max_id = 0
        for part in self.data.inventory_parts:
            if part.part_id.startswith("INV"):
                try:
                    num = int(part.part_id[3:])
                    if num > max_id:
                        max_id = num
                except ValueError:
                    continue # Ignore non-standard IDs
        return f"INV{max_id + 1:03d}"

