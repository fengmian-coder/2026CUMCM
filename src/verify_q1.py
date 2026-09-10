from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]

try:
    import scipy  # noqa: F401
except ModuleNotFoundError:
    # Local fallback used by this workspace; a normal virtual environment may
    # simply install scipy and will not use this directory.
    sys.path.insert(0, str(PROJECT / "tmp" / "pydeps"))

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

from data_loader import DT_HOURS, read_attachment1


T = 144
ETA_C = 0.9
ETA_D = 0.9
E_MIN = 1200.0
E_MAX = 10800.0
E_INITIAL = 6000.0
Q_MAX = 5000.0 * DT_HOURS


def read_data():
    data = read_attachment1()
    return data.price_yuan_per_kwh, data.load_kwh, data.pv_kwh


def solve():
    price, load, pv = read_data()

    # Variable blocks: x, charge, discharge, curtailment, E[0:T+1], z_charge, z_discharge
    ix = np.arange(0, T)
    ic = np.arange(T, 2 * T)
    idis = np.arange(2 * T, 3 * T)
    iw = np.arange(3 * T, 4 * T)
    ie = np.arange(4 * T, 5 * T + 1)
    izc = np.arange(5 * T + 1, 6 * T + 1)
    izd = np.arange(6 * T + 1, 7 * T + 1)
    n = 7 * T + 1

    objective = np.zeros(n)
    objective[ix] = price

    lower = np.zeros(n)
    upper = np.full(n, np.inf)
    upper[ic] = Q_MAX
    upper[idis] = Q_MAX
    upper[iw] = pv
    lower[ie] = E_MIN
    upper[ie] = E_MAX
    upper[izc] = 1
    upper[izd] = 1

    integrality = np.zeros(n, dtype=int)
    integrality[izc] = 1
    integrality[izd] = 1

    # Equalities: bus balance, storage transition, initial/final energy.
    aeq = lil_matrix((2 * T + 2, n))
    beq = np.zeros(2 * T + 2)
    for t in range(T):
        aeq[t, ix[t]] = 1
        aeq[t, ic[t]] = -1
        aeq[t, idis[t]] = 1
        aeq[t, iw[t]] = -1
        beq[t] = load[t] - pv[t]

        row = T + t
        aeq[row, ie[t + 1]] = 1
        aeq[row, ie[t]] = -1
        aeq[row, ic[t]] = -ETA_C
        aeq[row, idis[t]] = 1 / ETA_D

    aeq[2 * T, ie[0]] = 1
    beq[2 * T] = E_INITIAL
    aeq[2 * T + 1, ie[T]] = 1
    beq[2 * T + 1] = E_INITIAL

    # Inequalities: charge/discharge mode bounds and mutual exclusion.
    aub = lil_matrix((3 * T, n))
    bub = np.zeros(3 * T)
    for t in range(T):
        aub[t, ic[t]] = 1
        aub[t, izc[t]] = -Q_MAX
        aub[T + t, idis[t]] = 1
        aub[T + t, izd[t]] = -Q_MAX
        aub[2 * T + t, izc[t]] = 1
        aub[2 * T + t, izd[t]] = 1
        bub[2 * T + t] = 1

    constraints = [
        LinearConstraint(aeq.tocsr(), beq, beq),
        LinearConstraint(aub.tocsr(), -np.inf, bub),
    ]
    result = milp(
        c=objective,
        integrality=integrality,
        bounds=Bounds(lower, upper),
        constraints=constraints,
        options={"time_limit": 120, "mip_rel_gap": 1e-9},
    )
    if not result.success:
        raise RuntimeError(result.message)

    v = result.x
    x, charge, discharge, curtail = v[ix], v[ic], v[idis], v[iw]
    energy = v[ie]
    balance_error = x + pv + discharge - load - charge - curtail
    state_error = energy[1:] - energy[:-1] - ETA_C * charge + discharge / ETA_D

    no_storage_purchase = np.maximum(load - pv, 0)
    summary = {
        "optimal_cost": float(price @ x),
        "optimal_purchase": float(x.sum()),
        "no_storage_cost": float(price @ no_storage_purchase),
        "no_storage_purchase": float(no_storage_purchase.sum()),
        "saving_vs_no_storage": float(price @ no_storage_purchase - price @ x),
        "saving_rate_vs_no_storage": float(1 - (price @ x) / (price @ no_storage_purchase)),
        "total_charge": float(charge.sum()),
        "total_discharge": float(discharge.sum()),
        "total_curtailment": float(curtail.sum()),
        "energy_min": float(energy.min()),
        "energy_max": float(energy.max()),
        "energy_initial": float(energy[0]),
        "energy_final": float(energy[-1]),
        "max_balance_error": float(np.abs(balance_error).max()),
        "max_state_error": float(np.abs(state_error).max()),
        "simultaneous_slots": int(np.sum((charge > 1e-6) & (discharge > 1e-6))),
    }
    return summary


if __name__ == "__main__":
    for key, value in solve().items():
        print(f"{key}: {value}")
