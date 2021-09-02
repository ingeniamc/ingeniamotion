__version__ = '0.4.1'
""" str: Library version. """
from .motion_controller import MotionController
from . import enums
__all__ = ["MotionController", "enums"]
