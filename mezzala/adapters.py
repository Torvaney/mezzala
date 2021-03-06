# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/adapters.ipynb (unless otherwise specified).

__all__ = ['KeyAdapter', 'AttributeAdapter', 'LumpedAdapter']

# Cell
import collections
import functools

import mezzala.parameters

# Cell


class KeyAdapter:
    """
    Get data from subscriptable objects.
    """

    def __init__(self, home_goals, away_goals, **kwargs):
        self._lookup = {
            'home_goals': home_goals,
            'away_goals': away_goals,
            **kwargs
        }

    def __repr__(self):
        args_repr = ', '.join(f'{k}={repr(v)}' for k, v in self._lookup.items())
        return f'KeyAdapter({args_repr})'

    def _get_in(self, row, item):
        if isinstance(item, list):
            return functools.reduce(lambda d, i: d[i], item, row)
        return row[item]

    def __getattr__(self, key):
        def getter(row):
            return self._get_in(row, self._lookup[key])
        return getter

# Cell


class AttributeAdapter:
    """
    Get data from object attributes.
    """
    def __init__(self, home_goals, away_goals, **kwargs):
        self._lookup = {
            'home_goals': home_goals,
            'away_goals': away_goals,
            **kwargs
        }

    def __repr__(self):
        args_repr = ', '.join(f'{k}={repr(v)}' for k, v in self._lookup.items())
        return f'KeyAdapter({args_repr})'

    def _get_in(self, row, item):
        if isinstance(item, list):
            return functools.reduce(getattr, item, row)
        return getattr(row, item)

    def __getattr__(self, key):
        def getter(row):
            return self._get_in(row, self._lookup[key])
        return getter

# Cell


class LumpedAdapter:
    """
    Lump terms which have appeared below a minimum number of times in
    the training data into a placeholder term
    """

    def __init__(self, base_adapter, **kwargs):
        self.base_adapter = base_adapter

        # Match terms to placeholders
        # If multiple terms have the same placeholder (e.g. Home and Away
        # teams) they will share a counter
        self._term_lookup = kwargs

        self._counters = None

    def __repr__(self):
        args_repr = ', '.join(f'{k}={repr(v)}' for k, v in self._term_lookup.items())
        return f'LumpedAdapter(base_adapter={repr(self.base_adapter)}, {args_repr})'

    def fit(self, data):
        self._counters = {}
        for term, (placeholder, _) in self._term_lookup.items():
            # Initialise with an empty counter if it doesn't already exist
            # We need to do this so that multiple terms sharing the same counter
            # (home and away teams) are shared
            init_counter = self._counters.get(placeholder, collections.Counter())

            counter = collections.Counter(getattr(self.base_adapter, term)(row) for row in data)

            self._counters[placeholder] = init_counter + counter
        return self

    def __getattr__(self, key):
        if not self._counters:
            raise ValueError(
                'No counts found! You need to call `LumpedAdapter.fit` '
                'on the training data before you can use it!'
            )

        def getter(row):
            value = getattr(self.base_adapter, key)(row)
            placeholder, min_obs = self._term_lookup.get(key, (None, None))
            if placeholder and self._counters[placeholder][value] < min_obs:
                return placeholder
            return value
        return getter