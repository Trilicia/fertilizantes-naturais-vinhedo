"""Gera o dashboard (docs/index.html) a partir do banco e dos relatórios. Publicável no GitHub Pages."""
import json, sqlite3, sys
from pathlib import Path
import pandas as pd

DB, REP, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
TEMPLATE = Path(__file__).with_name("dashboard_template.html")
con = sqlite3.connect(DB)

prod = pd.read_sql("""SELECT t.sal, t.nivel, t.dose_g_l AS dose, m.safra, m.media, m.dp, m.letra_tukey AS letra
                      FROM fato_medicao m JOIN dim_tratamento t USING (tratamento_id) JOIN dim_variavel v USING (variavel_id)
                      WHERE v.codigo = 'produtividade_t_ha' ORDER BY t.sal DESC, m.safra, t.dose_g_l""", con)
vs = pd.read_csv(REP / "variacao_vs_controle.csv")
plac = pd.read_csv(REP / "placar_tratamentos.csv")
tuk = pd.read_csv(REP / "tukey_reconstruido.csv")

ITENS = [("produtividade_t_ha","vinhedo","Produtividade","t/ha"),("SST","mosto","Açúcar no mosto","°Brix"),
         ("Teor alcoólico","vinho","Teor alcoólico do vinho","% v/v"),("Acidez titulável","vinho","Acidez titulável do vinho","g/L"),
         ("FC","vinho","Polifenóis totais do vinho","mg/L"),("ABTS","vinho","Capacidade antioxidante do vinho","µmol TEAC/L"),
         ("trans-resveratrol","vinho","Resveratrol do vinho","mg/L"),("trans-caftárico","vinho","Ácido trans-caftárico do vinho","mg/L")]
heat = []
for cod, etapa, nome, un in ITENS:
    for _, r in vs[(vs.codigo == cod) & (vs.etapa == etapa)].iterrows():
        heat.append(dict(item=nome, unidade=un, sal=r.sal, dose=r.dose_g_l, safra=int(r.safra),
                         pct=round(float(r.var_pct), 1), media=float(r.media), ctrl=float(r.ctrl), difere=bool(r.difere)))
pts = []
for _, r in plac.iterrows():
    sal, dose = r.rotulo.split()[0], float(r.rotulo.split()[1])
    pts.append(dict(sal=sal, dose=dose, safra=int(r.safra), prod=r.produtividade_pct, alcool=r.alcool_vinho_pct,
                    sst=r.sst_mosto_pct, polif=r.polifenois_vinho_pct, resv=r.resveratrol_vinho_pct, sig=bool(r.ganho_significativo)))

both = plac[plac.ganho_significativo].groupby("rotulo").size()
si4 = plac[plac.rotulo == "Si 4 g/L"].sort_values("safra").produtividade_pct.round().astype(int).tolist()
kpi = dict(ambas=int((both == 2).sum()), total=int(plac.rotulo.nunique()), si4=si4,
           polif=[int(round(plac.polifenois_vinho_pct.min())), int(round(plac.polifenois_vinho_pct.max()))],
           concord=int(round(100 * (tuk.reproducao_difere == tuk.tese_difere).mean())), citacoes=26)

data = dict(prod=prod.where(prod.notna(), None).to_dict("records"), heat=heat, pts=pts, kpi=kpi)
html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(html, encoding="utf-8")
print("dashboard gerado:", OUT, "| KPIs:", kpi)
