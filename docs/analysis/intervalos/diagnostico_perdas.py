# ruff: noqa
"""Onde estão as perdas de cobertura: abaixo do inferior ou acima do superior."""

import numpy as np

from case_mr_health.backtest import rodar_backtest
from case_mr_health.candidatos import candidatos
from case_mr_health.config import Settings
from case_mr_health.intervalos import ConfigIntervalos
from case_mr_health.treino import _particao, carregar_serie

cfg = Settings()
conf = ConfigIntervalos((0.80, 0.95), 70)
for sku in ('item A', 'item B', 'item C', 'item D'):
    gran = 'diaria'
    s = carregar_serie(cfg, sku, gran)
    p = _particao(cfg, sku, gran)
    y = s.to_numpy()
    print(sku, 'zeros', round(float((y == 0).mean()), 3))
    for c in candidatos(sku, gran):
        if c.algoritmo not in ('naive', 'media_historica', 'naive_sazonal'):
            continue
        if not c.entra:
            continue
        r = rodar_backtest(s, p, c.algoritmo, c.combinacoes()[0], 1, conf)
        for nv in (0.80, 0.95):
            ab, ac, zero_ab, inf_pos = 0, 0, 0, 0
            for f in r.folds:
                o = np.array(f.observado)
                i, u = f.intervalos.empirico[nv]
                ab += int((o < i).sum())
                ac += int((o > u).sum())
                zero_ab += int(((o == 0) & (o < i)).sum())
                inf_pos += int((i > 0).sum())
            n = sum(len(f.observado) for f in r.folds)
            print(
                f'  {c.algoritmo:16s} {nv}: abaixo {ab:2d} (zeros {zero_ab:2d})'
                f' acima {ac:2d} de {n}; dias com inferior>0: {inf_pos}'
            )
