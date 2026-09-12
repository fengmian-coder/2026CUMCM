"""Independent 00:10-to-next-00:10 trial; preserves canonical Q2 outputs."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tmp/q2_trial_deps'))
import csv
import json
from dataclasses import replace
from datetime import datetime, timedelta
import numpy as np
from data_loader import read_attachment1
from q2_data import load_q2_data
from q2_forecast import ForecastConfig, _load_base, _date_features, _ridge_predict, _pv_forecast
from q2_optimize import OptimizationConfig, scenarios_for_day, solve_day

OUT = ROOT / 'outputs/q2_shifted_trial'

def forecast(data):
    # Each historical row ends at today's 00:00, so history[:d] is available.
    cfg = ForecastConfig()
    q1 = read_attachment1()
    cold_l, cold_p = np.roll(q1.load_kw, -1), np.roll(q1.pv_kw, -1)
    L, P = data.source_load_kw, data.source_pv_kw
    base = np.empty_like(L)
    lh, ph = np.empty_like(L), np.empty_like(P)
    for d in range(365):
        base[d] = _load_base(L[:d], data.dates, d, cfg, cold_l)
        correction = np.zeros(144)
        if d >= cfg.minimum_regression_days:
            correction = _ridge_predict(
                _date_features(list(data.dates[:d]), cfg.load_fourier_order),
                L[:d] - base[:d],
                _date_features([data.dates[d]], cfg.load_fourier_order)[0], cfg.load_ridge)
        lh[d] = np.maximum(base[d] + correction, 0)
        ph[d] = _pv_forecast(P[:d], data.dates, d, cfg, cold_p)
    return lh, ph

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = load_q2_data()
    lh, ph = forecast(data)
    cfg = OptimizationConfig(cvar_weight=0.05)
    price = np.roll(data.price_yuan_per_kwh, -1)
    solutions = []
    e0 = 6000.0
    for d in range(365):
        sl, sp = scenarios_for_day(d, data.dates, data.source_load_kw,
                                  data.source_pv_kw, lh, ph, cfg)
        s = solve_day(price, e0, sl, sp, cfg)
        shortage = data.source_load_kw[d]/6 + s['charge'] - s['purchase'] - data.source_pv_kw[d]/6 - s['discharge']
        s['emergency'] = np.maximum(shortage, 0)
        s['surplus'] = np.maximum(-shortage, 0)
        solutions.append(s)
        e0 = float(s['energy'][-1])
        if d % 30 == 0 or d == 364:
            print(f"Solved {data.dates[d]}", flush=True)
    arrays = {k: np.asarray([s[k] for s in solutions]) for k in
              ('purchase','charge','discharge','energy','emergency','surplus')}
    np.savez_compressed(OUT/'schedules.npz', **arrays, load_forecast_kw=lh, pv_forecast_kw=ph)
    header = ['decision_date','interval_start','price_yuan_per_kwh','load_forecast_kw','pv_forecast_kw',
              'actual_load_kw','actual_pv_kw','purchase_kwh','charge_kwh','discharge_kwh',
              'emergency_kwh','surplus_kwh','initial_energy_kwh','final_energy_kwh']
    with (OUT/'plan_schedule.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer = csv.writer(f); writer.writerow(header)
        for d in range(365):
            for t in range(144):
                stamp = datetime.combine(data.dates[d], datetime.min.time()) + timedelta(minutes=10*(t+1))
                s = solutions[d]
                writer.writerow([str(data.dates[d]),stamp.isoformat(),price[t],lh[d,t],ph[d,t],
                                 data.source_load_kw[d,t],data.source_pv_kw[d,t],
                                 *[s[k][t] for k in ('purchase','charge','discharge','emergency','surplus','energy')],s['energy'][t+1]])
    def totals(g,b,p):
        return dict(plan_cost_yuan=float(np.sum(g*p)), emergency_cost_yuan=float(np.sum(b*p*5)),
                    total_cost_yuan=float(np.sum((g+5*b)*p)),plan_purchase_kwh=float(g.sum()),
                    emergency_purchase_kwh=float(b.sum()))
    natural = {}
    for k in ('purchase','charge','discharge','emergency','surplus'):
        natural[k] = np.concatenate((arrays[k][30:364,-1,None],arrays[k][31:,:143]),axis=1)
    natural_energy = np.concatenate((arrays['energy'][30:364,143,None],arrays['energy'][31:,:144]),axis=1)
    np.savez_compressed(OUT/'natural_reporting.npz', **natural, energy=natural_energy)
    daily = []
    for i,d in enumerate(range(31,365)):
        item = {'date':str(data.dates[d]),'energy_0000_kwh':float(natural_energy[i,0]),
                'energy_0010_kwh':float(arrays['energy'][d,0]),'energy_2400_kwh':float(natural_energy[i,-1])}
        item.update(totals(natural['purchase'][i],natural['emergency'][i],data.price_yuan_per_kwh))
        item['four_hour_blocks'] = [{'charge_kwh':float(natural['charge'][i,j:j+24].sum()),
                                    'discharge_kwh':float(natural['discharge'][i,j:j+24].sum())} for j in range(0,144,24)]
        daily.append(item)
    (OUT/'natural_daily_summary.json').write_text(json.dumps(daily,ensure_ascii=False,indent=2),encoding='utf-8')
    residual = arrays['energy'][:,1:] - arrays['energy'][:,:-1] - .9*arrays['charge'] + arrays['discharge']/.9
    balance = arrays['purchase']+data.source_pv_kw/6+arrays['discharge']+arrays['emergency']-data.source_load_kw/6-arrays['charge']-arrays['surplus']
    audit = {'state_residual_kwh':float(np.abs(residual).max()),'balance_residual_kwh':float(np.abs(balance).max()),
             'cross_day_residual_kwh':float(np.abs(arrays['energy'][1:,0]-arrays['energy'][:-1,-1]).max()),
             'energy_min':float(arrays['energy'].min()),'energy_max':float(arrays['energy'].max()),
             'max_charge':float(arrays['charge'].max()),'max_discharge':float(arrays['discharge'].max()),
             'simultaneous_slots':int(((arrays['charge']>1e-7)&(arrays['discharge']>1e-7)).sum())}
    assert audit['state_residual_kwh']<1e-7 and audit['balance_residual_kwh']<1e-7
    assert audit['cross_day_residual_kwh']<1e-7 and audit['simultaneous_slots']==0
    assert audit['energy_min']>=1200-1e-7 and audit['energy_max']<=10800+1e-7
    old=json.loads((ROOT/'outputs/q2/q2_summary.json').read_text(encoding='utf-8'))
    nat=totals(natural['purchase'],natural['emergency'],data.price_yuan_per_kwh)
    result={'decision_window':'00:10 to next 00:10; all 144 decisions made at 00:00',
            'initial_boundary':'Jan 1 00:00-00:10 battery idle; energy 6000; no invented actual midnight sample used in forecast',
            'midnight_update':'Previous source row including its final midnight sample enters load lag matching and PV recent energy/shape; no extra ad-hoc correction',
            'natural_reporting_period':['2025-02-01T00:00','2026-01-01T00:00'],
            'plan_reporting_period':['2025-02-01T00:10','2026-01-01T00:10'],
            'natural_totals':nat,'plan_window_totals':totals(arrays['purchase'][31:],arrays['emergency'][31:],price),
            'comparison_same_natural_window':{k:{'old':old[k],'new':nat[k],'difference':nat[k]-old[k]} for k in ('total_cost_yuan','emergency_purchase_kwh')},
            'audit':audit}
    (OUT/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    main()
