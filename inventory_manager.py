from pydantic import BaseModel, Field, ValidationError
from typing import List, Dict, Optional, Union
import yaml
from pathlib import Path
import pandas as pd

# Use relative import from data_models package
from data_models.inventory_item import InventoryItem

class InventoryData(BaseModel):
    """Internal Pydantic model for validating the structure of inventory.yaml."""
    inventory_parts: List[InventoryItem] = Field(default_factory=list)

class Inventory:
    """Manages the inventory of components stored in inventory.yaml."""
    def __init__(self, file_path: Union[str, Path], project_root: Path = Path('.')):
        # Ensure file_path is relative to project_root if not absolute
        self.file_path = Path(file_path)
        if not self.file_path.is_absolute():
             self.file_path = (project_root / self.file_path).resolve()
        self.data = InventoryData()
        self.project_root = project_root # Store for potential relative path calculations

    def load(self) -> bool:
        """Loads inventory from the YAML file."""
        if not self.file_path.exists():
            print(f"INFO: Inventory file '{self.file_path}' not found. Starting empty inventory.")
            self.data = InventoryData()
            return False

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                raw_data = yaml.safe_load(f)
            if raw_data and 'inventory_parts' in raw_data:
                 # Use Pydantic to parse and validate the list
                 self.data = InventoryData(inventory_parts=raw_data['inventory_parts'])
                 print(f"Loaded {len(self.data.inventory_parts)} items from '{self.file_path}'.")
                 return True
            else:
                 # Handle case where file exists but is empty or has no 'inventory_parts' key
                 if raw_data is None: print(f"INFO: Inventory file '{self.file_path}' is empty. Starting empty.")
                 else: print(f"INFO: Inventory file '{self.file_path}' missing 'inventory_parts' key or invalid format.")
                 self.data = InventoryData()
                 return False
        except yaml.YAMLError as e: print(f"ERROR parsing inventory YAML '{self.file_path}': {e}"); self.data = InventoryData(); return False
        except ValidationError as e: print(f"ERROR validating inventory data '{self.file_path}':\n{e}"); self.data = InventoryData(); return False
        except Exception as e: print(f"ERROR loading inventory from '{self.file_path}': {e}"); self.data = InventoryData(); return False

    def save(self) -> bool:
        """Saves the current inventory to the YAML file."""
        try:
            # Use Pydantic's model_dump for clean export
            export_data = self.data.model_dump(mode='json', exclude_none=True)
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                yaml.dump(export_data, f, sort_keys=False, indent=2, default_flow_style=False, allow_unicode=True)
            print(f"Saved {len(self.data.inventory_parts)} items to '{self.file_path}'.")
            return True
        except Exception as e:
            print(f"ERROR saving inventory to '{self.file_path}': {e}")
            return False

    def add_part(self, part: InventoryItem):
        """Adds a new part, checking for duplicate part_id."""
        if any(p.part_id == part.part_id for p in self.data.inventory_parts if p.part_id): # Check existing part_id
            print(f"Warning: Part with ID '{part.part_id}' already exists. Skipping add.")
            return False
        self.data.inventory_parts.append(part)
        return True

    def get_part(self, part_id: str) -> Optional[InventoryItem]:
        """Retrieves a part by its unique inventory ID."""
        return next((part for part in self.data.inventory_parts if part.part_id == part_id), None)


    def find_match(self, bom_comp_data) -> Optional[InventoryItem]:
        """Tries to find a suitable match in inventory for BoM component data (dict or Component object)."""
        # Accept both dict and Component object
        if hasattr(bom_comp_data, 'mpn'):
            bom_mpn = getattr(bom_comp_data, 'mpn', None)
            bom_value = getattr(bom_comp_data, 'value', None)
            bom_package = getattr(bom_comp_data, 'package', None)
        else:
            bom_mpn = bom_comp_data.get('mpn')
            bom_value = bom_comp_data.get('value')
            bom_package = bom_comp_data.get('package')
        for item in self.data.inventory_parts:
            if bom_mpn and item.mpn and bom_mpn.lower() == item.mpn.lower():
                return item
            if bom_value and item.value and bom_value.lower() == item.value.lower():
                if bom_package and item.package and bom_package.lower() == item.package.lower():
                    return item
        return None

    def to_dataframe(self) -> pd.DataFrame:
        """Converts inventory data to a pandas DataFrame."""
        if not self.data.inventory_parts:
            return pd.DataFrame(columns=list(InventoryItem.model_fields.keys()))
        dict_list = [part.model_dump(mode='json') for part in self.data.inventory_parts]
        return pd.DataFrame(dict_list)

    def get_next_part_id(self) -> str:
        """Generates the next sequential inventory ID (e.g., INV001 -> INV002)."""
        if not self.data.inventory_parts: return "INV001"
        max_id = 0
        for part in self.data.inventory_parts:
            if part.part_id and part.part_id.startswith("INV"):
                try: num = int(part.part_id[3:])
                except (ValueError, IndexError): continue
                if num > max_id: max_id = num
        return f"INV{max_id + 1:03d}"

