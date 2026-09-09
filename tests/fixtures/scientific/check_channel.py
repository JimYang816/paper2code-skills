"""Exercise waveform equivalence, units, shapes, gradient and noise moments."""

import json
import math
import random
import sys

from channel import channel
from references.reference import energy_gradient, reference


def close(actual, expected, tolerance=1e-9):
    assert len(actual) == len(expected), "shape mismatch"
    assert all(math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)
               for a, b in zip(actual, expected)), (actual, expected)


samples = [1, -1, 2, 0]
gain = 1.1 if "--fault" in sys.argv else 1
output = channel(samples, gain)
close(output, reference(samples))
close(channel([1, 0, 0, 0], gain), [1, 0.5, 0, 0])
close(channel([0, 0, 0, 0], gain), [0, 0, 0, 0])
# Scaling volts preserves the same dimensionless channel response.
close(channel([1000 * x for x in samples], gain), [1000 * y for y in output])

epsilon = 1e-5
numeric_gradient = []
for index in range(len(samples)):
    plus, minus = samples.copy(), samples.copy()
    plus[index] += epsilon
    minus[index] -= epsilon
    energy_plus = sum(y * y for y in channel(plus, gain))
    energy_minus = sum(y * y for y in channel(minus, gain))
    numeric_gradient.append((energy_plus - energy_minus) / (2 * epsilon))
close(numeric_gradient, energy_gradient(samples), tolerance=1e-7)

# Independent Gaussian inputs through h=[1, 0.5] have variance 1.25.
rng = random.Random(7)
observations = [channel([rng.gauss(0, 1) for _ in range(4)], gain)[0]
                for _ in range(2000)]
mean = sum(observations) / len(observations)
variance = sum((x - mean) ** 2 for x in observations) / len(observations)
assert abs(mean) < 0.1
assert abs(variance - 1.25) < 0.15

print(json.dumps({"status": "passed", "checks": {
    "invariants": ["INV-0001"], "units": ["UNIT-0001"],
    "shapes": ["SHAPE-0001"], "gradients": ["GRAD-0001"],
}}))
