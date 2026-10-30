import tomllib
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from loguru import logger

from case_mr_health.api.rotas.changelog import obter_settings, router
from case_mr_health.api.schemas.changelog import TipoMudanca
from case_mr_health.config import Settings


def _link(issue: int) -> str:
    return f'[#{issue}](issues/{issue}.md)'


def _sufixo(issues: list[int]) -> str:
    if not issues:
        return ''
    return f' ({", ".join(_link(issue) for issue in issues)})'


def _renderizar(versoes: list[dict]) -> str:
    """Escreve as versões esperadas no formato do towncrier."""
    linhas = []
    for versao in versoes:
        linhas += [f'# case-mr-health {versao["versao"]} ({versao["data"]})']
        for secao in versao['secoes']:
            linhas += ['', f'## {secao["tipo"]}', '']
            linhas += [
                f'- {item["texto"]}{_sufixo(item["issues"])}'
                for item in secao['itens']
            ]
        linhas += ['', '']
    return '\n'.join(linhas)


@pytest.fixture
def versoes_esperadas(faker_br) -> list[dict]:
    """Duas versões cobrindo todos os tipos do towncrier."""
    tipos = [tipo.value for tipo in TipoMudanca]

    def _versao(numero: str, tipos_da_versao: list[str]) -> dict:
        return {
            'versao': numero,
            'data': faker_br.date_object().isoformat(),
            'secoes': [
                {
                    'tipo': tipo,
                    'itens': [
                        {
                            'texto': faker_br.sentence(),
                            'issues': [faker_br.pyint(1, 999)],
                        },
                        {'texto': faker_br.sentence(), 'issues': []},
                    ],
                }
                for tipo in tipos_da_versao
            ],
        }

    return [_versao('1.2.0', tipos[:3]), _versao('1.1.0', tipos[3:])]


@pytest.fixture
def changelog(tmp_path) -> Path:
    return tmp_path / 'CHANGELOG.md'


@pytest.fixture
def cliente(changelog) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[obter_settings] = lambda: Settings(
        changelog_path=changelog
    )
    return TestClient(app)


@pytest.fixture
def avisos():
    mensagens: list[str] = []
    sink = logger.add(mensagens.append, level='WARNING', format='{message}')
    yield mensagens
    logger.remove(sink)


def _versoes(cliente: TestClient) -> list[dict]:
    resposta = cliente.get('/changelog')
    assert resposta.status_code == HTTPStatus.OK
    return resposta.json()['versoes']


def test_extrai_versoes_datas_e_tipos(
    cliente, changelog, versoes_esperadas, avisos
):
    changelog.write_text(_renderizar(versoes_esperadas), encoding='utf-8')

    assert _versoes(cliente) == versoes_esperadas
    assert not avisos


def test_item_com_varios_links(cliente, changelog, faker_br):
    texto = faker_br.sentence()
    changelog.write_text(
        '# case-mr-health 1.0.0 (2026-01-02)\n\n## Adicionado\n\n'
        f'- {texto}{_sufixo([7, 12, 3])}\n',
        encoding='utf-8',
    )

    item = _versoes(cliente)[0]['secoes'][0]['itens'][0]

    assert item == {'texto': texto, 'issues': [7, 12, 3]}


def test_item_de_varias_linhas_vira_um_so(cliente, changelog):
    changelog.write_text(
        '# case-mr-health 1.0.0 (2026-01-02)\n\n## Adicionado\n\n'
        f'- Linha um\n  continua aqui.\n\n  Outro parágrafo.{_sufixo([3])}\n'
        '- Seguinte.\n',
        encoding='utf-8',
    )

    itens = _versoes(cliente)[0]['secoes'][0]['itens']

    assert itens == [
        {'texto': 'Linha um continua aqui. Outro parágrafo.', 'issues': [3]},
        {'texto': 'Seguinte.', 'issues': []},
    ]


def test_link_no_meio_do_texto_conta_e_permanece(cliente, changelog):
    changelog.write_text(
        '# case-mr-health 1.0.0 (2026-01-02)\n\n## Alterado\n\n'
        f'- Refaz {_link(4)} por completo.{_sufixo([5])}\n',
        encoding='utf-8',
    )

    item = _versoes(cliente)[0]['secoes'][0]['itens'][0]

    assert item == {
        'texto': f'Refaz {_link(4)} por completo.',
        'issues': [4, 5],
    }


@pytest.mark.parametrize('conteudo', ['', ' \n\n  \n'])
def test_changelog_vazio(cliente, changelog, avisos, conteudo):
    changelog.write_text(conteudo, encoding='utf-8')

    assert _versoes(cliente) == []
    assert len(avisos) == 1


def test_changelog_ausente(cliente, avisos):
    assert _versoes(cliente) == []
    assert len(avisos) == 1


def test_changelog_ilegivel(cliente, changelog, avisos):
    changelog.write_bytes(b'# case-mr-health 1.0.0 \xff\xfe')

    assert _versoes(cliente) == []
    assert len(avisos) == 1


@pytest.mark.parametrize(
    'lixo',
    [
        '# Sem versão',
        '# case-mr-health 1.0.0',
        '# case-mr-health 1.0.0 (2026-13-45)',
        'Texto solto.',
    ],
)
def test_conteudo_fora_do_formato_nao_contamina_versoes(
    cliente, changelog, avisos, lixo
):
    changelog.write_text(
        f'{lixo}\n\n## Adicionado\n\n- Órfão.\n\n'
        '# case-mr-health 1.0.0 (2026-01-02)\n\n## Interno\n\n- Válido.\n',
        encoding='utf-8',
    )

    assert _versoes(cliente) == [
        {
            'versao': '1.0.0',
            'data': '2026-01-02',
            'secoes': [
                {
                    'tipo': 'Interno',
                    'itens': [{'texto': 'Válido.', 'issues': []}],
                }
            ],
        }
    ]
    assert any(lixo in aviso for aviso in avisos)
    assert any('Órfão' in aviso for aviso in avisos)


def test_secao_desconhecida_e_ignorada_com_seus_itens(
    cliente, changelog, avisos
):
    changelog.write_text(
        '# case-mr-health 1.0.0 (2026-01-02)\n\n'
        '## Adicionado\n\n- Fica.\n\n'
        '## Novidades\n\n- Sai.\n',
        encoding='utf-8',
    )

    secoes = _versoes(cliente)[0]['secoes']

    assert [secao['tipo'] for secao in secoes] == ['Adicionado']
    assert [item['texto'] for item in secoes[0]['itens']] == ['Fica.']
    assert any('Novidades' in aviso for aviso in avisos)
    assert any('Sai.' in aviso for aviso in avisos)


def test_settings_aponta_para_o_changelog_do_projeto(monkeypatch):
    monkeypatch.delenv('CASE_MR_HEALTH_CHANGELOG_PATH', raising=False)

    assert Settings(_env_file=None).changelog_path == Path('CHANGELOG.md')


def test_tipos_acompanham_o_towncrier():
    pyproject = tomllib.loads(Path('pyproject.toml').read_text('utf-8'))
    tipos = pyproject['tool']['towncrier']['type']

    assert [tipo['name'] for tipo in tipos] == [t.value for t in TipoMudanca]


def test_swagger_documenta_a_rota(cliente):
    esquema = cliente.get('/openapi.json').json()
    operacao = esquema['paths']['/changelog']['get']
    resposta = operacao['responses']['200']
    referencia = resposta['content']['application/json']['schema']['$ref']

    assert referencia.endswith('/Changelog')
    assert operacao['summary']
    assert '`versoes` vazia' in operacao['description']
    assert resposta['description']
    assert esquema['components']['schemas']['Changelog']['examples']
