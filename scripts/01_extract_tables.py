"""Extrai as Tabelas 1 a 4 do Capítulo 4 da tese (texto do PDF, modo layout) para CSV em formato longo."""
import re, sys, csv
from pathlib import Path

SRC = Path(sys.argv[1]); OUT = Path(sys.argv[2])
lines = SRC.read_text(encoding="utf-8").splitlines()

COLS = [("Si","controle",0),("Si","baixa",4),("Si","media",8),("Si","alta",12),
        ("Ca","controle",0),("Ca","baixa",5),("Ca","media",10),("Ca","alta",15)]
TOKEN = re.compile(r"\b(nd|Nd)\b|(\d+[.,]\d+)\s*([a-d]{0,3})\s*(?:±\s*|\s+)(\d+[.,]\d+)\s*([a-d]{0,3})|(\d+[.,]\d+)")
LETTERS_ONLY = re.compile(r"^\s*([a-d]{1,3}\s+)*[a-d]{1,3}\s*$")
num = lambda s: float(s.replace(",", "."))

def parse_values(rest):
    vals = []
    for m in TOKEN.finditer(rest):
        if m.group(1): vals.append((None, None, ""))
        elif m.group(2): vals.append((num(m.group(2)), num(m.group(4)), m.group(3) or m.group(5)))
        else: vals.append((num(m.group(6)), None, ""))
    return vals

def find(text, start=0):
    for i in range(start, len(lines)):
        if text in lines[i]: return i
    raise ValueError(text)

def parse_block(start, end, labels, sections, table):
    rows, section, prev = [], None, ""
    for i in range(start, end):
        ln = lines[i]; s = ln.strip()
        for key, (stage, safra) in sections.items():
            if s.startswith(key): section = (stage, safra)
        lab = next((l for l in labels if s.startswith(l + " ") or s == l), None)
        if lab and section:
            vals = parse_values(s[len(lab):])
            if len(vals) == 8:
                missing = [k for k, v in enumerate(vals) if v[0] is not None and not v[2]]
                if missing and LETTERS_ONLY.match(prev):
                    lets = prev.split()
                    for k, l in zip(missing, lets): vals[k] = (vals[k][0], vals[k][1], l)
                for (sal, nivel, dose), (m, sd, let) in zip(COLS, vals):
                    rows.append(dict(tabela=table, etapa=section[0], safra=section[1], sal=sal, nivel=nivel,
                                     dose_g_l=dose, variavel=lab, media=m, dp=sd, letra_tukey=let,
                                     nao_detectado=int(m is None), linha_pdf=i + 1))
            else:
                print(f"[aviso] {table} linha {i+1} '{lab}': {len(vals)} valores", file=sys.stderr)
        if s: prev = ln
    return rows

T2 = ["SST","Acidez total","pH","Tartárico","Málico","Cítrico","Lático","Succínico","Acético","Teor alcoólico","Acidez titulável","SO2 total"]
T34 = ["Gálico","Protocateico","Vanílico","Siríngico","Elágico","trans-caftárico","Cafeico","p-cumárico","Ferúlico",
       "(+)-Catequina","(-)-Epicatequina","Miricetina","Quercetina","Campferol","Tirosol","trans-resveratrol","FC","FT","o-D","IE","ABTS"]

a = find("10Tabela 2."); b = find("11Tabela 3."); c = find("12Tabela 4."); d = find("Os resultados são expressos", c + 60)
rows = []
rows += parse_block(a, b, T2, {"Mosto (Safra 2017)":("mosto",2017),"Vinho (Safra 2017)":("vinho",2017),
                               "Mosto (Safra 2018)":("mosto",2018),"Vinho (Safra 2018)":("vinho",2018)}, "T2")
rows += parse_block(b, c, T34, {"Mosto(Safra 2017)":("mosto",2017),"Vinho (Safra 2017)":("vinho",2017)}, "T3")
rows += parse_block(c, d + 1, T34, {"Mostos":("mosto",2018),"Vinhos":("vinho",2018)}, "T4")

# Tabela 1 (produtividade): o texto do PDF quebra rótulos e valores em várias linhas,
# então os valores foram transcritos manualmente da tese (p. 119-120) e conferidos linha a linha.
T1 = {
 2017: {"producao_kg_planta": "1.43±0.04a 2.65±0.66b 1.80±0.11a 1.57±0.18a 2.43±0.75a 3.32±0.00b 2.79±0.48a 3.76±0.31c",
        "produtividade_t_ha": "2.99±0.45a 5.44±1.09c 3.99±0.24b 3.49±0.41ab 5.28±1.64a 7.37±0.11b 5.81±1.16a 8.23±0.65c",
        "cachos_por_planta":  "21.86±2.98a 34.05±5.98b 23.81±2.77a 23.16±1.47a 31.66±4.71a 35.80±0.67a 38.38±5.99a 44.53±6.81ab",
        "peso_cacho_g":       "69.70±17.00a 85.30±10.49a 76.20±5.88a 73.80±15.43a 78.00±8.92a 91.60±3.76a 91.40±23.75a 93.70±15.33a",
        "firmeza_N":          "3.81±0.36a 4.49±0.40b 4.04±0.42a 3.98±0.40a 3.81±0.36ab 3.99±0.46ab 3.71±0.36a 4.06±0.46b"},
 2018: {"producao_kg_planta": "0.24±0.10a 0.55±0.06b 0.27±0.06a 0.71±0.20b 0.12±0.03a 0.29±0.01c 0.33±0.01d 0.17±0.01b",
        "produtividade_t_ha": "0.53±0.26a 1.22±0.13b 0.60±0.13a 1.36±0.29b 0.28±0.07a 0.64±0.02c 0.73±0.03d 0.38±0.02b",
        "cachos_por_planta":  "4.01±0.92a 6.14±0.96b 5.09±0.88ab 18.02±0.53c 1.03±0.81a 4.01±0.33b 6.00±3.15c 12.11±3.36d",
        "peso_cacho_g":       "73.81±6.11a 116.29±28.03b 96.72±21.93b 97.33±9.69b 69.82±9.55a 74.66±14.23a 82.94±13.06b 76.39±4.51a"}}
for safra, d1 in T1.items():
    for var, txt in d1.items():
        vals = parse_values(txt); assert len(vals) == 8, (safra, var)
        for (sal, nivel, dose), (m, sd, let) in zip(COLS, vals):
            rows.append(dict(tabela="T1", etapa="vinhedo", safra=safra, sal=sal, nivel=nivel, dose_g_l=dose, variavel=var,
                             media=m, dp=sd, letra_tukey=let, nao_detectado=0, linha_pdf=""))

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(f"{len(rows)} medições gravadas em {OUT}")
