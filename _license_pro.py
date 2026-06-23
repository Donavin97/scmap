"""Pro edition license verification via compiled license_check.so.

Falls back to community stub (always unlicensed) if the .so is missing
or the certificate is invalid.
"""

import ctypes
import os

_SEARCH_PATHS = [
    os.path.join(os.path.expanduser('~'), '.seiscomp', 'licenses'),
    os.path.join(os.path.expanduser('~'), 'seiscomp', 'share', 'licenses'),
    os.path.join(os.sep, 'home', 'seismocomp', 'seiscomp', 'share', 'licenses'),
    os.path.dirname(os.path.abspath(__file__)),
]

_so = None
_is_licensed = False
_customer = None
_error = None


def _init():
    global _so, _is_licensed, _customer, _error
    so_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'license_check.so')
    if not os.path.isfile(so_path):
        _error = 'license_check.so not found'
        return
    try:
        _so = ctypes.CDLL(so_path)
        _so.verify_license.argtypes = [ctypes.c_char_p]
        _so.verify_license.restype = ctypes.c_int
        _so.get_error.restype = ctypes.c_char_p
        _so.get_customer.restype = ctypes.c_char_p
    except Exception as e:
        _error = f'failed to load license_check.so: {e}'
        return

    cert_path = _find_cert()
    if cert_path is None:
        _error = 'no scmap.crt found in search paths'
        return

    rc = _so.verify_license(cert_path.encode())
    if rc == 0:
        _is_licensed = True
        name = _so.get_customer()
        _customer = name.decode() if name else None
    else:
        err = _so.get_error()
        _error = err.decode() if err else 'certificate verification failed'


def _find_cert():
    for path in _SEARCH_PATHS:
        candidate = os.path.join(path, 'scmap.crt')
        if os.path.isfile(candidate):
            return candidate
    return None


def is_licensed():
    return _is_licensed


def customer_name():
    return _customer


def error():
    return _error


# Verify on import
_init()
