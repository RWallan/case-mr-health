# ruff: noqa
"""Exploratório pós-hoc: efeito de um piso zero no limite inferior.

Regra testada: se a fração de zeros do treino >= (1 - nível) / 2, inferior = 0.
Aprovada depois como D-009. Este script reproduz a comparação original:
desliga o piso do código (fração de zeros = 0) e o aplica à parte.
Ver docs/relatorio/fase2/8.md.
"""

import numpy as np

from case_mr_health import algoritmos, intervalos
from case_mr_health.backtest import rodar_backtest
from case_mr_health.candidatos import candidatos
from case_mr_health.config import Settings
from case_mr_health.intervalos import (
    ConfigIntervalos,
    calibrar,
    contar,
    normalizar,
)
from case_mr_health.treino import _particao, carregar_serie

intervalos.fracao_zeros = lambda y: 0.0  # estado anterior à D-009
cfg = Settings()
conf = ConfigIntervalos((0.80, 0.95), 70)
print('--- real (exploratório)')
for sku in ('item A', 'item B', 'item C', 'item D'):
    s = carregar_serie(cfg, sku, 'diaria')
    p = _particao(cfg, sku, 'diaria')
    y = s.to_numpy()
    for c in candidatos(sku, 'diaria'):
        if not c.entra or c.algoritmo not in algoritmos.ALGORITMOS:
            continue
        r = rodar_backtest(s, p, c.algoritmo, c.combinacoes()[0], 1, conf)
        saida = []
        for nv in (0.80, 0.95):
            k, n, kk = 0, 0, 0
            for f in r.folds:
                o = np.array(f.observado)
                i, u = f.intervalos.empirico[nv]
                tr = y[: f.treino_n]
                piso = (tr == 0).mean() >= (1 - nv) / 2
                k += contar(o, i, u).k
                kk += contar(o, np.zeros_like(i) if piso else i, u).k
                n += len(o)
            saida.append(f'{nv}: {k}/{n} -> {kk}/{n}')
        print(sku, c.algoritmo, *saida)

print('--- simulação: zeros 40%, positivo Poisson com nível que sobe 50%')


class Zero:
    def ajustar(self, y):
        return self

    @staticmethod
    def prever(h):
        return np.zeros(h)


rng = np.random.default_rng(20261030)
n, h, R = 42, 7, 3000
res = {0.80: [0, 0], 0.95: [0, 0]}
for _ in range(R):
    t = np.arange(n + h)
    nivel = 3 * (1 + 0.5 * t / (n + h))
    y = rng.poisson(nivel) * (rng.random(n + h) > 0.4)
    y = y.astype(float)
    tr, fu = y[:n], y[n:]
    cl = algoritmos.MediaHistorica
    c = calibrar(cl, tr, h, conf)
    p_ = cl().ajustar(tr).prever(h)
    lim = normalizar(p_, c.limites(Zero(), p_, h))
    for nv, v in res.items():
        i, u = lim[nv]
        piso = (tr == 0).mean() >= (1 - nv) / 2
        v[0] += contar(fu, i, u).k
        v[1] += contar(fu, np.zeros(h) if piso else i, u).k
for nv, v in res.items():
    print(
        nv, 'plano', round(v[0] / (R * h), 3), 'piso', round(v[1] / (R * h), 3)
    )
