# ruff: noqa
"""Cobertura real do procedimento em processos conhecidos (só simulação)."""

import numpy as np

from case_mr_health import algoritmos
from case_mr_health.intervalos import (
    ConfigIntervalos,
    calibrar,
    contar,
    normalizar,
)

CONFIG = ConfigIntervalos((0.80, 0.95))
R = 4000


class Zero:
    def ajustar(self, y):
        return self

    @staticmethod
    def prever(h):
        return np.zeros(h)


GER = {
    'normal(20,4)': lambda rng, n: rng.normal(20, 4, n),
    'poisson(1.5)': lambda rng, n: rng.poisson(1.5, n).astype(float),
    'poisson(10)': lambda rng, n: rng.poisson(10, n).astype(float),
    'passeio': lambda rng, n: 50 + np.cumsum(rng.normal(0, 1, n)),
}
CLASSES = {'media': algoritmos.MediaHistorica, 'naive': algoritmos.Naive}


def rodar(nome_g, nome_c, n, h):
    rng = np.random.default_rng(20261030)
    g = GER[nome_g]
    cl = CLASSES[nome_c]
    dentro = {0.80: np.zeros(h), 0.95: np.zeros(h)}
    for _ in range(R):
        y = g(rng, n + h)
        tr, fu = y[:n], y[n:]
        c = calibrar(cl, tr, h, CONFIG)
        p = cl().ajustar(tr).prever(h)
        lim = normalizar(p, c.limites(Zero(), p, h))
        for nivel in dentro:
            for j in range(h):
                dentro[nivel][j] += contar(
                    fu[j : j + 1],
                    lim[nivel][0][j : j + 1],
                    lim[nivel][1][j : j + 1],
                ).k
    res = {k: v / R for k, v in dentro.items()}
    print(
        f'{nome_g:14s} {nome_c:6s} n={n:3d} h={h:2d} {c.metodo:17s} '
        f'80%: {res[0.80].mean():.3f} (passo 1 {res[0.80][0]:.3f}, '
        f'último {res[0.80][-1]:.3f})  95%: {res[0.95].mean():.3f} '
        f'(passo 1 {res[0.95][0]:.3f}, último {res[0.95][-1]:.3f})'
    )


for g, c, n, h in [
    ('normal(20,4)', 'media', 42, 7),
    ('poisson(1.5)', 'media', 42, 7),
    ('poisson(1.5)', 'naive', 42, 7),
    ('poisson(1.5)', 'media', 76, 14),
    ('poisson(10)', 'media', 6, 1),
    ('poisson(10)', 'naive', 6, 1),
    ('poisson(10)', 'media', 9, 1),
    ('poisson(10)', 'naive', 9, 1),
    ('poisson(10)', 'media', 10, 2),
    ('passeio', 'naive', 76, 14),
    ('passeio', 'media', 76, 14),
]:
    rodar(g, c, n, h)
