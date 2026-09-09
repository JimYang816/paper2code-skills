"""Independent time-domain calculation; no import from channel implementation."""


def reference(samples):
    return [value + 0.5 * samples[index - 1] for index, value in enumerate(samples)]


def energy_gradient(samples):
    output = reference(samples)
    return [2 * value + output[(index + 1) % len(output)]
            for index, value in enumerate(output)]
