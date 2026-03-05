"""Public package API for config-driven HTTP clients."""

from .manager import ConfigHttpLibrary
from .openapi_bridge import export_maix_to_openapi, import_openapi_to_maix_config

# Global singleton that can be imported from anywhere in the project.
api = ConfigHttpLibrary()

__all__ = [
	"ConfigHttpLibrary",
	"api",
	"export_maix_to_openapi",
	"import_openapi_to_maix_config",
]
