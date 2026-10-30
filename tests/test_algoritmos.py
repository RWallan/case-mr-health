import numpy as np
import pytest

from case_mr_health import algoritmos


def test_naive_repete_o_ultimo_valor():
    previsao = algoritmos.Naive().ajustar([4, 0, 3]).prever(3)

    assert list(previsao) == [3, 3, 3]


def test_media_historica_usa_toda_a_janela_do_treino():
    previsao = algoritmos.MediaHistorica().ajustar([1, 2, 6]).prever(2)

    assert list(previsao) == [3, 3]


def test_naive_sazonal_repete_o_ciclo_anterior():
    treino = [9, 1, 2, 3, 4, 5, 6, 7]
    previsao = algoritmos.NaiveSazonal(periodo=7).ajustar(treino).prever(9)

    assert list(previsao) == [1, 2, 3, 4, 5, 6, 7, 1, 2]


def test_naive_sazonal_exige_treino_com_um_ciclo():
    with pytest.raises(ValueError, match='menor que o período'):
        algoritmos.NaiveSazonal(periodo=7).ajustar([1, 2, 3])


def test_registrar_permite_plugar_candidato_sem_mudar_o_fluxo(monkeypatch):
    monkeypatch.setattr(algoritmos, 'ALGORITMOS', dict(algoritmos.ALGORITMOS))

    @algoritmos.registrar('zero')
    class Zero:
        def __init__(self, k=0):
            self.k = k

        def ajustar(self, y):
            return self

        def prever(self, horizonte):
            return np.full(horizonte, self.k)

    assert list(algoritmos.criar('zero', {'k': 2}, seed=1).prever(2)) == [2, 2]
    with pytest.raises(ValueError, match='já registrado'):
        algoritmos.registrar('zero')(Zero)


def test_criar_repassa_a_seed_so_a_quem_a_aceita(monkeypatch):
    monkeypatch.setattr(algoritmos, 'ALGORITMOS', dict(algoritmos.ALGORITMOS))

    @algoritmos.registrar('com_seed')
    class ComSeed:
        aceita_seed = True

        def __init__(self, seed):
            self.seed = seed

    seed = 42
    assert algoritmos.criar('com_seed', {}, seed=seed).seed == seed
    naive = algoritmos.criar('naive', {}, seed=seed)
    assert isinstance(naive, algoritmos.Naive)
