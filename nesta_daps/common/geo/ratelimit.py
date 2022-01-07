'''
ratelimit
=========
Apply rate limiting at a threshold per second
'''

import time
from types import MethodType

def ratelimit(max_per_second: float) -> MethodType:
    '''
    Args:
        max_per_second (float): Number of permitted hits per second
    '''
    min_interval = 1.0 / float(max_per_second)
    def decorate(func):
        last_time_called = [time.perf_counter()]  # `list`s are globally persistified
        def rate_limited(*args, **kargs):
            elapsed = time.perf_counter() - last_time_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            ret = func(*args,**kargs)
            last_time_called[0] = time.perf_counter()
            return ret
        return rate_limited  # Note: returning a method
    return decorate  # Note: returning a method
