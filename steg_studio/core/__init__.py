# steg_studio/core/__init__.py
"""
Public API for the steganography core.
Import everything the GUI needs from here so gui/ only ever does:
    from steg_studio.core import encode_text, ...
"""
from .image_info   import get_image_info, estimate_encrypted_size   # noqa: F401
from .encoder      import encode_text, encode_file, encode_audio     # noqa: F401
from .decoder      import decode                                      # noqa: F401
from .decoder      import check_magic                                # noqa: F401
