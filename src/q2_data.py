"""Strict data preparation for Question 2.

Source workbooks are read only.  Power samples are interpreted by left-endpoint
zero-order hold.  Natural calendar days are reconstructed as documented in the
revised modelling scheme: the preceding row's 24:00 sample supplies the next
day's 00:00 value; only 2025-01-01 uses nearest-neighbour boundary extension.
No source value is rounded.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from data_loader import DT_HOURS, MATERIALS, STEPS_PER_DAY, read_attachment1, read_attachment2


@dataclass(frozen=True)
class Q2Data:
    dates: tuple[date, ...]
    price_yuan_per_kwh: np.ndarray
    load_kw: np.ndarray
    pv_kw: np.ndarray
    source_load_kw: np.ndarray
    source_pv_kw: np.ndarray

    @property
    def load_kwh(self) -> np.ndarray:
        return self.load_kw * DT_HOURS

    @property
    def pv_kwh(self) -> np.ndarray:
        return self.pv_kw * DT_HOURS


def _natural_day_matrix(source: np.ndarray) -> np.ndarray:
    if source.shape != (365, STEPS_PER_DAY):
        raise ValueError(f"Expected a 365x144 matrix, got {source.shape}")
    natural = np.empty_like(source)
    # The sole missing predecessor is 2025-01-01 00:00.  Use the revised
    # scheme's nearest-neighbour boundary extension from 00:10.
    natural[0, 0] = source[0, 0]
    natural[0, 1:] = source[0, :-1]
    natural[1:, 0] = source[:-1, -1]
    natural[1:, 1:] = source[1:, :-1]
    return natural


def load_q2_data() -> Q2Data:
    dates, source_load, source_pv = read_attachment2()
    q1 = read_attachment1()
    # read_attachment1() rotates Q1 values for its periodic natural-day solve;
    # that is exactly the required 00:00,...,23:50 price order here.
    price = np.asarray(q1.price_yuan_per_kwh, dtype=float).copy()
    load = _natural_day_matrix(np.asarray(source_load, dtype=float))
    pv = _natural_day_matrix(np.asarray(source_pv, dtype=float))
    if dates != tuple(date(2025, 1, 1) + timedelta(days=i) for i in range(365)):
        raise ValueError("Attachment 2 dates are not the complete 2025 calendar")
    for name, values in (("price", price), ("load", load), ("PV", pv)):
        if not np.isfinite(values).all() or np.any(values < 0):
            raise ValueError(f"{name} contains invalid values")
    return Q2Data(
        dates=dates,
        price_yuan_per_kwh=price,
        load_kw=load,
        pv_kw=pv,
        source_load_kw=np.asarray(source_load, dtype=float),
        source_pv_kw=np.asarray(source_pv, dtype=float),
    )


def natural_interval_labels() -> tuple[str, ...]:
    def clock(minutes: int) -> str:
        if minutes == 1440:
            return "24:00"
        return f"{minutes // 60:02d}:{minutes % 60:02d}"
    return tuple(f"{clock(t * 10)}-{clock((t + 1) * 10)}" for t in range(144))


if __name__ == "__main__":
    d = load_q2_data()
    print(d.dates[0], d.dates[-1], d.load_kw.shape, d.pv_kw.shape)
    print("2025-01-01 00:00 boundary values:", d.load_kw[0, 0], d.pv_kw[0, 0])
    print("2025-01-02 00:00 predecessor values:", d.load_kw[1, 0], d.pv_kw[1, 0])
