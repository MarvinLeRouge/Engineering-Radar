from radar_online.rate_limit import SlidingWindowLimiter


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_allows_up_to_the_limit_then_reports_the_wait():
    clock = _Clock()
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60, clock=clock)

    assert limiter.hit("ada") is None
    clock.now += 10
    assert limiter.hit("ada") is None
    clock.now += 5

    assert limiter.hit("ada") == 45


def test_a_slot_frees_up_once_the_oldest_hit_leaves_the_window():
    clock = _Clock()
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60, clock=clock)
    limiter.hit("ada")

    clock.now += 60

    assert limiter.hit("ada") is None


def test_refused_hits_do_not_extend_the_wait():
    clock = _Clock()
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60, clock=clock)
    limiter.hit("ada")
    clock.now += 30
    limiter.hit("ada")

    clock.now += 30

    assert limiter.hit("ada") is None


def test_keys_have_separate_quotas():
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60, clock=_Clock())
    limiter.hit("ada")

    assert limiter.hit("bob") is None
