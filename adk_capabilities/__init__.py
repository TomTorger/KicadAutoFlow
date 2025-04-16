# Make capabilities easily importable
from .api_client_base import LLMCapability, FootprintAPICapability
from .llm_capability import GeminiCapability, OpenAICapabilityPlaceholder
from .footprint_api_capability import SnapEDACapability # Assuming placeholder renamed/implemented

def create_llm_capability(config) -> LLMCapability:
    """Creates an LLM Capability instance based on config."""
    provider = config.llm_settings.default_provider.lower()
    try:
        if provider == "google_ai" or provider == "gemini":
            print("Initializing GeminiCapability...")
            return GeminiCapability(config=config)
        elif provider == "openai":
             print("Initializing OpenAICapabilityPlaceholder...")
             return OpenAICapabilityPlaceholder(config=config) # Replace with real one when implemented
        else:
             print(f"Warning: Unsupported LLM Provider '{provider}'. Using Placeholder.")
             return OpenAICapabilityPlaceholder(config=config) # Fallback
    except Exception as e:
        print(f"ERROR: Failed to initialize LLM capability '{provider}': {e}")
        print("Falling back to placeholder LLM.")
        return OpenAICapabilityPlaceholder(config=config)


def create_footprint_api_capability(config) -> FootprintAPICapability:
    """Creates a Footprint API Capability instance based on config."""
    # Add logic to select based on config if multiple APIs are supported
    # For now, assume SnapEDA if configured
    try:
        if config.api_keys.snapeda: # Check if SnapEDA key/creds exist
            print("Initializing SnapEDACapability...")
            return SnapEDACapability(config=config) # Use the implemented class
        else:
            print("Warning: No supported Footprint API configured. Using Placeholder.")
            # Return a dummy/placeholder if no real one is configured/implemented
            from .api_client_base import FootprintAPICapability as BaseFP # Avoid circular import if Dummy defined here
            class DummyFootprintAPICapability(BaseFP):
                 def search_by_mpn(self, mpn): return []
                 def download_asset(self, a, t, d): return None
            return DummyFootprintAPICapability()

    except Exception as e:
        print(f"ERROR: Failed to initialize Footprint API capability: {e}")
        print("Falling back to placeholder Footprint API.")
        class DummyFootprintAPICapability(FootprintAPICapability): # Redefine locally
             def search_by_mpn(self, mpn): return []
             def download_asset(self, a, t, d): return None
        return DummyFootprintAPICapability()

