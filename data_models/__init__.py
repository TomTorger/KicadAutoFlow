# data_models/__init__.py
# Make key data models easily importable
from .component import Component, ComponentStatus, HealthScore, ParsedFootprintData
from .inventory_item import InventoryItem
from .bom_data import BoM, ProjectBomData