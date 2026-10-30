# ruff: noqa
"""Cobertura por série no MLflow do worktree e erro por passo (só dev)."""

import numpy as np
import mlflow

from case_mr_health import algoritmos, intervalos
from case_mr_health.config import Settings
from case_mr_health.treino import carregar_serie, horizonte_maximo

cfg = Settings()
mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
for gran in ('diaria', 'semanal'):
    df = mlflow.search_runs(
        experiment_names=[f'demanda-{gran}'],
        filter_string="params.seed = '20261030'",
    )
    df = df.sort_values(['tags.sku', 'tags.algoritmo'])
    for _, r in df.iterrows():
        m = lambda k: r.get(f'metrics.{k}', float('nan'))  # noqa: E731
        n = int(m('cobertura_n_pontos'))
        print(
            f'{r["tags.sku"]} {gran:7s} {r["tags.algoritmo"]:15s} '
            f'n={n:2d} {r["tags.intervalo_metodo"]:16s}'
            f' m={r["params.intervalo.n_erros"]:>3s} '
            f'o={r["params.intervalo.n_origens"]:>2s} '
            f'f={r["params.intervalo.n_falhas"]} '
            f'c80={m("cobertura_80"):.3f} k={round(m("cobertura_80") * n):2d}'
            f' [{m("cobertura_80_ic_inf"):.3f},{m("cobertura_80_ic_sup"):.3f}]'
            f' amp80={m("amplitude_80"):6.2f} '
            f'c95={m("cobertura_95"):.3f} k={round(m("cobertura_95") * n):2d}'
            f' [{m("cobertura_95_ic_inf"):.3f},{m("cobertura_95_ic_sup"):.3f}]'
            f' amp95={m("amplitude_95"):6.2f}'
        )
        if r['tags.sku'] == 'item C' and gran == 'semanal':
            print(
                '   sens sem atípico: 80',
                m('sens_sem_periodo_atipico_cobertura_80'),
                '95',
                m('sens_sem_periodo_atipico_cobertura_95'),
            )
        hist = mlflow.MlflowClient().get_metric_history(
            r['run_id'], 'cobertura_95_fold'
        )
        h80 = mlflow.MlflowClient().get_metric_history(
            r['run_id'], 'cobertura_80_fold'
        )
        print(
            '   por fold 80:',
            [round(x.value, 2) for x in sorted(h80, key=lambda a: a.step)],
            '95:',
            [round(x.value, 2) for x in sorted(hist, key=lambda a: a.step)],
        )

print('--- |erro| médio por passo, modelo final, só desenvolvimento')
for sku in ('item A', 'item B', 'item C', 'item D'):
    for gran in ('diaria', 'semanal'):
        y = carregar_serie(cfg, sku, gran).to_numpy(dtype=float)
        h = horizonte_maximo(cfg, gran)
        for nome, cl in (
            ('naive', algoritmos.Naive),
            ('media', algoritmos.MediaHistorica),
        ):
            por, _ = intervalos._erros_por_origem(cl, y, h, 70)
            e = np.abs(np.vstack(por)).mean(axis=0)
            corte = h // 2
            print(
                f'{sku} {gran:7s} {nome:6s} passos 1..{corte}: '
                f'{e[:corte].mean():.3f}  passos {corte + 1}..{h}: '
                f'{e[corte:].mean():.3f}'
            )
