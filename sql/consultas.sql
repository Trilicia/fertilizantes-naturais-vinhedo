-- ============================================================
-- Perguntas de negócio: vale a pena aplicar silício ou cálcio no vinhedo?
-- Banco: data/processed/vinhedo.db (SQLite)
-- ============================================================

-- View de apoio: cada medição ao lado do controle do mesmo sal, safra e etapa
DROP VIEW IF EXISTS vw_vs_controle;
CREATE VIEW vw_vs_controle AS
SELECT t.sal, t.nivel, t.rotulo, t.dose_g_l, m.safra, m.etapa,
       v.codigo, v.nome, v.grupo, v.unidade,
       m.media, m.dp, m.letra_tukey, m.flag_qualidade,
       c.media AS media_controle, c.letra_tukey AS letra_controle,
       ROUND(100.0 * (m.media - c.media) / c.media, 1) AS variacao_pct,
       CASE WHEN m.letra_tukey IS NOT NULL AND c.letra_tukey IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM (SELECT substr(m.letra_tukey,1,1) l UNION SELECT substr(m.letra_tukey,2,1) UNION SELECT substr(m.letra_tukey,3,1)) x
                             WHERE x.l <> '' AND instr(c.letra_tukey, x.l) > 0)
            THEN 1 ELSE 0 END AS difere_do_controle
FROM fato_medicao m
JOIN dim_tratamento t ON t.tratamento_id = m.tratamento_id
JOIN dim_variavel v   ON v.variavel_id = m.variavel_id
JOIN dim_tratamento tc ON tc.sal = t.sal AND tc.nivel = 'controle'
JOIN fato_medicao c   ON c.tratamento_id = tc.tratamento_id AND c.safra = m.safra
                     AND c.etapa = m.etapa AND c.variavel_id = m.variavel_id
WHERE t.nivel <> 'controle';

-- Q1. Quanto cada tratamento aumentou a produtividade em relação ao controle, em cada safra?
SELECT rotulo, safra, media AS t_ha, media_controle AS t_ha_controle, variacao_pct, difere_do_controle
FROM vw_vs_controle
WHERE codigo = 'produtividade_t_ha'
ORDER BY sal, dose_g_l, safra;

-- Q2. Quais tratamentos superaram o controle nas DUAS safras, com diferença estatística?
SELECT rotulo,
       SUM(variacao_pct > 0 AND difere_do_controle = 1) AS safras_com_ganho_significativo,
       ROUND(AVG(variacao_pct), 1) AS ganho_medio_pct
FROM vw_vs_controle
WHERE codigo = 'produtividade_t_ha'
GROUP BY rotulo
ORDER BY safras_com_ganho_significativo DESC, ganho_medio_pct DESC;

-- Q3. Trade-off: ganho de produtividade x açúcar no mosto x álcool no vinho
SELECT p.rotulo, p.safra,
       p.variacao_pct AS produtividade_pct,
       s.variacao_pct AS sst_mosto_pct,
       a.variacao_pct AS alcool_vinho_pct
FROM vw_vs_controle p
JOIN vw_vs_controle s ON s.rotulo = p.rotulo AND s.safra = p.safra AND s.codigo = 'SST' AND s.etapa = 'mosto'
JOIN vw_vs_controle a ON a.rotulo = p.rotulo AND a.safra = p.safra AND a.codigo = 'Teor alcoólico' AND a.etapa = 'vinho'
WHERE p.codigo = 'produtividade_t_ha'
ORDER BY p.safra, p.variacao_pct DESC;

-- Q4. Qualidade funcional do vinho: polifenóis totais, antioxidantes e resveratrol vs controle
SELECT rotulo, safra,
       MAX(CASE WHEN codigo = 'FC' THEN variacao_pct END) AS polifenois_pct,
       MAX(CASE WHEN codigo = 'ABTS' THEN variacao_pct END) AS antioxidante_pct,
       MAX(CASE WHEN codigo = 'trans-resveratrol' THEN variacao_pct END) AS resveratrol_pct
FROM vw_vs_controle
WHERE etapa = 'vinho'
GROUP BY rotulo, safra
ORDER BY safra, polifenois_pct DESC;

-- Q5. Em quantas variáveis fenólicas do vinho cada tratamento ficou acima do controle (com diferença estatística)?
SELECT rotulo, safra,
       SUM(variacao_pct > 0 AND difere_do_controle = 1) AS acima_do_controle,
       SUM(variacao_pct < 0 AND difere_do_controle = 1) AS abaixo_do_controle,
       COUNT(*) AS variaveis_comparadas
FROM vw_vs_controle
WHERE etapa = 'vinho' AND grupo NOT IN ('Físico-químico','Ácidos orgânicos','Produtividade')
  AND media IS NOT NULL AND media_controle IS NOT NULL AND flag_qualidade = ''
GROUP BY rotulo, safra
ORDER BY safra, acima_do_controle DESC;

-- Q6. Qualidade dos dados: o que foi encontrado na fonte e como foi tratado
SELECT tema, problema, decisao FROM auditoria_qualidade;

SELECT v.nome, m.etapa, m.safra, COUNT(*) AS medicoes_marcadas
FROM fato_medicao m JOIN dim_variavel v ON v.variavel_id = m.variavel_id
WHERE m.flag_qualidade <> ''
GROUP BY v.nome, m.etapa, m.safra;
