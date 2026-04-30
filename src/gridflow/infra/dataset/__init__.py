"""Infra-layer dataset registries (filesystem-backed)."""

from .filesystem_registry import FilesystemDatasetRegistry, InMemoryDatasetRegistry

__all__ = ("FilesystemDatasetRegistry", "InMemoryDatasetRegistry")
