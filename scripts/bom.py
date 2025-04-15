from pydantic import BaseModel, Field, ValidationError
from typing import List, Dict, Optional, Union
import yaml
import csv
import xml.etree.ElementTree as ET # For XML parsing
from pathlib import Path
import pandas as pd

# Assuming component_base.py is in the same directory level or PYTHONPATH includes scripts/
from component_base import Component

class BomData(BaseModel):
    """Pydantic model for the structure of the canonical project bom.yaml."""
    # Could add metadata here like project name, date, etc.
    components: List[Component] = Field(default_factory=list)

class BoM:
    """Manages the Bill of Materials for a specific KiCad project."""
    def __init__(self, canonical_file_path: Union[str, Path]):
        """Initialize with the path to the canonical project bom.yaml."""
        self.file_path = Path(canonical_file_path)
        self.data = BomData()

    def load_from_kicad_export(self, kicad_export_path: Union[str, Path]):
        """Loads BoM data by parsing a KiCad exported file (CSV or XML).
           Resets the current BoM data.
        """
        export_file = Path(kicad_export_path)
        if not export_file.exists():
            print(f"Error: KiCad export file '{export_file}' not found.")
            return False

        new_components = []
        try:
            if export_file.suffix.lower() == '.csv':
                new_components = self._parse_kicad_csv(export_file)
            elif export_file.suffix.lower() == '.xml':
                new_components = self._parse_kicad_xml(export_file)
            else:
                print(f"Error: Unsupported KiCad BoM export format '{export_file.suffix}'. Use CSV or XML.")
                return False

            self.data = BomData(components=new_components)
            print(f"Loaded {len(self.data.components)} components from KiCad export '{export_file}'.")
            # Optionally save immediately to canonical YAML? Or let verification loop do it?
            # self.save()
            return True

        except Exception as e:
            print(f"Error processing KiCad export file '{export_file}': {e}")
            self.data = BomData() # Reset on error
            return False

    def _parse_kicad_csv(self, file_path: Path) -> List[Component]:
        """Parses KiCad's default CSV BoM export."""
        components = []
        with open(file_path, mode='r', newline='', encoding='utf-8') as csvfile:
             # Skip header lines until we find the component data
             reader = csv.reader(csvfile)
             header_found = False
             expected_headers = ['Reference', 'Value', 'Footprint', 'Datasheet', 'Manufacturer', 'Part Number'] # Adjust if KiCad default changes
             header_map = {}

             for row in reader:
                 if not row: continue # Skip empty rows

                 if not header_found:
                     # Find the actual header row (might vary based on KiCad version/settings)
                     if all(h in row for h in ['Reference', 'Value', 'Footprint']): # Check for key headers
                          header_found = True
                          # Map header names to column indices
                          header_map = {name: index for index, name in enumerate(row)}
                          # Verify required headers exist
                          if not all(h in header_map for h in ['Reference', 'Value', 'Footprint']):
                              raise ValueError("CSV missing required headers: Reference, Value, Footprint")
                          continue # Move to next row after finding header
                     else:
                          continue # Skip comment/title lines

                 # Process component rows
                 if header_found:
                     try:
                        # References might be comma-separated: "R1, R2, R3"
                        refs_str = row[header_map['Reference']]
                        refs = [r.strip() for r in refs_str.split(',')]

                        for ref in refs:
                            comp_data = {
                                'ref': ref,
                                'value': row[header_map['Value']],
                                'footprint': row[header_map.get('Footprint', -1)] or None, # Handle missing optional columns
                                'datasheet_url': row[header_map.get('Datasheet', -1)] or None,
                                'mpn': row[header_map.get('Part Number', -1)] or None,
                                # KiCad default CSV doesn't usually have Description or Package separate
                                'description': f"{row[header_map['Value']]} {row[header_map.get('Footprint', '')]}".strip(),
                                'package': None # Or try to parse from Footprint? Risky.
                            }
                            # Basic validation/cleaning
                            if comp_data['datasheet_url'] == '~': comp_data['datasheet_url'] = None
                            if comp_data['footprint'] == '~': comp_data['footprint'] = None
                            components.append(Component(**comp_data))
                     except IndexError:
                         print(f"Warning: Skipping malformed CSV row: {row}")
                     except ValidationError as e:
                         print(f"Warning: Skipping row due to validation error: {row} - {e}")

        return components

    def _parse_kicad_xml(self, file_path: Path) -> List[Component]:
        """Parses KiCad's default XML BoM export."""
        components = []
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            # Find the 'components' element
            components_element = root.find('.//components')
            if components_element is None:
                 raise ValueError("Could not find <components> element in XML.")

            for comp_node in components_element.findall('comp'):
                ref = comp_node.get('ref')
                if not ref: continue

                value_node = comp_node.find('value')
                footprint_node = comp_node.find('footprint')
                datasheet_node = comp_node.find('datasheet')
                # KiCad XML often uses 'fields' for MPN etc.
                mpn = None
                description = None
                fields = comp_node.find('fields')
                if fields is not None:
                     for field in fields.findall('field'):
                          if field.get('name', '').lower() in ['mpn', 'part number', 'manufacturer part number']:
                               mpn = field.text
                          if field.get('name', '').lower() == 'description':
                               description = field.text

                comp_data = {
                     'ref': ref,
                     'value': value_node.text if value_node is not None else '',
                     'footprint': footprint_node.text if footprint_node is not None else None,
                     'datasheet_url': datasheet_node.text if datasheet_node is not None else None,
                     'mpn': mpn,
                     'description': description or f"{value_node.text if value_node is not None else ''} {footprint_node.text if footprint_node is not None else ''}".strip(),
                     'package': None # Difficult to reliably get from default XML
                }
                # Basic validation/cleaning
                if comp_data['datasheet_url'] == '~': comp_data['datasheet_url'] = None
                if comp_data['footprint'] == '~': comp_data['footprint'] = None
                components.append(Component(**comp_data))

        except ET.ParseError as e:
             print(f"Error parsing XML file '{file_path}': {e}")
             raise
        except ValidationError as e:
             print(f"Warning: Skipping component due to validation error: {ref} - {e}")
        except Exception as e:
             print(f"Unexpected error parsing XML '{file_path}': {e}")
             raise

        return components


    def load_canonical(self):
        """Loads BoM from the canonical project YAML file."""
        if not self.file_path.exists():
            print(f"Canonical BoM file '{self.file_path}' not found. Starting empty.")
            self.data = BomData()
            return False
        try:
            with open(self.file_path, 'r') as f:
                raw_data = yaml.safe_load(f)
            if raw_data and 'components' in raw_data:
                self.data = BomData(components=raw_data['components'])
                print(f"Loaded {len(self.data.components)} components from canonical BoM '{self.file_path}'.")
                return True
            else:
                print(f"Canonical BoM file '{self.file_path}' is empty or invalid. Starting empty.")
                self.data = BomData()
                return False
        except Exception as e:
            print(f"Error loading canonical BoM from '{self.file_path}': {e}")
            self.data = BomData()
            return False

    def save(self):
        """Saves the current BoM to the canonical project YAML file."""
        try:
            # Use Pydantic's dict() method for clean export
            export_data = self.data.model_dump(exclude_none=True, exclude_defaults=False) # Keep defaults for clarity maybe?
            # Ensure directory exists
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'w') as f:
                yaml.dump(export_data, f, sort_keys=False, indent=2)
            print(f"Saved {len(self.data.components)} components to canonical BoM '{self.file_path}'.")
            return True
        except Exception as e:
            print(f"Error saving canonical BoM to '{self.file_path}': {e}")
            return False

    def get_component(self, ref: str) -> Optional[Component]:
        """Retrieves a component by its reference designator."""
        for comp in self.data.components:
            if comp.ref == ref:
                return comp
        return None

    def get_all_components(self) -> List[Component]:
        return self.data.components

    def to_dataframe(self, include_health: bool = False) -> pd.DataFrame:
        """Converts BoM data to a pandas DataFrame."""
        if not self.data.components:
            cols = ['ref', 'value', 'description', 'package', 'footprint', 'mpn']
            if include_health: cols.extend(['health_score', 'health_details'])
            return pd.DataFrame(columns=cols)

        dict_list = []
        for comp in self.data.components:
             comp_dict = comp.model_dump()
             if include_health:
                 # Flatten health score for easier display
                 comp_dict['health_score'] = comp.health_score.score
                 comp_dict['health_details'] = "; ".join(comp.health_score.details)
             else:
                 # Remove detailed objects if not needed in simple view
                 comp_dict.pop('status', None)
                 comp_dict.pop('health_score', None)
                 comp_dict.pop('llm_notes', None)
                 comp_dict.pop('extracted_params', None)
             dict_list.append(comp_dict)

        return pd.DataFrame(dict_list)

