import random
import sys
from typing import Callable, Dict, Tuple

import gym
import jax
import jax.numpy as jnp
from chex import dataclass, Array, Numeric, PRNGKey, Scalar

from reinforced_lib.exts import IEEE_802_11_ax


gym.envs.registration.register(
    id='RASimEnv-v1',
    entry_point='examples.ra-sim.sim:RASimEnv'
)


# CW constraints
MIN_CW_EXP = 4
MAX_CW_EXP = 10

# mean value based on the ns-3 static simulation with 1 station, ideal channel, AMPDU on, and constant MCS
FRAMES_PER_SECOND = 188

# based on the ns-3 static simulation with 1 station, ideal channel, and constant MCS
AMPDU_SIZES = jnp.array([3, 6, 9, 12, 18, 25, 28, 31, 37, 41, 41, 41])

# default values used by the ns-3 simulator
# https://www.nsnam.org/docs/models/html/wifi-testing.html#packet-error-rate-performance
DEFAULT_NOISE = -93.97
DEFAULT_TX_POWER = 16.0206

# LogDistance channel model
# https://www.nsnam.org/docs/models/html/propagation.html#logdistancepropagationlossmodel
REFERENCE_SNR = DEFAULT_TX_POWER - DEFAULT_NOISE
REFERENCE_LOSS = 46.6777
EXPONENT = 3.0


def distance_to_snr(distance: Numeric) -> Numeric:
    return REFERENCE_SNR - (REFERENCE_LOSS + 10 * EXPONENT * jnp.log10(distance))


@dataclass
class RASimState:
    time: Array
    snr: Array
    ptr: jnp.int32
    cw: jnp.int32


@dataclass
class Env:
    init: Callable
    step: Callable


def ra_sim(
        simulation_time: Scalar,
        velocity: Scalar,
        initial_position: Scalar,
        n_wifi: jnp.int32,
        total_frames: jnp.int32
) -> Env:

    wifi_ext = IEEE_802_11_ax()
    phy_rates = jnp.array(wifi_ext._wifi_phy_rates)

    @jax.jit
    def init() -> Tuple[RASimState, Dict]:
        distance = jnp.abs(jnp.linspace(0.0, simulation_time * velocity, total_frames) + initial_position)

        state = RASimState(
            time=jnp.linspace(0.0, simulation_time, total_frames),
            snr=distance_to_snr(distance),
            ptr=0,
            cw=MIN_CW_EXP
        )

        return state, _get_env_state(state, 0, 0)

    def _get_env_state(state: RASimState, n_successful: jnp.int32, n_failed: jnp.int32) -> Dict:
        return {
            'time': state.time[state.ptr],
            'n_successful': n_successful,
            'n_failed': n_failed,
            'n_wifi': n_wifi,
            'power': DEFAULT_TX_POWER,
            'cw': 2 ** state.cw - 1,
            'mcs': 0
        }

    @jax.jit
    def step(state: RASimState, action: jnp.int32, key: PRNGKey) -> Tuple[RASimState, Dict, Scalar, jnp.bool_]:
        n_all = AMPDU_SIZES[action]
        n_successful = (n_all * wifi_ext.success_probability(state.snr[state.ptr])[action]).astype(jnp.int32)
        collision = wifi_ext.collision_probability(n_wifi) > jax.random.uniform(key)

        n_successful = n_successful * (1 - collision)
        n_failed = n_all - n_successful

        cw = jnp.where(n_successful > 0, MIN_CW_EXP, state.cw + 1)
        cw = jnp.where(cw <= MAX_CW_EXP, cw, MAX_CW_EXP)

        state = RASimState(
            time=state.time,
            snr=state.snr,
            ptr=state.ptr + 1,
            cw=cw
        )

        terminated = state.ptr == len(state.time)
        reward = jnp.where(n_all > 0, phy_rates[action] * n_successful / n_all, 0.0)

        return state, _get_env_state(state, n_successful, n_failed), reward, terminated

    return Env(
        init=init,
        step=step
    )


class RASimEnv(gym.Env):
    """
    Simple Rate Adaptation Simulator for IEEE 802.11ax networks. Calculates if packet has been transmitted
    successfully based on approximated success probability for a given distance and SNR (according to the
    LogDistance channel model) and approximated collision probability (calculated experimentally).
    Environment simulates Wi-Fi networks with 20 MHz width channel, guard interval set to 3200 ns,
    1 spatial stream, and the packet is treated as indivisible.
    """

    def __init__(self) -> None:
        self.action_space = gym.spaces.Discrete(12)
        self.observation_space = gym.spaces.Dict({
            'time': gym.spaces.Box(0.0, jnp.inf, (1,)),
            'n_successful': gym.spaces.Box(0, jnp.inf, (1,), jnp.int32),
            'n_failed': gym.spaces.Box(0, jnp.inf, (1,), jnp.int32),
            'n_wifi': gym.spaces.Box(1, jnp.inf, (1,), jnp.int32),
            'power': gym.spaces.Box(-jnp.inf, jnp.inf, (1,)),
            'cw': gym.spaces.Discrete(32767),
            'mcs': gym.spaces.Discrete(12)
        })

        self.options = {
            'initial_position': 0.0,
            'n_wifi': 1,
            'simulation_time': 25.0,
            'velocity': 2.0
        }

    def reset(
            self,
            seed: int = None,
            options: Dict = None
    ) -> Tuple[gym.spaces.Dict, Dict]:
        """
        Resets the environment to the initial state.

        Parameters
        ----------
        seed : int
            An integer used as the random key.
        options : dict
            Dictionary containing simulation parameters, i.e. `initial_position`, `n_wifi`, `simulation_time`, `velocity`.

        Returns
        -------
        state : tuple[dict, dict]
            Initial environment state.
        """

        seed = seed if seed else random.randint(0, sys.maxsize)
        super().reset(seed=seed)
        self.key = jax.random.PRNGKey(seed)

        options = options if options else {}
        self.options.update(options)

        self.sim = ra_sim(
            self.options['simulation_time'],
            self.options['velocity'],
            self.options['initial_position'],
            self.options['n_wifi'],
            int(self.options['simulation_time'] * FRAMES_PER_SECOND)
        )
        self.state, env_state = self.sim.init()

        return env_state, {}

    def step(self, action: int) -> Tuple[gym.spaces.Dict, float, bool, bool, Dict]:
        """
        Performs one step in the environment and returns new environment state.

        Parameters
        ----------
        action : int
            Action to perform in the environment.

        Returns
        -------
        out : tuple[dict, float, bool, bool, dict]
            Environment state after performing a step, reward, and info about termination.
        """

        step_key, self.key = jax.random.split(self.key)
        self.state, *env_state = self.sim.step(self.state, action, step_key)

        return *env_state, False, {}
