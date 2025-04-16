from pydantic import BaseModel, Field, ValidationError
from typing import List, Dict, Optional, Union, Any
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

class ImageAnalysisManager:
    """Manages the analysis of component images for inventory management."""
    
    def __init__(self, llm_capability, inventory, img_dir: Union[str, Path] = None):
        """Initialize the image analysis manager.
        
        Args:
            llm_capability: LLM capability instance (e.g., GeminiCapability)
            inventory: Inventory instance
            img_dir: Directory to store images (defaults to docs/inventory_images)
        """
        self.llm = llm_capability
        self.inventory = inventory
        self.img_dir = Path(img_dir) if img_dir else Path('docs/inventory_images')
        self.img_dir.mkdir(parents=True, exist_ok=True)
        
    def analyze_image(self, image_path: Union[str, Path]) -> Dict[str, Any]:
        """Analyze a component image and extract information.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary with extracted component information
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
            
        # Read image bytes
        with open(image_path, 'rb') as f:
            img_bytes = f.read()
            
        # Use LLM to analyze image
        try:
            analysis_result = self.llm.analyze_image_for_component(img_bytes) or {}
            
            # Get footprint suggestion if package was detected
            if analysis_result.get('package_guess'):
                footprint_suggestion = self.llm.suggest_footprint(
                    analysis_result.get('package_guess', ''),
                    analysis_result.get('component_type_guess', '')
                )
                analysis_result['footprint_suggestion'] = footprint_suggestion
            
            print(f"Image analysis result: {analysis_result}")

            item = self.create_item_from_analysis(analysis_result, image_path)
            return item
        except Exception as e:
            print(f"Error analyzing image: {e}")
            return {}
            
    def create_item_from_analysis(self, analysis_result: Dict[str, Any], 
                                  image_path: Union[str, Path] = None) -> InventoryItem:
        """Create an InventoryItem from analysis results.
        
        Args:
            analysis_result: Dictionary with analysis results
            image_path: Optional path to the original image
            
        Returns:
            New InventoryItem populated with analysis results
        """
        # Generate relative image path if provided
        img_rel_path = None
        if image_path:
            image_path = Path(image_path)
            if image_path.exists():
                # Make path relative to project root if it's not already
                if image_path.is_absolute():
                    try:
                        # Try to make relative to img_dir parent (project root)
                        img_rel_path = str(image_path.relative_to(self.img_dir.parent))
                    except ValueError:
                        # If not under project root, just use the name
                        img_rel_path = str(image_path.name)
                else:
                    img_rel_path = str(image_path)
                    
                # Normalize path separators
                img_rel_path = img_rel_path.replace('\\', '/')
        
        # Create new inventory item
        new_item = InventoryItem(
            part_id=self.inventory.get_next_part_id(),
            description=analysis_result.get('component_type_guess', ''),
            value=analysis_result.get('value_guess', ''),
            package=analysis_result.get('package_guess', ''),
            footprint=analysis_result.get('footprint_suggestion', ''),
            mounting_type=analysis_result.get('mounting_type', 'Unknown'),
            footprint_source='image_analysis',
            mpn=analysis_result.get('mpn') if analysis_result.get('mpn') else None,
            quantity=analysis_result.get('quantity_guess', 1),
            storage_location=None,
            image_path=img_rel_path,
            analysis_confidence=analysis_result.get('confidence', 'Medium')
        )
        
        return new_item
        
    def add_part_from_image(self, image_path: Union[str, Path], 
                            save_to_inventory: bool = False) -> InventoryItem:
        """Analyze an image and create a component from it.
        
        Args:
            image_path: Path to the image file
            save_to_inventory: Whether to automatically save to inventory
            
        Returns:
            Created InventoryItem
        """
        # Analyze the image
        analysis_result = self.analyze_image(image_path)
        
        # Create item from analysis
        item = self.create_item_from_analysis(analysis_result, image_path)
        
        # Add to inventory if requested
        if save_to_inventory:
            self.inventory.add_part(item)
            self.inventory.save()
            
        return item

