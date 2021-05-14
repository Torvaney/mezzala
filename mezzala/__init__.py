# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/00_core.ipynb (unless otherwise specified).

__all__ = ['UniformWeight', 'ExponentialWeight', 'DixonColesParameterKey', 'RHO_KEY', 'HFA_KEY', 'AVG_KEY',
           'KeyAdapter', 'AttributeAdapter', 'LumpedAdapter', 'DixonColes', 'BaseRate', 'HomeAdvantage', 'TeamStrength',
           'KeyBlock']

# Cell
import abc
import collections
import dataclasses
import itertools
import typing
import functools
import json

import numpy as np
import scipy.stats
import scipy.optimize

# Cell

class UniformWeight:
    @staticmethod
    def __call__(row):
        return 1.0


class ExponentialWeight:
    def __init__(self, epsilon, key):
        self.epsilon = epsilon
        self.key = key

    def __call__(self, row):
        return np.exp(self.epsilon*self.key(row))

# Cell

@dataclasses.dataclass(frozen=True)
class DixonColesParameterKey:
    label: typing.Hashable


# Model constants
RHO_KEY = DixonColesParameterKey('Rho')
HFA_KEY = DixonColesParameterKey('Home-field advantage')
AVG_KEY = DixonColesParameterKey('Average rate')

# Cell


class KeyAdapter:
    def __init__(self, home_team, away_team, home_goals, away_goals):
        self._home_team = home_team
        self._away_team = away_team
        self._home_goals = home_goals
        self._away_goals = away_goals

    def _get_in(self, row, item):
        if isinstance(item, list):
            return functools.reduce(lambda d, i: d[i], item, row)
        return row[item]

    def home_team(self, row):
        return self._get_in(row, self._home_team)

    def away_team(self, row):
        return self._get_in(row, self._away_team)

    def home_goals(self, row):
        return self._get_in(row, self._home_goals)

    def away_goals(self, row):
        return self._get_in(row, self._away_goals)

# Cell


class AttributeAdapter:
    def __init__(self, home_team, away_team, home_goals, away_goals):
        self._home_team = home_team
        self._away_team = away_team
        self._home_goals = home_goals
        self._away_goals = away_goals

    def home_team(self, row):
        return getattr(row, self._home_team)

    def away_team(self, row):
        return getattr(row, self._away_team)

    def home_goals(self, row):
        return getattr(row, self._home_goals)

    def away_goals(self, row):
        return getattr(row, self._away_goals)

# Cell


class LumpedAdapter:
    """ Lump teams who appear below `min_matches` times (default 10) into one team """

    def __init__(self, base_adapter, data, min_matches=10, placeholder=DixonColesParameterKey('Other team')):
        self.base_adapter = base_adapter
        self.min_matches = min_matches
        self.placeholder = placeholder

        self.match_count = None
        self.train(data)

    def home_team(self, row):
        home_team = self.base_adapter.home_team(row)
        if self.match_count[home_team] <= self.min_matches:
            return self.placeholder
        return home_team

    def away_team(self, row):
        away_team = self.base_adapter.away_team(row)
        if self.match_count[away_team] <= self.min_matches:
            return self.placeholder
        return away_team

    def home_goals(self, row):
        return self.base_adapter.home_goals(row)

    def away_goals(self, row):
        return self.base_adapter.away_goals(row)

    def fit(self, data):
        home_match_count = collections.Counter(self.base_adapter.home_team(row) for row in data)
        away_match_count = collections.Counter(self.base_adapter.away_team(row) for row in data)
        self.match_count = home_match_count + away_match_count

# Cell


class DixonColes:
    def __init__(self, adapter, blocks, weight=UniformWeight(), params=None):
        self.params = params
        self.adapter = adapter
        self.weight = weight
        self._blocks = blocks

    @property
    def blocks(self):
        # Make sure blocks are always in the correct order
        return sorted(self._blocks, key=lambda x: -x.PRIORITY)

    def home_goals(self, row):
        """ Returns home goals scored """
        return self.adapter.home_goals(row)

    def away_goals(self, row):
        """ Returns away goals scored """
        return self.adapter.away_goals(row)

    def parse_params(self, data):
        """ Returns a tuple of (parameter_names, [constraints]) """
        base_params = [RHO_KEY]
        block_params = list(itertools.chain(*[b.param_keys(self.adapter, data) for b in self.blocks]))
        return (
            block_params + base_params,
            list(itertools.chain(*[b.constraints(self.adapter, data) for b in self.blocks]))
        )

    def home_rate(self, params, row):
        """ Returns home goalscoring rate """
        terms = itertools.chain(*[b.home_terms(self.adapter, row) for b in self.blocks])
        return np.exp(sum(params[t] for t in terms))

    def away_rate(self, params, row):
        """ Returns away goalscoring rate """
        terms = itertools.chain(*[b.away_terms(self.adapter, row) for b in self.blocks])
        return np.exp(sum(params[t] for t in terms))

    # Core methods

    @staticmethod
    def _assign_params(param_keys, param_values):
        return dict(zip(param_keys, param_values))

    @staticmethod
    def _tau(home_goals, away_goals, home_rate, away_rate, rho):
        tau = np.ones(len(home_goals))
        tau = np.where((home_goals == 0) & (away_goals == 0), 1 - home_rate*away_rate*rho, tau)
        tau = np.where((home_goals == 0) & (away_goals == 1), 1 + home_rate*rho, tau)
        tau = np.where((home_goals == 1) & (away_goals == 0), 1 + away_rate*rho, tau)
        tau = np.where((home_goals == 1) & (away_goals == 1), 1 - rho, tau)
        return tau

    def _log_like(self, home_goals, away_goals, home_rate, away_rate, params):
        rho = params[RHO_KEY]
        return (
            scipy.stats.poisson.logpmf(home_goals, home_rate) +
            scipy.stats.poisson.logpmf(away_goals, away_rate) +
            np.log(self._tau(home_goals, away_goals, home_rate, away_rate, rho))
        )

    def objective_fn(self, data, param_keys, xs):
        params = self._assign_params(param_keys, xs)

        home_goals, away_goals = np.empty(len(data)), np.empty(len(data))
        home_rate, away_rate = np.empty(len(data)), np.empty(len(data))
        weights = np.empty(len(data))

        # NOTE: Should data adapter define the iteration?
        # E.g. dataframe adapter?
        for i, row in enumerate(data):
            home_goals[i] = self.home_goals(row)
            away_goals[i] = self.away_goals(row)
            home_rate[i] = self.home_rate(params, row)
            away_rate[i] = self.away_rate(params, row)
            weights[i] = self.weight(row)

        log_like = self._log_like(home_goals, away_goals, home_rate, away_rate, params)

        pseudo_log_like = log_like * weights
        return -np.sum(pseudo_log_like)

    def fit(self, data, **kwargs):
        param_keys, constraints = self.parse_params(data)

        init_params = (
            np.asarray([self.params.get(p, 0) for p in param_keys])
            if self.params
            else np.zeros(len(param_keys))
        )

        # Optimise!
        estimate = scipy.optimize.minimize(
            lambda xs: self.objective_fn(data, param_keys, xs),
            x0=init_params,
            constraints=constraints,
            **kwargs
        )

        # Parse the estimates into parameter map
        self.params = self._assign_params(param_keys, estimate.x)

        return self

    def predict_one(self, row, up_to=26):
        scorelines = list(itertools.product(range(up_to), repeat=2))

        home_goals = [h for h, a in scorelines]
        away_goals = [a for h, a in scorelines]
        home_rate = self.home_rate(self.params, row)
        away_rate = self.away_rate(self.params, row)

        probs = np.exp(self._log_like(home_goals, away_goals, home_rate, away_rate, self.params))

        # TODO: add a mixin/adapter to customise the indexing in the results dicts?
        # OR just use a custom dataclass for these...
        return [dict(zip(['home_goals', 'away_goals', 'probability'], vals))
                for vals in zip(home_goals, away_goals, probs)]

    def predict(self, data, up_to=26):
        scorelines = [self.predict_one(row, up_to=up_to) for row in data]
        return scorelines

# Internal Cell


class ModelBlockABC(abc.ABC):
    """
    Base class for model blocks
    """
    PRIORITY = 0

    def param_keys(self, adapter, data):
        return []

    def constraints(self, adapter, data):
        return []

    def home_terms(self, adapter, data):
        return []

    def away_terms(self, adapter, data):
        return []

# Cell


class BaseRate(ModelBlockABC):
    def __init__(self):
        pass

    def param_keys(self, adapter, data):
        return [AVG_KEY]

    def home_terms(self, adapter, row):
        return [AVG_KEY]

    def away_terms(self, adapter, row):
        return [AVG_KEY]

# Cell


class HomeAdvantage(ModelBlockABC):
    def __init__(self):
        # TODO: allow HFA on/off depending on the data?
        pass

    def param_keys(self, adapter, data):
        return [HFA_KEY]

    def home_terms(self, adapter, row):
        return [HFA_KEY]

# Cell


class TeamStrength(ModelBlockABC):
    # This is a gross hack so that we know that the
    # team strength parameters come first, and thus can
    # do the constraints (which are positionally indexed)
    PRIORITY = 1

    def __init__(self):
        pass

    def _teams(self, adapter, data):
        return set(adapter.home_team(r) for r in data) | set(adapter.away_team(r) for r in data)

    def offence_key(self, label):
        return DixonColesParameterKey(('Offence', label))

    def defence_key(self, label):
        return DixonColesParameterKey(('Defence', label))

    def param_keys(self, adapter, data):
        teams = self._teams(adapter, data)

        offence = [self.offence_key(t) for t in teams]
        defence = [self.defence_key(t) for t in teams]

        return offence + defence

    def constraints(self, adapter, data):
        n_teams = len(self._teams(adapter, data))
        return [
            # Force team offence parameters to average to 1
            {'fun': lambda x: 1 - np.mean(np.exp(x[0:n_teams])),
             'type': 'eq'},
        ]

    def home_terms(self, adapter, row):
        return [
            self.offence_key(adapter.home_team(row)),
            self.defence_key(adapter.away_team(row))
        ]

    def away_terms(self, adapter, row):
        return [
            self.offence_key(adapter.away_team(row)),
            self.defence_key(adapter.home_team(row))
        ]

# Cell


class KeyBlock(ModelBlockABC):
    """
    Generic model block for adding arbitrary model terms to both home and away team
    """
    def __init__(self, key):
        self.key = key

    def param_keys(self, adapter, data):
        return list(set(self.key(r) for r in data))

    def home_terms(self, adapter, row):
        return [self.key(row)]

    def away_terms(self, adapter, row):
        return [self.key(row)]