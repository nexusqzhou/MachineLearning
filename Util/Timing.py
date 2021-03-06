import time
import wrapt


class Timing:
    _timings = {}
    _enabled = False

    def __init__(self, enabled=True):
        Timing._enabled = enabled
        self.name = None

    def __str__(self):
        return "Timing"

    __repr__ = __str__

    def timeit(self, level=0, name=None, cls_name=None, prefix="[Method] "):
        @wrapt.decorator
        def wrapper(func, instance, args, kwargs):
            if not Timing._enabled:
                return func(*args, **kwargs)
            name_flag = False
            if self.name is not None:
                instance_name = "{:>18s}".format(self.name)
                name_flag = True
            elif instance is not None:
                instance_name = "{:>18s}".format(str(instance))
            else:
                instance_name = " " * 18 if cls_name is None else "{:>18s}".format(cls_name)
            _prefix = "{:>26s}".format(prefix)
            func_name = "{:>28}".format(func.__name__ if name is None else name)
            _name = instance_name + _prefix + func_name
            _t = time.time()
            rs = func(*args, **kwargs)
            _t = time.time() - _t
            try:
                Timing._timings[_name]["timing"] += _t
                Timing._timings[_name]["call_time"] += 1
            except KeyError:
                Timing._timings[_name] = {
                    "level": level,
                    "timing": _t,
                    "call_time": 1,
                    "name_flag": name_flag
                }
            return rs

        return wrapper

    @property
    def timings(self):
        return self._timings

    def show_timing_log(self, level=2):
        print()
        print("=" * 110 + "\n" + "Timing log\n" + "-" * 110)
        if not self.timings:
            print("None")
        else:
            for key in sorted(self.timings.keys()):
                timing_info = self.timings[key]
                if self.name is not None and self.timings[key]["name_flag"]:
                    key = "{:>18s}".format(self.name) + key[18:]
                if level >= timing_info["level"]:
                    print("{:<42s} :  {:12.7} s (Call Time: {:6d})".format(
                        key, timing_info["timing"], timing_info["call_time"]))
        print("-" * 110)
