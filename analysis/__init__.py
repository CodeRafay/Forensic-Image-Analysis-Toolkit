# Lazy imports - modules are only loaded when first accessed.
# This prevents loading heavy libraries (cv2, scipy, matplotlib, numpy)
# at app startup when the user may only use one or two analysis tabs.

import importlib as _importlib

_MODULE_NAMES = [
    "ela",
    "metadata_analysis",
    "histogram_analysis",
    "noise_map",
    "jpeg_ghost",
    "quant_table",
    "cmfd",
    "prnu",
    "frequency_analysis",
    "deepfake_detector",
    "resampling_detector",
    "steganography_detection",
    "hash_verification",
    "util",
]

__all__ = list(_MODULE_NAMES)


def __getattr__(name):
    """Lazily import sub-modules on first access."""
    if name in _MODULE_NAMES:
        mod = _importlib.import_module(f".{name}", __name__)
        globals()[name] = mod  # cache so subsequent accesses are fast
        return mod
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
