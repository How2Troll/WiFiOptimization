import os.path
from collections import defaultdict
from datetime import datetime
from typing import List

import jax.numpy as jnp
import matplotlib.pyplot as plt
from chex import Array, Scalar

from reinforced_lib.logs import BaseLogger, Source


class PlotsLogger(BaseLogger):
    """
    Logger that presents and saves values as line plots. Offers smoothing of the curve and multiple curves
    in a single plot while for arrays.

    Parameters
    ----------
    plots_dir : str, default="~"
        Output directory for plots.
    plots_ext : str, default="svg"
        Extension of saved plots.
    plots_smoothing : float, default=0.6
        Weight of the exponential moving average (EMA/EWMA) [3]_ used for smoothing.
        Weight must be in [0, 1).
    scatter : bool, default=False
        Set to `True` if you want a scatter plot instead of a line plot. `plots_smoothing` parameter does
        not apply to scatter plot.

    References
    ----------
    .. [3] https://en.wikipedia.org/wiki/Moving_average#Exponential_moving_average
    """

    def __init__(
        self,
        plots_dir: str = None,
        plots_ext: str = 'svg',
        plots_smoothing: Scalar = 0.6,
        scatter: bool = False,
        **kwargs
    ) -> None:
        super().__init__(**kwargs)

        self._plots_dir = plots_dir if plots_dir else os.path.expanduser("~")
        self._plots_ext = plots_ext
        self._plots_smoothing = plots_smoothing
        self._scatter = scatter

        assert 1 > self._plots_smoothing >= 0

        self._plots_values = defaultdict(list)
        self._plots_names = []

    def init(self, sources: List[Source]) -> None:
        """
        Creates list of all sources names.

        Parameters
        ----------
        sources : list[Source]
            List containing all sources for the logger.
        """

        self._plots_names = list(map(self.source_to_name, sources))

    def finish(self) -> None:
        """
        Shows generated plots and saves them to the output directory with specified extension
        (names of files follow the pattern ``"rlib-plot-[source]-[date]-[time].[ext]"``).
        """

        def lineplot(values: List, alpha: Scalar = 1.0, label: bool = False) -> None:
            values = jnp.array(values)
            values = jnp.squeeze(values)

            if values.ndim == 1:
                plt.plot(values, alpha=alpha, c='C0')
            elif values.ndim == 2:
                for i, val in enumerate(jnp.array(values).T):
                    plt.plot(val, alpha=alpha, c=f'C{i % 10}', label=i if label else '')
                plt.legend()
        
        def scatterplot(values: List, label: bool = False) -> None:
            values = jnp.array(values)
            values = jnp.squeeze(values)
            xs = range(1, len(values) + 1)

            if values.ndim == 1:
                plt.scatter(xs, values, c='C0', marker='.', s=4)
            elif values.ndim == 2:
                for i, val in enumerate(jnp.array(values).T):
                    plt.scatter(xs, val, c=f'C{i % 10}', label=i if label else '', marker='.', s=4)
                plt.legend()

        now = datetime.now()

        for name, values in self._plots_values.items():
            filename = f'rlib-plot-{name}-{now.strftime("%Y%m%d")}-{now.strftime("%H%M%S")}.{self._plots_ext}'

            if self._scatter:
                scatterplot(values, True)
            else:
                smoothed = self._exponential_moving_average(values, self._plots_smoothing)
                lineplot(values, alpha=0.3)
                lineplot(smoothed, label=True)
            
            plt.title(name)
            plt.xlabel('step')
            plt.savefig(os.path.join(self._plots_dir, filename), bbox_inches='tight')
            plt.show()

    @staticmethod
    def _exponential_moving_average(values: List, weight: Scalar) -> List:
        """
        Calculates exponential moving average (EMA/EWMA) [3]_ to smooth plotted values.

        Parameters
        ----------
        values : array_like
            Original values.
        weight : float
            Weight of the EMA, must be in [0, 1).

        Returns
        -------
        smoothed : array_like
            Smoothed values.
        """

        smoothed = [values[0]]

        for value in values[1:]:
            smoothed.append((1 - weight) * value + weight * smoothed[-1])

        return smoothed

    def log_scalar(self, source: Source, value: Scalar) -> None:
        """
        Adds the given scalar to plots values.

        Parameters
        ----------
        source : Source
            Source of the logged value.
        value : float
            Scalar to log.
        """

        self._plots_values[self.source_to_name(source)].append(value)

    def log_array(self, source: Source, value: Array) -> None:
        """
        Adds the given array to plots values.

        Parameters
        ----------
        source : Source
            Source of the logged value.
        value : array_like
            Array to log.
        """

        self._plots_values[self.source_to_name(source)].append(value)