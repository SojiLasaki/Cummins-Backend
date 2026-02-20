# apps/core/utils.py
import socket

def is_connected(host="8.8.8.8", port=53, timeout=3):
    """
    Returns True if connected to the internet
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception:
        return False