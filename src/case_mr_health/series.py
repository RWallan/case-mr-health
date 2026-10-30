def construir_series(con) -> None:
    """Cria `serie_diaria` e `serie_semanal` a partir da base consolidada.

    O calendário de cada SKU vai da primeira venda até o último dia com
    pedido na rede. Dia sem venda no calendário é zero imputado
    (`imputado = true`). A semana vai de segunda a domingo, rotulada pela
    segunda-feira, e só entra na série semanal se tiver os 7 dias dentro
    do calendário do SKU.
    """
    con.execute(
        'CREATE TABLE serie_diaria AS '
        'WITH calendario AS ('
        ' SELECT s.sku, CAST(d.dia AS DATE) AS data'
        ' FROM (SELECT sku, min(data) AS inicio FROM base_consolidada'
        '       GROUP BY sku) s,'
        ' (SELECT max(data) AS fim FROM pedido) f,'
        ' LATERAL (SELECT unnest(generate_series(s.inicio, f.fim,'
        '                        INTERVAL 1 DAY)) AS dia) d),'
        ' venda AS ('
        ' SELECT sku, data, sum(quantidade) AS quantidade'
        ' FROM base_consolidada GROUP BY sku, data)'
        ' SELECT c.sku, c.data, coalesce(v.quantidade, 0) AS quantidade,'
        ' v.quantidade IS NULL AS imputado'
        ' FROM calendario c LEFT JOIN venda v USING (sku, data)'
        ' ORDER BY c.sku, c.data'
    )
    con.execute(
        'CREATE TABLE serie_semanal AS '
        "SELECT sku, CAST(date_trunc('week', data) AS DATE) AS semana,"
        ' sum(quantidade) AS quantidade'
        " FROM serie_diaria GROUP BY sku, date_trunc('week', data)"
        ' HAVING count(*) = 7 ORDER BY sku, semana'
    )
