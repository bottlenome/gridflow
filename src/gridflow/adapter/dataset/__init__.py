"""Adapter-layer dataset loaders.

Spec: ``docs/dataset_contribution.md``.

Each concrete loader is a separate module so contributors can add new
sources by adding a single file.
"""

from .synthetic_loader import SYNTHETIC_VPP_METADATA, SyntheticLoader

__all__ = ("SyntheticLoader", "SYNTHETIC_VPP_METADATA")
