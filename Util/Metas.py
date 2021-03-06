import time
import numpy as np
from abc import ABCMeta
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

from Util.Timing import Timing


class TimingMeta(type):
    def __new__(mcs, *args, **kwargs):
        name, bases, attr = args[:3]
        try:
            _timing = attr[name + "Timing"]
        except KeyError:
            _timing = Timing()
            attr[name + "Timing"] = _timing

        for _name, _value in attr.items():
            if "__" in _name or "timing" in _name or "estimate" in _name:
                continue
            _str_val = str(_value)
            if "<" not in _str_val and ">" not in _str_val:
                continue
            if _str_val.find("function") >= 0 or _str_val.find("staticmethod") >= 0 or _str_val.find("property") >= 0:
                attr[_name] = _timing.timeit(level=2)(_value)

        def __str__(self):
            try:
                return self.name
            except AttributeError:
                return name

        def __repr__(self):
            return str(self)

        def feed_timing(self, timing):
            setattr(self, name + "Timing", timing)

        def show_timing_log(self, level=2):
            getattr(self, name + "Timing").show_timing_log(level)

        for key, value in locals().items():
            if str(value).find("function") >= 0 or str(value).find("property"):
                attr[key] = value

        return type(name, bases, attr)


class ClassifierMeta(type):
    def __new__(mcs, *args, **kwargs):
        name, bases, attr = args[:3]
        try:
            clf_timing = attr[name + "Timing"]
        except KeyError:
            clf_timing = Timing()
            attr[name + "Timing"] = clf_timing

        def __str__(self):
            try:
                return self.name
            except AttributeError:
                return name

        def __repr__(self):
            return str(self)

        def __getitem__(self, item):
            if isinstance(item, str):
                return getattr(self, "_" + item)

        def acc(y, y_pred, weights=None):
            if not isinstance(y, np.ndarray):
                y = np.array(y)
            if not isinstance(y_pred, np.ndarray):
                y_pred = np.array(y_pred)
            if weights is not None:
                return np.sum((y == y_pred) * weights) / len(y)
            return np.sum(y == y_pred) / len(y)

        try:
            init = attr["__init__"]
        except KeyError:
            init = None

        def __init__(self, *_args, **_kwargs):
            if init is not None:
                init(self, *_args, **_kwargs)
            self._metrics = [acc]
            self._available_metrics = {
                "acc": acc
            }

        def get_metrics(self, metrics):
            if len(metrics) == 0:
                for metric in self._metrics:
                    metrics.append(metric)
                return metrics
            for i in range(len(metrics) - 1, -1, -1):
                metric = metrics[i]
                if isinstance(metric, str):
                    try:
                        metrics[i] = self._available_metrics[metric]
                    except AttributeError:
                        metrics.pop(i)
            return metrics

        @clf_timing.timeit(level=1, prefix="[API] ")
        def estimate(self, x, y, metrics=None, tar=None, prefix="Acc"):
            if metrics is None:
                metrics = []
            self.get_metrics(metrics)
            logs, y_pred = [], self.predict(x)
            y = np.array(y)
            if y.ndim == 2:
                y = np.argmax(y, axis=1)
            for metric in metrics:
                logs.append(metric(y, y_pred))
            if tar is None:
                tar = 0
            if isinstance(tar, int):
                print(prefix + ": {:12.8}".format(logs[tar]))
            return logs

        def visualize2d(self, x, y, padding=0.1, dense=200,
                        title=None, show_org=False, show_background=True, emphasize=None):
            axis, labels = np.array(x).T, np.array(y)

            print("=" * 30 + "\n" + str(self))
            decision_function = lambda _xx: self.predict(_xx)

            nx, ny, padding = dense, dense, padding
            x_min, x_max = np.min(axis[0]), np.max(axis[0])
            y_min, y_max = np.min(axis[1]), np.max(axis[1])
            x_padding = max(abs(x_min), abs(x_max)) * padding
            y_padding = max(abs(y_min), abs(y_max)) * padding
            x_min -= x_padding
            x_max += x_padding
            y_min -= y_padding
            y_max += y_padding

            def get_base(_nx, _ny):
                _xf = np.linspace(x_min, x_max, _nx)
                _yf = np.linspace(y_min, y_max, _ny)
                n_xf, n_yf = np.meshgrid(_xf, _yf)
                return _xf, _yf, np.c_[n_xf.ravel(), n_yf.ravel()]

            xf, yf, base_matrix = get_base(nx, ny)

            t = time.time()
            z = decision_function(base_matrix).reshape((nx, ny))
            print("Decision Time: {:8.6} s".format(time.time() - t))

            print("Drawing figures...")
            xy_xf, xy_yf = np.meshgrid(xf, yf, sparse=True)
            if labels.ndim == 1:
                _dic = {c: i for i, c in enumerate(set(labels))}
                n_label = len(_dic)
                labels = np.array([_dic[label] for label in labels])
            else:
                n_label = labels.shape[1]
                labels = np.argmax(labels, axis=1)
            colors = plt.cm.rainbow([i / n_label for i in range(n_label)])[labels]

            if title is None:
                try:
                    title = self.title
                except AttributeError:
                    title = str(self)

            if show_org:
                plt.figure()
                plt.scatter(axis[0], axis[1], c=colors)
                plt.xlim(x_min, x_max)
                plt.ylim(y_min, y_max)
                plt.show()

            plt.figure()
            plt.title(title)
            if show_background:
                plt.pcolormesh(xy_xf, xy_yf, z, cmap=plt.cm.Paired)
            else:
                plt.contour(xf, yf, z, c='k-', levels=[0])
            plt.scatter(axis[0], axis[1], c=colors)
            if emphasize is not None:
                _indices = np.array([False] * len(axis[0]))
                _indices[np.array(emphasize)] = True
                plt.scatter(axis[0][_indices], axis[1][_indices], s=80,
                            facecolors="None", zorder=10)
            plt.xlim(x_min, x_max)
            plt.ylim(y_min, y_max)
            plt.show()

            print("Done.")

        def visualize3d(self, x, y, padding=0.1, dense=100,
                        title=None, show_org=False, show_background=True, emphasize=None):
            if False:
                print(Axes3D.add_artist)
            axis, labels = np.array(x).T, np.array(y)

            print("=" * 30 + "\n" + str(self))
            decision_function = lambda _x: self.predict(_x)

            nx, ny, nz, padding = dense, dense, dense, padding
            x_min, x_max = np.min(axis[0]), np.max(axis[0])
            y_min, y_max = np.min(axis[1]), np.max(axis[1])
            z_min, z_max = np.min(axis[2]), np.max(axis[2])
            x_padding = max(abs(x_min), abs(x_max)) * padding
            y_padding = max(abs(y_min), abs(y_max)) * padding
            z_padding = max(abs(z_min), abs(z_max)) * padding
            x_min -= x_padding
            x_max += x_padding
            y_min -= y_padding
            y_max += y_padding
            z_min -= z_padding
            z_max += z_padding

            def get_base(_nx, _ny, _nz):
                _xf = np.linspace(x_min, x_max, _nx)
                _yf = np.linspace(y_min, y_max, _ny)
                _zf = np.linspace(z_min, z_max, _nz)
                n_xf, n_yf, n_zf = np.meshgrid(_xf, _yf, _zf)
                return _xf, _yf, _zf, np.c_[n_xf.ravel(), n_yf.ravel(), n_zf.ravel()]

            xf, yf, zf, base_matrix = get_base(nx, ny, nz)

            t = time.time()
            z_xyz = decision_function(base_matrix).reshape((nx, ny, nz))
            p_classes = decision_function(x).astype(np.int8)
            _, _, _, base_matrix = get_base(10, 10, 10)
            z_classes = decision_function(base_matrix).astype(np.int8)
            print("Decision Time: {:8.6} s".format(time.time() - t))

            print("Drawing figures...")
            z_xy = np.average(z_xyz, axis=2)
            z_yz = np.average(z_xyz, axis=1)
            z_xz = np.average(z_xyz, axis=0)

            xy_xf, xy_yf = np.meshgrid(xf, yf, sparse=True)
            yz_xf, yz_yf = np.meshgrid(yf, zf, sparse=True)
            xz_xf, xz_yf = np.meshgrid(xf, zf, sparse=True)

            def transform_arr(arr):
                if arr.ndim == 1:
                    _dic = {c: i for i, c in enumerate(set(arr))}
                    n_dim = len(_dic)
                    arr = np.array([_dic[label] for label in arr])
                else:
                    n_dim = arr.shape[1]
                    arr = np.argmax(arr, axis=1)
                return arr, n_dim

            labels, n_label = transform_arr(labels)
            p_classes, _ = transform_arr(p_classes)
            z_classes, _ = transform_arr(z_classes)
            colors = plt.cm.rainbow([i / n_label for i in range(n_label)])

            if title is None:
                try:
                    title = self.title
                except AttributeError:
                    title = str(self)

            if show_org:
                fig = plt.figure()
                ax = fig.add_subplot(111, projection='3d')
                ax.scatter(axis[0], axis[1], axis[2], c=colors[labels])
                plt.show()

            fig = plt.figure(figsize=(16, 4), dpi=100)
            plt.title(title)
            ax1 = fig.add_subplot(131, projection='3d')
            ax2 = fig.add_subplot(132, projection='3d')
            ax3 = fig.add_subplot(133, projection='3d')

            ax1.set_title("Org")
            ax2.set_title("Pred")
            ax3.set_title("Boundary")

            ax1.scatter(axis[0], axis[1], axis[2], c=colors[labels])
            ax2.scatter(axis[0], axis[1], axis[2], c=colors[p_classes], s=15)
            xyz_xf, xyz_yf, xyz_zf = base_matrix[..., 0], base_matrix[..., 1], base_matrix[..., 2]
            ax3.scatter(xyz_xf, xyz_yf, xyz_zf, c=colors[z_classes], s=15)

            plt.show()
            plt.close()

            fig = plt.figure(figsize=(16, 4), dpi=100)
            ax1 = fig.add_subplot(131)
            ax2 = fig.add_subplot(132)
            ax3 = fig.add_subplot(133)

            def _draw(_ax, _x, _xf, _y, _yf, _z):
                if show_background:
                    _ax.pcolormesh(_x, _y, _z > 0, cmap=plt.cm.Paired)
                else:
                    _ax.contour(_xf, _yf, _z, c='k-', levels=[0])

            def _emphasize(_ax, axis0, axis1, _c):
                _ax.scatter(axis0, axis1, c=_c)
                if emphasize is not None:
                    _indices = np.array([False] * len(axis[0]))
                    _indices[np.array(emphasize)] = True
                    _ax.scatter(axis0[_indices], axis1[_indices], s=80,
                                facecolors="None", zorder=10)

            colors = colors[labels]

            ax1.set_title("xy figure")
            _draw(ax1, xy_xf, xf, xy_yf, yf, z_xy)
            _emphasize(ax1, axis[0], axis[1], colors)

            ax2.set_title("yz figure")
            _draw(ax2, yz_xf, yf, yz_yf, zf, z_yz)
            _emphasize(ax2, axis[1], axis[2], colors)

            ax3.set_title("xz figure")
            _draw(ax3, xz_xf, xf, xz_yf, zf, z_xz)
            _emphasize(ax3, axis[0], axis[2], colors)

            plt.show()

            print("Done.")

        def feed_timing(self, timing):
            setattr(self, name + "Timing", timing)

        def show_timing_log(self, level=2):
            getattr(self, name + "Timing").show_timing_log(level)

        for key, value in locals().items():
            if str(value).find("function") >= 0 or str(value).find("property"):
                attr[key] = value

        return type(name, bases, attr)


class SubClassTimingMeta(type):
    def __new__(mcs, *args, **kwargs):
        name, bases, attr = args[:3]
        try:
            timing = getattr(bases[0], bases[0].__name__ + "Timing")
        except AttributeError:
            timing = Timing()
            setattr(bases[0], bases[0].__name__ + "Timing", timing)
        for _name, _value in attr.items():
            if "__" in _name or "timing" in _name or "estimate" in _name:
                continue
            _str_val = str(_value)
            if "<" not in _str_val and ">" not in _str_val:
                continue
            if _str_val.find("function") >= 0 or _str_val.find("staticmethod") >= 0 or _str_val.find("property") >= 0:
                attr[_name] = timing.timeit(level=2)(_value)
        return type(name, bases, attr)


class SubClassChangeNamesMeta(type):
    def __new__(mcs, *args, **kwargs):
        name, bases, attr = args[:3]
        attr["name"] = name
        try:
            init = attr["__init__"]
        except KeyError:
            init = None

        def __init__(self, *_args, **_kwargs):
            if callable(init):
                init(self, *_args, **_kwargs)
            try:
                timing = getattr(bases[0], bases[0].__name__ + "Timing")
                attr[name + "Timing"] = timing
            except AttributeError:
                try:
                    timing = attr[name + "Timing"]
                except KeyError:
                    timing = attr[name + "Timing"] = Timing()
                setattr(bases[0], bases[0].__name__ + "Timing", timing)
            timing.name = name

        attr["__init__"] = __init__
        return type(name, bases, attr)


class SKCompatibleMeta(ABCMeta, ClassifierMeta):
    pass
