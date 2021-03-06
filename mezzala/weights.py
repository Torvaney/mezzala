# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/weights.ipynb (unless otherwise specified).

__all__ = ['UniformWeight', 'ExponentialWeight', 'KeyWeight']

# Cell
import numpy as np

# Cell


class UniformWeight:
    """
    Weight all observations equally
    """
    def __repr__(self):
        return f'UniformWeight()'

    @staticmethod
    def __call__(row):
        return 1.0

# Cell


class ExponentialWeight:
    """
    Weight observations with exponential decay
    """
    def __init__(self, epsilon, key):
        self.epsilon = epsilon
        self.key = key

    def __repr__(self):
        return f'ExponentialWeight(epsilon={self.epsilon}, key={self.key})'

    def __call__(self, row):
        return np.exp(self.epsilon*self.key(row))

# Cell


class KeyWeight:
    """
    Weight observations with an arbitrary key function
    """
    def __init__(self, key):
        self.key = key

    def __repr__(self):
        return f'KeyWeight(key={self.key})'

    def __call__(self, row):
        return self.key(row)