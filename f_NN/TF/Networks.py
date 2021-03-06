from f_NN.TF.Layers import *
from f_NN.TF.Optimizers import *

from Util.Bases import ClassifierBase
from Util.Metas import ClassifierMeta
from Util.Timing import Timing
from Util.ProgressBar import ProgressBar


class NNVerbose:
    NONE = 0
    EPOCH = 1
    METRICS = 2
    METRICS_DETAIL = 3
    DETAIL = 4
    DEBUG = 5


class NN(ClassifierBase, metaclass=ClassifierMeta):
    NNTiming = Timing()

    def __init__(self):
        self._layers = []
        self._optimizer = None
        self._current_dimension = 0
        self._metrics, self._metric_names, self._logs = [], [], {}

        self._tfx = self._tfy = None
        self._tf_weights, self._tf_bias = [], []
        self._cost = self._y_pred = None

        self.verbose = 0
        self._train_step = None
        self._sess = tf.Session()

    @NNTiming.timeit(level=1)
    def _get_prediction(self, x, name=None, batch_size=1e6, verbose=None, out_of_sess=False):
        if verbose is None:
            verbose = self.verbose
        single_batch = int(batch_size / np.prod(x.shape[1:]))
        if not single_batch:
            single_batch = 1
        if single_batch >= len(x):
            if not out_of_sess:
                return self._y_pred.eval(feed_dict={self._tfx: x})
            with self._sess.as_default():
                x = x.astype(np.float32)
                return self._get_rs(x).eval(feed_dict={self._tfx: x})
        epoch = int(len(x) / single_batch)
        if not len(x) % single_batch:
            epoch += 1
        name = "Prediction" if name is None else "Prediction ({})".format(name)
        sub_bar = ProgressBar(min_value=0, max_value=epoch, name=name)
        if verbose >= NNVerbose.METRICS:
            sub_bar.start()
        if not out_of_sess:
            rs = [self._y_pred.eval(feed_dict={self._tfx: x[:single_batch]})]
        else:
            rs = [self._get_rs(x[:single_batch])]
        count = single_batch
        if verbose >= NNVerbose.METRICS:
            sub_bar.update()
        while count < len(x):
            count += single_batch
            if count >= len(x):
                if not out_of_sess:
                    rs.append(self._y_pred.eval(feed_dict={self._tfx: x[count - single_batch:]}))
                else:
                    rs.append(self._get_rs(x[count - single_batch:]))
            else:
                if not out_of_sess:
                    rs.append(self._y_pred.eval(feed_dict={self._tfx: x[count - single_batch:count]}))
                else:
                    rs.append(self._get_rs(x[count - single_batch:count]))
            if verbose >= NNVerbose.METRICS:
                sub_bar.update()
        if out_of_sess:
            with self._sess.as_default():
                rs = [_rs.eval() for _rs in rs]
        return np.vstack(rs)

    @staticmethod
    @NNTiming.timeit(level=4)
    def _get_w(shape):
        initial = tf.truncated_normal(shape, stddev=0.1)
        return tf.Variable(initial, name="w")

    @staticmethod
    @NNTiming.timeit(level=4)
    def _get_b(shape):
        initial = tf.constant(0.1, shape=shape)
        return tf.Variable(initial, name="b")

    @NNTiming.timeit(level=4)
    def _add_weight(self, shape):
        w_shape = shape
        b_shape = shape[1],
        self._tf_weights.append(self._get_w(w_shape))
        self._tf_bias.append(self._get_b(b_shape))

    @NNTiming.timeit(level=1)
    def _get_rs(self, x, y=None):
        _cache = self._layers[0].activate(x, self._tf_weights[0], self._tf_bias[0])
        for i, layer in enumerate(self._layers[1:]):
            if i == len(self._layers) - 2:
                if y is None:
                    return tf.matmul(_cache, self._tf_weights[-1]) + self._tf_bias[-1]
                return layer.activate(_cache, self._tf_weights[i + 1], self._tf_bias[i + 1], y)
            _cache = layer.activate(_cache, self._tf_weights[i + 1], self._tf_bias[i + 1])
        return _cache

    def _append_log(self, x, y, y_classes, name, out_of_sess=False):
        y_pred = self._get_prediction(x, name, out_of_sess=out_of_sess)
        y_pred_class = np.argmax(y_pred, axis=1)
        for i, metric in enumerate(self._metrics):
            self._logs[name][i].append(metric(y_classes, y_pred_class))
        if not out_of_sess:
            self._logs[name][-1].append(self._layers[-1].calculate(y, y_pred).eval())
        else:
            with self._sess.as_default():
                self._logs[name][-1].append(self._layers[-1].calculate(y, y_pred).eval())

    def _print_metric_logs(self, data_type):
        print()
        print("=" * 47)
        for i, name in enumerate(self._metric_names):
            print("{:<16s} {:<16s}: {:12.8}".format(
                data_type, name, self._logs[data_type][i][-1]))
        print("{:<16s} {:<16s}: {:12.8}".format(
            data_type, "loss", self._logs[data_type][-1][-1]))
        print("=" * 47)

    @NNTiming.timeit(level=4, prefix="[API] ")
    def _preview(self):
        if not self._layers:
            rs = "None"
        else:
            rs = (
                "Input  :  {:<10s} - {}\n".format("Dimension", self._layers[0].shape[0]) +
                "\n".join(
                    ["Layer  :  {:<10s} - {}".format(
                        _layer.name, _layer.shape[1]
                    ) for _layer in self._layers[:-1]]
                ) + "\nCost   :  {:<10s}".format(self._layers[-1].name)
            )
        print("=" * 30 + "\n" + "Structure\n" + "-" * 30 + "\n" + rs + "\n" + "=" * 30)
        print("Optimizer")
        print("-" * 30)
        print(self._optimizer)
        print("=" * 30)

    @NNTiming.timeit(level=4, prefix="[API] ")
    def add(self, layer):
        if not self._layers:
            self._layers, self._current_dimension = [layer], layer.shape[1]
            self._add_weight(layer.shape)
        else:
            _next = layer.shape[0]
            layer.shape = (self._current_dimension, _next)
            self._layers.append(layer)
            self._add_weight((self._current_dimension, _next))
            self._current_dimension = _next

    @NNTiming.timeit(level=1, prefix="[API] ")
    def fit(self, x, y, lr=0.01, epoch=10, batch_size=128, train_rate=None,
            optimizer="Adam", metrics=None, record_period=100, verbose=0):
        self.verbose = verbose
        self._optimizer = OptFactory().get_optimizer_by_name(optimizer, lr)
        self._tfx = tf.placeholder(tf.float32, shape=[None, x.shape[1]])
        self._tfy = tf.placeholder(tf.float32, shape=[None, y.shape[1]])
        self._preview()

        if train_rate is not None:
            train_rate = float(train_rate)
            train_len = int(len(x) * train_rate)
            shuffle_suffix = np.random.permutation(int(len(x)))
            x, y = x[shuffle_suffix], y[shuffle_suffix]
            x_train, y_train = x[:train_len], y[:train_len]
            x_test, y_test = x[train_len:], y[train_len:]
        else:
            x_train = x_test = x
            y_train = y_test = y
        y_train_classes = np.argmax(y_train, axis=1)
        y_test_classes = np.argmax(y_test, axis=1)

        train_len = len(x_train)
        batch_size = min(batch_size, train_len)
        do_random_batch = train_len >= batch_size
        train_repeat = int(train_len / batch_size) + 1

        if metrics is None:
            metrics = []
        self._metrics = self.get_metrics(metrics)
        self._metric_names = [_m.__name__ for _m in metrics]
        self._logs = {
            name: [[] for _ in range(len(metrics) + 1)] for name in ("train", "test")
        }

        bar = ProgressBar(min_value=0, max_value=max(1, epoch // record_period), name="Epoch")
        if self.verbose >= NNVerbose.EPOCH:
            bar.start()

        with self._sess.as_default() as sess:

            self._cost = self._get_rs(self._tfx, self._tfy)
            self._y_pred = self._get_rs(self._tfx)
            self._train_step = self._optimizer.minimize(self._cost)
            sess.run(tf.global_variables_initializer())

            sub_bar = ProgressBar(min_value=0, max_value=train_repeat * record_period - 1, name="Iteration")
            for counter in range(epoch):
                if self.verbose >= NNVerbose.EPOCH and counter % record_period == 0:
                    sub_bar.start()
                for _i in range(train_repeat):
                    if do_random_batch:
                        batch = np.random.choice(train_len, batch_size)
                        x_batch, y_batch = x_train[batch], y_train[batch]
                    else:
                        x_batch, y_batch = x_train, y_train
                    self._train_step.run(feed_dict={self._tfx: x_batch, self._tfy: y_batch})
                    if self.verbose >= NNVerbose.EPOCH:
                        if sub_bar.update() and self.verbose >= NNVerbose.METRICS_DETAIL:
                            self._append_log(x_train, y_train, y_train_classes, "train")
                            self._append_log(x_test, y_test, y_test_classes, "test")
                            self._print_metric_logs("train")
                            self._print_metric_logs("test")
                if self.verbose >= NNVerbose.EPOCH:
                    sub_bar.update()
                if (counter + 1) % record_period == 0:
                    self._append_log(x_train, y_train, y_train_classes, "train")
                    self._append_log(x_test, y_test, y_test_classes, "test")
                    if self.verbose >= NNVerbose.METRICS:
                        self._print_metric_logs("train")
                        self._print_metric_logs("test")
                    if self.verbose >= NNVerbose.EPOCH:
                        bar.update(counter // record_period + 1)
                        sub_bar = ProgressBar(min_value=0, max_value=train_repeat * record_period - 1, name="Iteration")

    @NNTiming.timeit(level=1, prefix="[API] ")
    def predict(self, x, get_raw_results=False):
        y_pred = self._get_prediction(np.atleast_2d(x).astype(np.float32), out_of_sess=True)
        if get_raw_results:
            return y_pred
        return np.argmax(y_pred, axis=1)
