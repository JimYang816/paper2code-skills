"""Tiny frequency-domain channel implementation used only in disposable tests."""

import cmath
import math


def transform(values, inverse=False):
    size = len(values)
    sign = 1 if inverse else -1
    scale = size if inverse else 1
    return [sum(value * cmath.exp(sign * 2j * math.pi * k * n / size)
                for n, value in enumerate(values)) / scale for k in range(size)]


def channel(samples, gain=1):
    # Dimensionless taps [1, 0.5], samples and outputs in volts.
    spectrum = transform(samples)
    response = transform([1, 0.5] + [0] * (len(samples) - 2))
    return [gain * value.real for value in
            transform([x * h for x, h in zip(spectrum, response)], inverse=True)]
