from .api_client_base import FootprintAPICapability
from typing import Optional, Dict, Any, List, Literal
from pathlib import Path
import requests
import json
import shutil
import time
import os

class SnapEDACapability(FootprintAPICapability):
    """Footprint API Capability using SnapEDA."""
    def __init__(self, config):
        # SnapEDA typically uses Username/Password or specific header keys
        # Adjust based on actual auth method. Using placeholder key from config.
        self.api_key = config.api_keys.snapeda
        self.headers = {
            'Accept': 'application/json',
            # Example Header Auth: (Check SnapEDA Docs for correct header name)
            # 'X-SnapEDA-Key': self.api_key
        }
        self.base_url = "https://api.snapeda.com/v1" # Verify correct URL from SnapEDA docs
        self.auth = None # Use requests' auth tuple if username/password needed
        # if config.snapeda_username and config.snapeda_password:
        #    self.auth = (config.snapeda_username, config.snapeda_password)

        self.can_operate = bool(self.api_key) # Or check self.auth if using user/pass
        if not self.can_operate:
            print("Warning: SnapEDA credentials missing in config. SnapEDA capability disabled.")
        else:
             print(f"SnapEDACapability Initialized (Base URL: {self.base_url})")


    def search_by_mpn(self, mpn: str) -> List[Dict[str, Any]]:
        if not self.can_operate: return []
        search_url = f"{self.base_url}/parts/search" # Verify endpoint from SnapEDA docs
        params = {'q': mpn, 'type': 'json', 'limit': 5}
        processed_results = []
        print(f"[SnapEDA] Searching MPN: {mpn}...")
        try:
            response = requests.get(search_url, headers=self.headers, params=params, auth=self.auth, timeout=20)
            response.raise_for_status()
            data = response.json()

            if data and 'results' in data:
                print(f"  Found {len(data['results'])} potential matches.")
                for result in data['results']:
                    # Check if KiCad assets exist - structure depends on SnapEDA response
                    # Assume keys like 'has_kicad_footprint', 'has_kicad_symbol' exist based on API docs
                    has_kicad_fp = result.get('has_kicad_footprint', False) # Example key
                    has_kicad_sym = result.get('has_kicad_symbol', False)  # Example key

                    if has_kicad_fp or has_kicad_sym:
                        manufacturer = result.get('manufacturer', {}).get('name') if result.get('manufacturer') else None
                        processed_results.append({
                            'mpn': result.get('part_number'), # Use correct field name from API
                            'manufacturer': manufacturer,
                            'description': result.get('description'),
                            'api_source': 'SnapEDA',
                            'has_kicad_fp': has_kicad_fp,
                            'has_kicad_sym': has_kicad_sym,
                            'api_specific_data': result # Store raw result for download
                        })
            else:
                 print(f"  No results found for {mpn}.")
            # Add small delay?
            time.sleep(0.5)

        except requests.exceptions.RequestException as e:
            print(f"ERROR searching SnapEDA for '{mpn}': {e}")
        except Exception as e:
            print(f"ERROR: Unexpected error during SnapEDA search: {e}")

        return processed_results

    def download_asset(self, asset_info: Dict, asset_type: Literal['symbol', 'footprint'], download_dir: Path) -> Optional[Path]:
        if not self.can_operate: return None

        snapeda_data = asset_info.get('api_specific_data')
        if not snapeda_data:
            print(f"ERROR: Missing 'api_specific_data' in asset info for download.")
            return None

        # Construct download URL/request based on SnapEDA API documentation
        # This typically requires a part ID or specific download endpoint from the search result.
        # Example using hypothetical part ID and endpoint structure:
        part_id = snapeda_data.get('id') # Use correct ID field from API response
        if not part_id:
             print(f"ERROR: Missing part ID in SnapEDA data for {asset_info.get('mpn')}")
             return None

        download_url = f"{self.base_url}/parts/{part_id}/download" # Verify endpoint
        params = {'format': 'kicad', 'type': asset_type}

        print(f"[SnapEDA] Downloading {asset_type} for {asset_info.get('mpn')}...")
        try:
            response = requests.get(download_url, headers=self.headers, params=params, auth=self.auth, stream=True, timeout=45)
            response.raise_for_status()

            # Determine filename
            content_disp = response.headers.get('content-disposition')
            filename = None
            if content_disp:
                 filename_parts = [p.strip() for p in content_disp.split(';') if 'filename=' in p.lower()]
                 if filename_parts:
                      filename = filename_parts[0].split('=', 1)[1].strip('" ')
            # Fallback filename construction
            if not filename or not (filename.endswith(".kicad_mod") or filename.endswith(".kicad_sym")):
                 ext = ".kicad_mod" if asset_type == 'footprint' else ".kicad_sym"
                 filename = f"{asset_info.get('mpn','asset')}_{asset_type}{ext}"
                 print(f"  WARN: Could not determine filename from header, using fallback: {filename}")


            filepath = download_dir / filename
            filepath.parent.mkdir(parents=True, exist_ok=True) # Ensure download_dir exists

            with open(filepath, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            print(f"  SUCCESS: Saved to {filepath}")
            return filepath

        except requests.exceptions.RequestException as e:
            print(f"ERROR downloading {asset_type} from SnapEDA: {e}")
            # Attempt to read error response body if available
            try:
                 error_details = response.json()
                 print(f"  API Error Details: {error_details}")
            except: pass # Ignore if response body isn't JSON or doesn't exist
            return None
        except Exception as e:
             print(f"ERROR: Unexpected error during SnapEDA download: {e}")
             return None
