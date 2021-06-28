__version__ = '0.4.0'
""" str: Library version. """
from .motion_controller import MotionController
from . import enums
__all__ = ["MotionController", "enums"]
