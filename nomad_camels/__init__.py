"""NOMAD-CAMELS package.

Import the GUI launcher only when it is requested. This keeps package and
headless-worker imports (such as Windows Dash plotting subprocesses) from
initializing PySide6 unnecessarily.
"""

__version__ = "1.3.0"
__all__ = ["start_camels", "__version__"]


def __getattr__(name):
    if name == "start_camels":
        from .CAMELS_start import start_camels

        return start_camels
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
