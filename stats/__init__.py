"""The statistics: the authorities for sensitivity.

How many faint signals are found at a given false-alarm rate is a statistical
question. The reference model's bit-identity says nothing about it. This
package holds what does: the analytic result with its committed source, and an
independent floating-point implementation.

Nothing here imports from `model/`. Both read `spec.constants`: shared facts,
not shared code. The `independence` stage of verify/run.sh holds that.

This file is the lead's. The STAT parcel adds modules beside it.
"""
