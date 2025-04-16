import time
# adk_tools/doc_tools.py
import google.adk as adk
from typing import Dict, Any, Optional, List
from pathlib import Path

# Assume imports work
from data_models.bom_data import BoM # Needs to load/process final BoM object
from data_models.inventory_item import Inventory # Needs inventory access
from utils.render_footprint_util import FootprintRenderer # If rendering images

class GenerateMarkdownReportTool(adk.tools.BaseTool):
    """Generates the Component_Review.md documentation file."""
    def __init__(self, inventory: Inventory, project_root: Path, name="GenerateMarkdownReport", description="Generates Component Review Markdown file."):
        super().__init__(name=name, description=description)
        self._inventory = inventory
        self._project_root = project_root
        # Renderer needs lib_manager, potentially passed via context or init
        # self._renderer = FootprintRenderer(lib_manager, project_root)
        self._doc_dir = project_root / "docs"
        self._output_path = self._doc_dir / "Component_Review.md"

    def _generate_component_markdown(self, component_dict: Dict) -> str:
        # Placeholder: Adapt the markdown generation logic from previous iterations
        # using the component_dict as input. Fetch inventory images, render footprints etc.
        ref = component_dict.get('ref','N/A')
        val = component_dict.get('value','')
        score = component_dict.get('health_score',{}).get('score','N/A')
        md = f"## Component: {ref} ({val}) - Score: {score}\n\n"
        md += f"**Description:** {component_dict.get('description','')}\n"
        # ... add all other sections ...
        md += "**Review Actions Required:**\n"
        # ... add checklist based on status ...
        md += "\n---\n"
        return md

    async def run_async(self, *, final_bom_data: List[Dict], tool_context: adk.ToolContext) -> Dict[str, Any]:
        """
        Input: final_bom_data (List of component dicts after verification).
        Output: {'success': bool, 'report_path': str | None}
        """
        print("TOOL: Generating Component Review Markdown report...")
        try:
            self._doc_dir.mkdir(parents=True, exist_ok=True)
            markdown_content = "# Component Review Report\n\n"
            markdown_content += f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n" # Add timestamp

            for comp_dict in final_bom_data:
                 markdown_content += self._generate_component_markdown(comp_dict)

            with open(self._output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            relative_path = str(self._output_path.relative_to(self._project_root))
            print(f"  Report saved to: {relative_path}")
            return {'success': True, 'report_path': relative_path}
        except Exception as e:
            print(f"ERROR in GenerateMarkdownReportTool: {e}")
            return {'success': False, 'report_path': None, 'error': str(e)}