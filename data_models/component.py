# data_models/component.py
from pydantic import BaseModel, Field, HttpUrl, FilePath, field_validator, model_validator, ConfigDict, ValidationError
from typing import Optional, Dict, List, Any, Literal, Union
from pathlib import Path

class ComponentStatus(BaseModel):
    """Tracks the verification status of a component's assets."""
    datasheet_downloaded: bool = False
    datasheet_local_path_valid: bool = False # Confirms the path points to an existing file
    footprint_found_libs: bool = False # Found in KiCad/Project libs via name
    footprint_parsed_ok: bool = False # Was KiUtils able to parse the file?
    footprint_api_result_available: bool = False # API search returned something
    footprint_downloaded_for_review: bool = False # Asset downloaded to libs/review/
    footprint_verified: bool = False # Final user acceptance of the assigned footprint
    footprint_review_pending: bool = False # Flag specifically for downloaded assets needing review
    symbol_found_libs: bool = False # Found the .kicad_sym file
    symbol_parsed_ok: bool = False # Was KiUtils able to parse the library file?
    symbol_definition_found: bool = False # Found the specific symbol def within the lib file
    symbol_verified: bool = False # Future use
    # LLM/LMM check results (optional, based on execution)
    llm_datasheet_check_result: Optional[Dict[str, Any]] = None # e.g., {'pin_match': True, 'package_match': False, 'notes': ...}
    lmm_footprint_check_result: Optional[Dict[str, Any]] = None # e.g., {'plausibility': 'High', 'notes': ...}
    llm_suggested: bool = False  # Added for test compatibility

    # Use ConfigDict for Pydantic v2+ configuration
    model_config = ConfigDict(validate_assignment=True)

class HealthScore(BaseModel):
    """Stores the calculated health score and contributing factors."""
    score: float = 0.0
    max_possible: float = 10.0 # Will be dynamically calculated
    details: List[str] = Field(default_factory=list)
    rules_version: Optional[str] = None # Optional: track which rule version was used

    model_config = ConfigDict(validate_assignment=True)

class ParsedFootprintData(BaseModel):
    """Holds data extracted from parsing footprint file."""
    courtyard_area: Optional[float] = None # mm^2
    bounding_box_area: Optional[float] = None # mm^2
    pin_count: Optional[int] = None
    errors: List[str] = Field(default_factory=list)

class Component(BaseModel):
    """Base model representing a component instance in a BoM."""
    ref: str = Field(..., description="Hierarchical reference (e.g., /Sheet1/R1)") # Explicitly required
    value: str = ""
    description: str = ""
    qty: int = 1
    package: Optional[str] = None # e.g., "0805", "SOT-23"
    footprint: Optional[str] = None # KiCad format: "Library:FootprintName"
    mpn: Optional[str] = None # Manufacturer Part Number
    datasheet_url: Optional[HttpUrl] = None
    datasheet_local: Optional[str] = None # Relative path to project root (e.g., docs/datasheets/...)
    source_link: Optional[HttpUrl] = None
    source_info: Optional[str] = Field(default="Unknown", description="Origin: KiCad Export, Inventory INVXXX, API: XYZ, Manual Add")
    status: ComponentStatus = Field(default_factory=ComponentStatus)
    health_score: HealthScore = Field(default_factory=HealthScore)
    llm_notes: List[str] = Field(default_factory=list) # General notes/warnings from processes
    extracted_params: Dict[str, Any] = Field(default_factory=dict) # e.g., {'pin_count': 8}
    estimated_area: Optional[float] = None # To be populated from ParsedFootprintData

    # Use ConfigDict for Pydantic v2+ configuration
    model_config = ConfigDict(validate_assignment=True, extra='ignore') # Ignore extra fields during parsing

    @field_validator('ref')
    @classmethod
    def check_ref_format(cls, v: str) -> str:
        if not v or not v.strip(): raise ValueError('Component reference (ref) cannot be empty')
        # Allow alphanumeric, underscores, dashes, and forward slashes for hierarchy
        # Add other valid KiCad ref chars if needed
        # if not re.match(r"^[a-zA-Z0-9_/\-]+$", v):
        #     raise ValueError(f"Invalid characters in reference: {v}")
        return v.strip()

    @field_validator('datasheet_local', mode='before')
    @classmethod
    def validate_relative_path_str(cls, v: Optional[str]) -> Optional[str]:
        """Ensure path strings are relative and clean."""
        if v is None: return None
        try:
            # Attempt to create Path object, will fail on invalid chars
            p = Path(str(v))
            # Disallow absolute paths for portability
            if p.is_absolute():
                raise ValueError("Local path must be relative to project root")
            # Disallow '..' for basic security/simplicity
            if '..' in p.parts:
                 raise ValueError("Local path cannot contain '..'")
            return str(p).replace('\\', '/') # Consistent separators
        except Exception as e:
            raise ValueError(f"Invalid path format: {v} ({e})")

    def update_status_fields(self, updates: Dict[str, Any]):
        """Safely update fields in the status object."""
        current_status_dict = self.status.model_dump()
        valid_updates = {k: v for k, v in updates.items() if k in ComponentStatus.model_fields}
        current_status_dict.update(valid_updates)
        try:
            self.status = ComponentStatus(**current_status_dict)
        except ValidationError as e:
             print(f"ERROR validating status update for {self.ref}: {e}")
             # Optionally log the error or invalid updates, but don't apply partial update

    def add_note(self, note: str):
        """Append a note to the llm_notes field, avoiding duplicates."""
        if note not in self.llm_notes:
            self.llm_notes.append(note)

    def set_parsed_footprint_data(self, data: ParsedFootprintData):
        """Updates component fields based on footprint parsing results."""
        self.estimated_area = data.courtyard_area or data.bounding_box_area
        if data.errors:
            self.add_note(f"Footprint parsing issues: {'; '.join(data.errors)}")
        self.update_status_fields({'footprint_parsed_ok': not data.errors})
        # Store pin count if parsed
        if data.pin_count is not None:
             # Ensure existing dict if not present
             if self.extracted_params is None: self.extracted_params = {}
             self.extracted_params['parsed_pin_count'] = data.pin_count