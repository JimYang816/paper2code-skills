# Independent numerical fixture

These original MIT-licensed, standard-library-only scripts run in disposable
Reproduction Repositories. `channel.py` implements a four-sample circular
two-tap channel using a DFT and inverse DFT. `reference.py` separately computes
the same waveform in the time domain and the analytic squared-energy gradient.
The reference imports no production calculation.

`check_channel.py` checks a known impulse response, zero input, waveform
equivalence, voltage scaling, shape, finite-difference gradients, and the
expected output variance for seeded independent Gaussian inputs. It emits
passing check IDs only after the calculations pass. `--fault` introduces a 10%
gain error into the frequency-domain implementation; the CPU gate must classify
that numerical discrepancy as scientific and route to diagnosis. Existing
fixed-output fixtures remain useful for isolated report-protocol checks.
