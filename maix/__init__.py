"""Public package API for config-driven HTTP clients."""

from .manager import ConfigHttpLibrary

# Global singleton that can be imported from anywhere in the project.
api = ConfigHttpLibrary()

__all__ = ["ConfigHttpLibrary", "api"]
