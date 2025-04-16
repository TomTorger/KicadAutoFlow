# adk_tools/inventory_tools.py
import google.adk as adk
from inventory_manager import Inventory # The Inventory manager class
from typing import Dict, Any, Optional, List

# Assume these are imported correctly based on project structure
from data_models.component import Component
from data_models.inventory_item import InventoryItem
from data_models.inventory_item import Inventory # The Inventory manager class

class FindInventoryMatchTool(adk.tools.BaseTool):
    """ADK Tool to find a matching part in the local inventory for a BoM component."""
    def __init__(self, inventory_manager: Inventory, name="FindInventoryMatch", description="Searches local inventory for a component match."):
        super().__init__(name=name, description=description)
        self._inventory = inventory_manager

    async def run_async(self, *, component_data: Dict, tool_context: adk.ToolContext) -> Optional[Dict]:
        """
        Input: component_data (dict representation of a Component).
        Output: dict representation of the matched InventoryItem or None.
        """
        print(f"TOOL: Searching inventory for component: {component_data.get('ref', component_data.get('value'))}")
        try:
            # Recreate Component object to leverage type hints/validation if needed
            # Or just use the dict directly if find_match accepts it
            bom_component = Component(**component_data)
            match = self._inventory.find_match(bom_component)
            if match:
                print(f"  Found inventory match: {match.part_id}")
                # Return the matched item's data as a dictionary
                return match.model_dump(mode='json')
            else:
                print("  No suitable match found in inventory.")
                return None
        except Exception as e:
            print(f"ERROR in FindInventoryMatchTool: {e}")
            return None # Return None on error

class AddVerifiedPartToInventoryTool(adk.tools.BaseTool):
    """ADK Tool to add a verified part definition to inventory.yaml."""
    def __init__(self, inventory_manager: Inventory, name="AddVerifiedPartToInventory", description="Adds a verified component definition to the inventory file."):
        super().__init__(name=name, description=description)
        self._inventory = inventory_manager

    async def run_async(self, *, verified_item_data: Dict, tool_context: adk.ToolContext) -> Dict[str, Any]:
        """
        Input: verified_item_data (dict matching InventoryItem structure, confirmed by user).
        Output: {'success': bool, 'part_id': str | None, 'message': str}
        """
        print(f"TOOL: Attempting to add verified item to inventory: {verified_item_data.get('description')}")
        try:
            # Assign a new part_id if not provided
            if 'part_id' not in verified_item_data or not verified_item_data['part_id']:
                 verified_item_data['part_id'] = self._inventory.get_next_part_id()
                 print(f"  Assigned new part_id: {verified_item_data['part_id']}")

            # Validate and create InventoryItem object
            new_item = InventoryItem(**verified_item_data)

            # Add the part using the inventory manager
            added = self._inventory.add_part(new_item)
            if added:
                # Save the updated inventory file
                saved = self._inventory.save()
                if saved:
                    return {'success': True, 'part_id': new_item.part_id, 'message': f"Successfully added and saved {new_item.part_id}."}
                else:
                    # Added in memory, but failed to save! Requires handling.
                    return {'success': False, 'part_id': new_item.part_id, 'message': f"Added {new_item.part_id} to memory, but FAILED to save inventory file!"}
            else:
                # add_part returned False (likely duplicate ID)
                 return {'success': False, 'part_id': new_item.part_id, 'message': f"Failed to add part {new_item.part_id} (likely duplicate ID)."}

        except Exception as e:
            print(f"ERROR in AddVerifiedPartToInventoryTool: {e}")
            return {'success': False, 'part_id': verified_item_data.get('part_id'), 'message': f"Error: {e}"}