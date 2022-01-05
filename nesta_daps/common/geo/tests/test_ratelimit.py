import pytest
import time

from nesta_daps.common.geo.ratelimit import ratelimit

def test_rate_limit():
    dummy_func = lambda : None
    wrapper = ratelimit(1)
    wrapped = wrapper(dummy_func)
    previous_time = time.time()
    for i in range(0, 3):
        wrapped()
        assert time.time() - previous_time > 1
        previous_time = time.time()