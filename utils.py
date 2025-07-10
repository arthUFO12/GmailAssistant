import threading
from functools import wraps

def synchronized(func):
    lock = threading.Lock()

    @wraps(func)
    def wrapper(*args, **kwargs):
        with lock:
            return func(*args, **kwargs)
    
    return wrapper