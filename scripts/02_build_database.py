"""Cria o banco SQLite (modelo estrela) a partir do CSV extraído e registra a auditoria de qualidade."""
import sqlite3, sys
import pandas as pd
from pathlib import Path

CSV, DB = Path(sys.argv[1]), Path(sys.argv[2])
d = pd.read_csv(CSV)
DB.unlink(missing_ok=True)
con = sqlite3.connect(DB)
con.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))

VAR = {  # variavel: (nome, grupo, unidade)
 "producao_kg_planta": ("Produção por planta","Produtividade","kg/planta"),
 "produtividade_t_ha": ("Produtividade estimada","Produtividade","t/ha"),
 "cachos_por_planta": ("Cachos por planta","Produtividade","cachos/planta"),
 "peso_cacho_g": ("Peso do cacho","Produtividade","g"),
 "firmeza_N": ("Força máxima de compressão","Produtividade","N"),
 "SST": ("Sólidos solúveis totais","Físico-químico","°Brix"),
 "Acidez total": ("Acidez total","Físico-químico","meq/L (provável; ver auditoria)"),
 "pH": ("pH","Físico-químico","-"),
 "Teor alcoólico": ("Teor alcoólico","Físico-químico","% v/v"),
 "Acidez titulável": ("Acidez titulável","Físico-químico","g/L ác. tartárico"),
 "SO2 total": ("SO2 total","Físico-químico","mg/L"),
 **{a: (f"Ácido {a.lower()}","Ácidos orgânicos","g/L") for a in ["Tartárico","Málico","Cítrico","Lático","Succínico","Acético"]},
 **{a: (f"Ácido {a.lower()}","Ácidos hidroxibenzoicos","mg/L") for a in ["Gálico","Protocateico","Vanílico","Siríngico","Elágico"]},
 "trans-caftárico": ("Ácido trans-caftárico","Ácidos hidroxicinâmicos","mg/L"),
 "Cafeico": ("Ácido cafeico","Ácidos hidroxicinâmicos","mg/L"),
 "p-cumárico": ("Ácido p-cumárico","Ácidos hidroxicinâmicos","mg/L"),
 "Ferúlico": ("Ácido ferúlico","Ácidos hidroxicinâmicos","mg/L"),
 "(+)-Catequina": ("(+)-Catequina","Flavanóis","mg/L"),
 "(-)-Epicatequina": ("(-)-Epicatequina","Flavanóis","mg/L"),
 "Miricetina": ("Miricetina","Flavonóis","mg/L"), "Quercetina": ("Quercetina","Flavonóis","mg/L"),
 "Campferol": ("Campferol","Flavonóis","mg/L"),
 "Tirosol": ("Tirosol","Outros fenólicos","mg/L"), "trans-resveratrol": ("trans-Resveratrol","Outros fenólicos","mg/L"),
 "FC": ("Polifenóis totais (Folin-Ciocalteu)","Espectrofotometria","mg/L ác. gálico"),
 "FT": ("Flavanóis totais","Espectrofotometria","mg/L catequina"),
 "o-D": ("o-Difenóis","Espectrofotometria","mg/L catequina"),
 "IE": ("Índice de escurecimento","Espectrofotometria","absorbância"),
 "ABTS": ("Capacidade antioxidante (ABTS)","Espectrofotometria","µmol TEAC/L"),
}
var = pd.DataFrame([(k,*v) for k,v in VAR.items()], columns=["codigo","nome","grupo","unidade"])
var.insert(0,"variavel_id",range(1,len(var)+1)); var.to_sql("dim_variavel", con, if_exists="append", index=False)

trat = d[["sal","nivel","dose_g_l"]].drop_duplicates().reset_index(drop=True)
trat["dose_pct"] = trat.dose_g_l/10
trat["rotulo"] = trat.apply(lambda r: f"{r.sal} controle" if r.nivel=="controle" else f"{r.sal} {r.dose_g_l:g} g/L", axis=1)
trat["fertilizante"] = trat.sal.map({"Si":"Metassilicato de sódio","Ca":"Cloreto de cálcio"})
trat.insert(0,"tratamento_id",range(1,len(trat)+1)); trat.to_sql("dim_tratamento", con, if_exists="append", index=False)

pd.DataFrame({"safra":[2017,2018],"ciclo":["2016/2017","2017/2018"],
              "observacao":["","Geada tardia em outubro reduziu o rendimento (segundo a tese)"]}).to_sql("dim_safra", con, if_exists="append", index=False)
pd.DataFrame({"etapa":["vinhedo","mosto","vinho"],"ordem":[1,2,3]}).to_sql("dim_etapa", con, if_exists="append", index=False)

f = d.merge(trat[["tratamento_id","sal","nivel"]], on=["sal","nivel"]).merge(var[["variavel_id","codigo"]], left_on="variavel", right_on="codigo")
f["n_repeticoes"] = 3
f["flag_qualidade"] = ""
dup = {("T3","mosto",2017,"Gálico"),("T3","mosto",2017,"Cafeico"),("T4","mosto",2018,"Protocateico"),("T4","mosto",2018,"Ferúlico")}
f.loc[f.apply(lambda r: (r.tabela,r.etapa,r.safra,r.variavel) in dup, axis=1),"flag_qualidade"] = "linha_duplicada_na_fonte"
f = f[["tratamento_id","safra","etapa","variavel_id","media","dp","n_repeticoes","letra_tukey","nao_detectado","tabela","linha_pdf","flag_qualidade"]]
f = f.rename(columns={"tabela":"fonte_tabela"})
f.to_sql("fato_medicao", con, if_exists="append", index=False)

audit = [
 ("Doses","Metodologia: Si 4, 8 e 12 g/L e Ca 5, 10 e '1,5 g/L'. Tabelas 1 e 2: Si 0,4%, 0,8% e 1,4%. Tabela 4 e legenda da Figura 2: Si 1,2%. Tabelas 3 e 4: Ca 15.",
  "Padronizado como Si 4/8/12 g/L (0,4/0,8/1,2%) e Ca 5/10/15 g/L (0,5/1,0/1,5%). Confirmado pela autora e pelo artigo publicado (Gomes et al., 2020, J Sci Food Agric)."),
 ("Linhas duplicadas","Tabela 3 (mosto 2017): ácido gálico e ácido cafeico têm os mesmos 8 valores. Tabela 4 (mosto 2018): ácido protocateico e ácido ferúlico também.",
  "Valores mantidos, mas marcados com flag_qualidade = 'linha_duplicada_na_fonte' e excluídos das análises. Provável erro de transcrição: conferir nos dados brutos."),
 ("Controles","Nas Tabelas 2 a 4 os controles de Si e Ca deveriam ser a mesma amostra. Diferem por arredondamento na acidez total e, no vinho 2017, no ácido trans-caftárico (2,64 vs 2,33).",
  "Mantidos como publicados; cada sal é comparado com o seu próprio controle."),
 ("Unidade","A tese indica acidez total em g/L de ácido tartárico, mas os valores (93 a 144) são compatíveis com meq/L.",
  "Unidade registrada como 'meq/L (provável)'. Não afeta as comparações relativas."),
 ("Controles da produtividade","Na Tabela 1 os controles de Si e Ca são parcelas diferentes (ex.: 2017: 2,99 vs 5,28 t/ha).",
  "Ganhos calculados sempre contra o controle da mesma parcela; não se comparam valores absolutos entre Si e Ca."),
 ("Tabela 1","O texto extraído do PDF quebra rótulos e valores em várias linhas.",
  "Valores transcritos manualmente das páginas 119 e 120 e conferidos linha a linha."),
]
pd.DataFrame(audit, columns=["tema","problema","decisao"]).to_sql("auditoria_qualidade", con, if_exists="append", index=False)
con.commit()
for t in ["dim_tratamento","dim_variavel","dim_safra","dim_etapa","fato_medicao","auditoria_qualidade"]:
    print(t, con.execute(f"select count(*) from {t}").fetchone()[0])
