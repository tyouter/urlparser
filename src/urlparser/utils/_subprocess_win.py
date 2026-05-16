"""Windows subprocess helper: suppresses console window flashes."""
import subprocess
import sys

# CREATE_NO_WINDOW = 0x08000000
_CREATE_NO_WINDOW = 0x08000000


def run_nowindow(args, **kwargs):
    """subprocess.run with CREATE_NO_WINDOW on Windows (suppresses cmd popup)."""
    if sys.platform == 'win32':
        kwargs.setdefault('creationflags', 0)
        kwargs['creationflags'] |= _CREATE_NO_WINDOW
    return subprocess.run(args, **kwargs)
