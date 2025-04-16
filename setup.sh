#!/bin/bash

echo "Creating inventory_manager.py with the Inventory class..."

# --- inventory_manager.py ---
cat << 'EOF' > inventory_manager.py
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


    def find_match(self, bom_comp_data: Dict) -> Optional[InventoryItem]:
        """Tries to find a suitable match in inventory for BoM component data (dict).
           Returns the best match found based on criteria (MPN > Value+Package).
        """
        best_match: Optional[InventoryItem] = None
        match_level = 0 # 3=MPN, 2=Value+Package

        bom_mpn = bom_comp_data.get('mpn')
        bom_value = bom_comp_data.get('value')
        bom_package = bom_comp_data.get('package')

        # 1. MPN Match (highest confidence)
        if bom_mpn and match_level < 3:
            bom_mpn_norm = bom_mpn.strip().lower()
            for part in self.data.inventory_parts:
                if part.mpn and part.mpn.strip().lower() == bom_mpn_norm:
                    best_match = part; match_level = 3; break

        # 2. Value + Package Match (medium confidence)
        if bom_value and bom_package and match_level < 2:
            bom_val_norm = bom_value.strip().lower()
            bom_pkg_norm = bom_package.strip().lower()
            # Find all potential matches at this level
            vp_matches = [
                part for part in self.data.inventory_parts
                if part.value and part.package and
                   part.value.strip().lower() == bom_val_norm and
                   part.package.strip().lower() == bom_pkg_norm
            ]
            if vp_matches:
                 # Prefer matches that also have an MPN defined in inventory
                 mpn_matches = [p for p in vp_matches if p.mpn]
                 if mpn_matches:
                      best_match = mpn_matches[0] # Pick first one with MPN
                 else:
                      best_match = vp_matches[0] # Pick first one without MPN
                 match_level = 2

        # print(f"Match search for {bom_comp_data.get('ref', 'N/A')}: Found {best_match.part_id if best_match else 'None'} at level {match_level}")
        return best_match

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

EOF

echo "Created inventory_manager.py."

# --- Fix Imports ---
echo "Attempting to fix import statements..."

CONTEST_FILE="tests/conftest.py"
TEST_INV_FILE="tests/test_inventory.py"
INV_TOOLS_FILE="adk_tools/inventory_tools.py" # Also likely needs this import

# Fix conftest.py
if [ -f "$CONTEST_FILE" ]; then
    if grep -q "^from inventory import Inventory" "$CONTEST_FILE"; then
        sed -i 's#^from inventory import Inventory#from inventory_manager import Inventory#' "$CONTEST_FILE" || echo " sed failed for $CONTEST_FILE"
        echo "Updated import in $CONTEST_FILE"
    elif ! grep -q "^from inventory_manager import Inventory" "$CONTEST_FILE"; then
         # Insert if neither exists (might need adjustment based on file content)
         sed -i '/^from data_models.bom_data import BoM/a from inventory_manager import Inventory' "$CONTEST_FILE" || echo " sed insert failed for $CONTEST_FILE"
         echo "Inserted import in $CONTEST_FILE"
    fi
else
    echo "Warning: $CONTEST_FILE not found."
fi

# Fix test_inventory.py
if [ -f "$TEST_INV_FILE" ]; then
    if grep -q "^from inventory import Inventory" "$TEST_INV_FILE"; then
        sed -i 's#^from inventory import Inventory#from inventory_manager import Inventory#' "$TEST_INV_FILE" || echo " sed failed for $TEST_INV_FILE"
        echo "Updated import in $TEST_INV_FILE"
    elif ! grep -q "^from inventory_manager import Inventory" "$TEST_INV_FILE"; then
         sed -i '/^import pytest/a from inventory_manager import Inventory' "$TEST_INV_FILE" || echo " sed insert failed for $TEST_INV_FILE"
         echo "Inserted import in $TEST_INV_FILE"
    fi
else
    echo "Warning: $TEST_INV_FILE not found."
fi

# Fix adk_tools/inventory_tools.py (Placeholder)
if [ -f "$INV_TOOLS_FILE" ]; then
    if ! grep -q "^from inventory_manager import Inventory" "$INV_TOOLS_FILE"; then
         sed -i '/^import google.adk as adk/a from inventory_manager import Inventory # The Inventory manager class' "$INV_TOOLS_FILE" || echo " sed insert failed for $INV_TOOLS_FILE"
         echo "Inserted import in $INV_TOOLS_FILE"
    fi
else
     echo "Warning: $INV_TOOLS_FILE not found."
fi


echo ""
echo "--- Inventory Manager Created & Imports Fixed ---"
echo "Next steps:"
echo "1. Review the new 'inventory_manager.py' file."
echo "2. Review the import changes in 'tests/conftest.py', 'tests/test_inventory.py', and 'adk_tools/inventory_tools.py'."
echo "3. Stage and commit: \`git add . && git commit -m 'Feat: Add Inventory manager class and fix related imports' \`"
echo "4. Re-run \`pytest\` to ensure tests depending on Inventory are collected and pass (or fail correctly)."
echo "------------------------------------------------"