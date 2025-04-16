# data_models/bom_data.py
from pydantic import BaseModel, Field, ValidationError
from typing import List, Dict, Optional, Union
import yaml
import csv
import xml.etree.ElementTree as ET
from pathlib import Path
import pandas as pd
from .component import Component, ComponentStatus # Relative import

class ProjectBomData(BaseModel):
    project_name: Optional[str] = None
    export_source: Optional[str] = None # Path to the KiCad export file used
    components: List[Component] = Field(default_factory=list)

class BoM:
    """Manages the project BoM, typically loaded from KiCad export and saved canonically."""
    def __init__(self, canonical_file_path: Union[str, Path]):
        """Initialize with the path to the canonical project bom.yaml."""
        self.file_path = Path(canonical_file_path)
        self.data = ProjectBomData()
        self._ref_map: Dict[str, int] = {} # Cache index for faster lookups

    def _build_ref_map(self):
        """Updates the internal cache mapping RefDes to list index."""
        self._ref_map = {comp.ref: i for i, comp in enumerate(self.data.components) if comp.ref}

    def load_from_kicad_export(self, kicad_export_path: Union[str, Path]) -> bool:
        """Loads BoM by parsing a KiCad exported file (CSV or XML). Resets current data."""
        export_file = Path(kicad_export_path)
        if not export_file.exists():
            print(f"ERROR: KiCad export file '{export_file}' not found.")
            self.data = ProjectBomData() # Reset
            self._build_ref_map()
            return False

        parsed_components: List[Component] = []
        success = False
        try:
            if export_file.suffix.lower() == '.csv':
                parsed_components = self._parse_kicad_csv(export_file)
                success = True
            elif export_file.suffix.lower() == '.xml':
                parsed_components = self._parse_kicad_xml(export_file)
                success = True
            else:
                print(f"ERROR: Unsupported KiCad BoM export format '{export_file.suffix}'. Use CSV or XML.")
                success = False

            if success:
                self.data = ProjectBomData(components=parsed_components, export_source=str(export_file))
                self._build_ref_map() # Update cache
                print(f"Loaded {len(self.data.components)} components from KiCad export '{export_file}'.")
            else:
                 self.data = ProjectBomData() # Reset on parse fail type
                 self._build_ref_map()

            return success

        except Exception as e:
            print(f"ERROR processing KiCad export file '{export_file}': {e}")
            self.data = ProjectBomData() # Reset on error
            self._build_ref_map()
            return False

    def _parse_kicad_csv(self, file_path: Path) -> List[Component]:
        """Parses KiCad's default CSV BoM export, handling potential variations."""
        components = []
        try:
            with open(file_path, mode='r', newline='', encoding='utf-8-sig') as csvfile: # Use utf-8-sig
                # Read a sample to sniff dialect robustly
                sample = "".join(csvfile.readline() for _ in range(10)) # Read first few lines for sniffing
                csvfile.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
                    has_header = csv.Sniffer().has_header(sample)
                except csv.Error:
                    print(f"WARN: Could not automatically detect CSV dialect/header for {file_path.name}. Assuming standard comma-separated with header.")
                    dialect = csv.excel # Fallback
                    # Try simple header check
                    first_line = csvfile.readline().lower()
                    has_header = 'reference' in first_line and 'value' in first_line
                    csvfile.seek(0) # Reset after reading first line

                reader = csv.reader(csvfile, dialect)
                header_map = {}

                if has_header:
                    header = next(reader)
                    norm_header = [h.lower().strip().replace(' ', '_').replace('#', 'number') for h in header]
                    header_map = {name: index for index, name in enumerate(norm_header)}
                    aliases = {
                        'reference': ['reference', 'designator', 'ref', 'references'],
                        'value': ['value', 'designation'],
                        'footprint': ['footprint', 'package', 'footprint_spec'],
                        'datasheet': ['datasheet', 'ds'],
                        'manufacturer': ['manufacturer', 'mfr', 'manf#'],
                        'part_number': ['part_number', 'mpn', 'mfr_part_number', 'manf#_partnumber', 'supplier_and_ref', 'vendor_ref'],
                        'description': ['description', 'desc'],
                        'quantity': ['quantity', 'qty']
                    }
                    resolved_map = {}
                    for key, possible_names in aliases.items():
                        for name in possible_names:
                             norm_name = name.replace(' ','_') # Normalize alias too
                             if norm_name in header_map:
                                  resolved_map[key] = header_map[norm_name]
                                  break
                    header_map = resolved_map
                    if not all(k in header_map for k in ['reference', 'value', 'footprint']):
                         print(f"WARN: CSV {file_path.name} might be missing key headers (Reference, Value, Footprint). Results may be inaccurate.")

                for i, row in enumerate(reader):
                    if not row or (has_header and i == 0 and len(header_map) > 0): continue # Skip empty/header

                    try:
                        ref_idx = header_map.get('reference', 0)
                        val_idx = header_map.get('value', 1)
                        fp_idx = header_map.get('footprint', 2)
                        qty_idx = header_map.get('quantity', -1)

                        if len(row) <= max(ref_idx, val_idx, fp_idx):
                             print(f"WARN: Row {i+1}: Skipping row due to insufficient columns. Row: {row}")
                             continue

                        refs_str = row[ref_idx]
                        refs = [r.strip() for r in refs_str.split(',') if r.strip()]
                        if not refs: continue

                        qty_per_ref = 1
                        if qty_idx != -1:
                             try: total_qty = int(row[qty_idx])
                             except (ValueError, IndexError): total_qty = len(refs)
                             if len(refs) > 0: qty_per_ref = max(1, total_qty // len(refs)) # Approximate
                        else:
                             total_qty = len(refs)
                             qty_per_ref = 1


                        for ref in refs:
                            val = row[val_idx]
                            fp = row[fp_idx] or None
                            ds = row[header_map.get('datasheet', -1)] or None
                            mpn = row[header_map.get('part_number', -1)] or None
                            desc = row[header_map.get('description', -1)] or f"{val} {fp or ''}".strip()
                            pkg = None # Package usually derived from footprint later

                            if ds == '~': ds = None
                            if fp == '~': fp = None
                            if mpn == '~': mpn = None

                            comp_data = {
                                'ref': ref, 'value': val, 'qty': qty_per_ref, 'footprint': fp,
                                'datasheet_url': ds, 'mpn': mpn, 'description': desc, 'package': pkg,
                                'source_info': f'KiCad CSV Export ({file_path.name})'
                            }
                            components.append(Component(**comp_data))
                    except Exception as row_e:
                        print(f"WARN: Row {i+1}: Error processing row. Error: {row_e}. Row: {row}")

        except FileNotFoundError: raise
        except Exception as e: print(f"ERROR: Failed to parse CSV file '{file_path}': {e}"); raise
        return components

    def _parse_kicad_xml(self, file_path: Path) -> List[Component]:
        """Parses KiCad's default XML BoM export."""
        # (Implementation from Iteration 3 - looks reasonable, ensure fields mapping is robust)
        components = []
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            components_node = root.find('.//components')
            if components_node is None: raise ValueError("<components> element not found.")

            for comp_node in components_node.findall('comp'):
                ref = comp_node.get('ref')
                if not ref: continue

                value = comp_node.findtext('value', default='')
                footprint = comp_node.findtext('footprint', default=None)
                datasheet = comp_node.findtext('datasheet', default=None)
                qty = 1 # XML default export doesn't group refs
                mpn = None
                desc = None
                pkg = None

                fields_node = comp_node.find('fields')
                if fields_node is not None:
                    for field in fields_node.findall('field'):
                        name = field.get('name', '').lower().strip().replace(' ', '_')
                        text = field.text.strip() if field.text else None
                        if name in ['mpn', 'part_number', 'mfg_part_number', 'manufacturer_part_number', 'pn']: mpn = text
                        elif name == 'description': desc = text
                        elif name == 'package': pkg = text
                        # Could extract other fields into extracted_params if needed

                desc = desc or f"{value} {footprint or ''}".strip()
                if datasheet == '~': datasheet = None
                if footprint == '~': footprint = None
                if mpn == '~': mpn = None

                try:
                    comp_data = {
                        'ref': ref, 'value': value, 'qty': qty, 'footprint': footprint,
                        'datasheet_url': datasheet, 'mpn': mpn, 'description': desc, 'package': pkg,
                        'source_info': f'KiCad XML Export ({file_path.name})'
                    }
                    components.append(Component(**comp_data))
                except ValidationError as e:
                     print(f"WARN: Skipping component {ref} from XML due to validation error: {e}")

        except ET.ParseError as e: print(f"ERROR: Failed to parse XML file '{file_path}': {e}"); raise
        except Exception as e: print(f"ERROR: Unexpected error parsing XML '{file_path}': {e}"); raise
        return components

    # --- load_canonical, save_canonical, get_component, update_component, add_component, to_dataframe ---
    # (Implementations from Iteration 3 are suitable)
    def load_canonical(self) -> bool:
        if not self.file_path.exists(): print(f"INFO: Canonical BoM file '{self.file_path}' not found."); self.data = ProjectBomData(); self._build_ref_map(); return False
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f: raw_data = yaml.safe_load(f)
            if raw_data: self.data = ProjectBomData(**raw_data); self._build_ref_map(); print(f"Loaded {len(self.data.components)} components from canonical BoM '{self.file_path}'."); return True
            else: print(f"INFO: Canonical BoM file '{self.file_path}' is empty."); self.data = ProjectBomData(); self._build_ref_map(); return False
        except Exception as e: print(f"ERROR loading canonical BoM '{self.file_path}': {e}"); self.data = ProjectBomData(); self._build_ref_map(); return False

    def save_canonical(self) -> bool:
        try:
            export_data = self.data.model_dump(mode='json', exclude_none=True)
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f: yaml.dump(export_data, f, sort_keys=False, indent=2, default_flow_style=False, allow_unicode=True)
            print(f"Saved {len(self.data.components)} components to canonical BoM '{self.file_path}'.")
            return True
        except Exception as e: print(f"ERROR saving canonical BoM '{self.file_path}': {e}"); return False

    def get_component(self, ref: str) -> Optional[Component]:
        index = self._ref_map.get(ref)
        if index is not None and index < len(self.data.components): return self.data.components[index]
        # Linear scan fallback if ref changed or map stale
        return next((c for c in self.data.components if c.ref == ref), None)

    def get_all_components(self) -> List[Component]: return self.data.components

    def update_component(self, updated_component: Component):
        index = self._ref_map.get(updated_component.ref)
        if index is not None and index < len(self.data.components) and self.data.components[index].ref == updated_component.ref:
             self.data.components[index] = updated_component; return True
        else: # Try linear scan by ref
            for i, comp in enumerate(self.data.components):
                if comp.ref == updated_component.ref: self.data.components[i] = updated_component; self._ref_map[updated_component.ref] = i; return True
            print(f"WARN: Component ref '{updated_component.ref}' not found for update."); return False

    def add_component(self, new_component: Component):
         if self.get_component(new_component.ref): print(f"WARN: Component ref '{new_component.ref}' already exists."); return False
         self.data.components.append(new_component); self._ref_map[new_component.ref] = len(self.data.components) - 1; return True

    def to_dataframe(self, include_health: bool = False, include_status: bool = False) -> pd.DataFrame:
         if not self.data.components:
              cols = ['ref', 'value', 'qty', 'description', 'package', 'footprint', 'mpn', 'source_info']
              if include_health: cols.extend(['health_score', 'health_details'])
              if include_status: cols.extend(list(ComponentStatus.model_fields.keys()))
              return pd.DataFrame(columns=cols)
         dict_list = []
         status_keys = list(ComponentStatus.model_fields.keys()) # Get keys once
         for comp in self.data.components:
              comp_dict = comp.model_dump(mode='json')
              if include_health: comp_dict['health_score'] = comp.health_score.score; comp_dict['health_details'] = "; ".join(comp.health_score.details)
              else: comp_dict.pop('health_score', None)
              if include_status: comp_dict.update({f"status_{k}": v for k, v in comp.status.model_dump().items()}) # Prefix status fields
              comp_dict.pop('status', None) # Remove original status object
              comp_dict.pop('llm_notes', None); comp_dict.pop('extracted_params', None)
              dict_list.append(comp_dict)
         return pd.DataFrame(dict_list)