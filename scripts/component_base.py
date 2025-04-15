from pydantic import BaseModel, Field, HttpUrl, FilePath
from typing import Optional, Dict, List, Any, Literal

class ComponentStatus(BaseModel):
    datasheet_local: bool = False
    datasheet_url_valid: Optional[bool] = None # None = not checked
    footprint_exists: bool = False
    footprint_verified: Union[bool, Literal['review_pending']] = False # True when manually accepted or known good
    symbol_exists: bool = False # Heuristic check result
    api_downloaded: bool = False # True if assets were downloaded to review/
    llm_suggested: bool = False # True if LLM suggested footprint/symbol
    # Add flags for specific LLM/LMM checks later
    llm_doc_check_status: Optional[Literal['OK', 'Mismatch', 'Uncertain']] = None
    lmm_fp_check_status: Optional[Literal['Plausible', 'Mismatch', 'Uncertain']] = None

class HealthScore(BaseModel):
    score: float = 0.0
    max_possible: float = 7.0 # Example, should be calculated based on rules
    details: List[str] = Field(default_factory=list) # e.g., ["+1.0 Datasheet Local", "-0.5 Footprint Missing"]

class Component(BaseModel):
    """Base model for a component in the BoM or Inventory."""
    ref: Optional[str] = None # Only used in BoM context (hierarchical)
    value: str = ""
    description: str = ""
    package: Optional[str] = None # e.g., "0805", "SOT-23", "TQFP-100"
    footprint: Optional[str] = None # KiCad format: "Library:FootprintName"
    mpn: Optional[str] = None # Manufacturer Part Number
    datasheet_url: Optional[HttpUrl] = None
    datasheet_local: Optional[FilePath] = None
    source_link: Optional[HttpUrl] = None
    source_info: Optional[str] = None # e.g., "Inventory INV001", "API: SnapEDA", "Manual Add"
    status: ComponentStatus = Field(default_factory=ComponentStatus)
    health_score: HealthScore = Field(default_factory=HealthScore)
    llm_notes: List[str] = Field(default_factory=list) # Notes/discrepancies from LLM checks
    extracted_params: Dict[str, Any] = Field(default_factory=dict) # e.g., {'pin_count': 8}
    estimated_area: Optional[float] = None # mm^2

    class Config:
        # Allow FilePath to be used
        arbitrary_types_allowed = True
        validate_assignment = True # Re-validate on attribute assignment

    def update_status(self, updates: Dict[str, Any]):
        """Update status fields."""
        status_data = self.status.model_dump()
        status_data.update(updates)
        self.status = ComponentStatus(**status_data)

    # Placeholder for health calculation - actual logic in HealthCalculator
    def calculate_health(self, calculator):
        """Calculates health score using external calculator."""
        score_data = calculator.calculate(self)
        self.health_score = HealthScore(**score_data)

