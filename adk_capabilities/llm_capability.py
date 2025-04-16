import google.generativeai as genai
from .api_client_base import LLMCapability
from typing import Optional, Dict, Any, List
import base64
import json
import time

# Configure the Gemini client library
def configure_gemini(api_key: Optional[str]):
    if api_key:
        try:
            genai.configure(api_key=api_key)
            print("Gemini configured successfully.")
            return True
        except Exception as e:
            print(f"ERROR: Failed to configure Gemini API: {e}")
            return False
    else:
        print("Warning: Google AI API key not provided in config. Gemini features disabled.")
        return False

# Helper to parse JSON response from LLM, robustly
def parse_llm_json_response(text: str, context: str = "") -> Optional[Dict]:
    try:
        # Find the first '{' and the last '}'
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_str = text[start:end+1]
            # Basic cleaning
            json_str = json_str.replace("```json", "").replace("```", "").strip()
            return json.loads(json_str)
        else:
            print(f"Warning: No valid JSON block found in LLM response for {context}: {text}")
            return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from LLM response for {context}: {e}\nRaw text: {text}")
        return None
    except Exception as e:
        print(f"Unexpected error parsing LLM JSON for {context}: {e}")
        return None


class GeminiCapability(LLMCapability):
    """LLM Capability using Google's Gemini models via Python client."""
    def __init__(self, config):
        self.config = config.llm_settings
        self.prompts = config.prompts # Loaded prompts dictionary
        self.api_key_present = configure_gemini(config.api_keys.google_ai)
        self.text_model = None
        self.vision_model = None
        if self.api_key_present:
             try:
                  self.text_model = genai.GenerativeModel(self.config.default_text_model)
                  self.vision_model = genai.GenerativeModel(self.config.default_vision_model)
             except Exception as e:
                  print(f"ERROR: Could not initialize Gemini models ({self.config.default_text_model}, {self.config.default_vision_model}): {e}")
                  self.api_key_present = False # Disable capability if models fail

        self.generation_config = genai.types.GenerationConfig(**(self.config.gemini_generation_config or {}))
        # Set default low temperature for more factual tasks if not specified
        if self.generation_config.temperature is None:
             self.generation_config.temperature = 0.2

        print(f"GeminiCapability Initialized (API Active: {self.api_key_present})")

    def get_default_text_model_name(self) -> str:
        return self.config.default_text_model

    def _call_gemini(self, model, prompt_parts: List[Any], task_description: str) -> Optional[str]:
        """Helper function to call Gemini API with error handling."""
        if not self.api_key_present or not model:
             print(f"Skipping Gemini call for '{task_description}': API key or model not available.")
             return None
        try:
            # print(f"DEBUG: Calling Gemini for '{task_description}'...") # Optional debug
            response = model.generate_content(prompt_parts, generation_config=self.generation_config)
            # print(f"DEBUG: Gemini response received for '{task_description}'.")
            # Handle potential blocks or safety ratings if needed
            # return response.text # Returns combined text
            # Check for empty candidates or parts
            if response.candidates and response.candidates[0].content.parts:
                 return response.text
            else:
                 print(f"Warning: Gemini response for '{task_description}' was empty or blocked.")
                 # print(f"DEBUG: Full Response: {response}")
                 return None
        except Exception as e:
            print(f"ERROR: Gemini API call failed for '{task_description}': {e}")
            # Implement retry logic?
            time.sleep(1) # Basic wait before potential retry elsewhere
            return None

    def suggest_footprint(self, package_desc: str, component_desc: str) -> Optional[str]:
        prompt_template = self.prompts.get('suggest_footprint')
        if not prompt_template: return None

        prompt = prompt_template.format(package_desc=package_desc or "N/A", component_desc=component_desc or "N/A")
        result_text = self._call_gemini(self.text_model, [prompt], "footprint suggestion")

        if result_text:
            result = result_text.strip()
            if result.lower() == 'none' or ':' not in result:
                return None # LLM indicated uncertainty or invalid format
            # Basic validation
            if len(result.split(':')) == 2 and result.split(':')[0] and result.split(':')[1]:
                 return result
            else:
                 print(f"Warning: LLM suggested footprint has invalid format: '{result}'")
                 return None
        return None

    def analyze_image_for_component(self, image_data: bytes) -> Optional[Dict[str, Any]]:
        prompt_template = self.prompts.get('analyze_component_image')
        if not prompt_template or not self.vision_model: return None

        # Assuming JPEG for now, adjust mime_type if needed
        image_part = {"mime_type": "image/jpeg", "data": image_data}
        prompt_parts = [prompt_template, image_part]

        result_text = self._call_gemini(self.vision_model, prompt_parts, "image analysis")

        if result_text:
            parsed_json = parse_llm_json_response(result_text, "image analysis")
            return parsed_json # Returns dict or None
        return None

    def check_datasheet_consistency(self, datasheet_text: str, expected_params: Dict) -> Dict[str, Any]:
        default_response = {'match': None, 'notes': "Check not performed or failed."}
        if not self.text_model: return default_response

        pin_prompt_template = self.prompts.get('check_pin_count')
        pkg_prompt_template = self.prompts.get('check_package_match')
        if not pin_prompt_template or not pkg_prompt_template: return default_response

        # Limit text snippet size
        text_snippet = datasheet_text[:3000] # Limit context size
        value_desc = f"{expected_params.get('value','')} / {expected_params.get('description','')}"[:100]
        package = expected_params.get('package', 'N/A')
        # Get expected pin count from footprint details if available
        expected_pin_count = expected_params.get('parsed_pin_count', 'N/A')

        results = {'notes': ''}

        # Check Pin Count
        if expected_pin_count != 'N/A':
             pin_prompt = pin_prompt_template.format(
                 datasheet_text_snippet=text_snippet,
                 package=package,
                 value_desc=value_desc,
                 expected_pin_count=expected_pin_count
             )
             pin_result_text = self._call_gemini(self.text_model, [pin_prompt], "pin count check")
             pin_json = parse_llm_json_response(pin_result_text or "", "pin count check") if pin_result_text else None
             results['pin_check'] = pin_json or {'match': None, 'notes': 'Pin check failed/no response.'}
             results['notes'] += results['pin_check']['notes'] + " "
        else:
             results['pin_check'] = {'match': None, 'notes': 'Skipped (no expected pin count).'}


        # Check Package Match
        if package != 'N/A':
             pkg_prompt = pkg_prompt_template.format(
                 datasheet_text_snippet=text_snippet,
                 package=package,
                 value_desc=value_desc
             )
             pkg_result_text = self._call_gemini(self.text_model, [pkg_prompt], "package match check")
             pkg_json = parse_llm_json_response(pkg_result_text or "", "package match check") if pkg_result_text else None
             results['package_check'] = pkg_json or {'match': None, 'notes': 'Package check failed/no response.'}
             results['notes'] += results['package_check']['notes']
        else:
             results['package_check'] = {'match': None, 'notes': 'Skipped (no expected package).'}

        results['notes'] = results['notes'].strip()
        return results

# --- Patch: Minimal OpenAICapabilityPlaceholder for test compatibility ---
class OpenAICapabilityPlaceholder(LLMCapability):
    def __init__(self, config=None):
        self.config = config
        self.prompts = getattr(config, 'prompts', {})
    def get_default_text_model_name(self):
        return "openai-placeholder"
    def suggest_footprint(self, package_desc, component_desc):
        return None
    def analyze_image_for_component(self, image_data):
        return None
    def check_datasheet_consistency(self, datasheet_text, expected_params):
        return {'match': None, 'notes': 'OpenAI placeholder: check not performed.'}

