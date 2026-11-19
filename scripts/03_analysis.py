"""Análises do experimento: ganho vs controle, consistência entre safras, trade-off produtividade x qualidade,
reprodução da ANOVA/Tukey a partir de média e desvio padrão, PCA do perfil fenólico do vinho e figuras."""
import sqlite3, sys, itertools
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

DB, OUT = Path(sys.argv[1]), Path(sys.argv[2])
FIG = OUT / "figures"; FIG.mkdir(parents=True, exist_ok=True)
con = sqlite3.connect(DB)
d = pd.read_sql("""SELECT t.sal, t.nivel, t.rotulo, t.dose_g_l, m.safra, m.etapa, v.codigo, v.nome, v.grupo, v.unidade,
                          m.media, m.dp, m.n_repeticoes AS n, m.letra_tukey, m.flag_qualidade
                   FROM fato_medicao m JOIN dim_tratamento t USING (tratamento_id) JOIN dim_variavel v USING (variavel_id)""", con)
d = d[d.flag_qualidade.fillna("") == ""]
NIVEIS = ["controle", "baixa", "media", "alta"]

# --- estilo: azul-petróleo (silício) e ocre (cálcio); par validado para daltonismo e contraste ---
SURF, INK, INK2, GRID, NEUTRO = "#ffffff", "#1d2b30", "#5b6669", "#eceae5", "#c9c5bc"
COR = {"Si": "#046b96", "Ca": "#b7752b"}
plt.rcParams.update({"font.family": "Inter", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK, "figure.facecolor": SURF,
                     "axes.facecolor": SURF, "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 200})

# --- 1. ANOVA de um fator e Tukey HSD reconstruídos a partir de média, DP e n ---
def anova_resumo(g):
    m, s, n = g.media.values, g.dp.values, g.n.values
    k, N = len(m), n.sum(); gm = (m * n).sum() / N
    ssb = (n * (m - gm) ** 2).sum(); ssw = ((n - 1) * s ** 2).sum()
    dfb, dfw = k - 1, N - k; msw = ssw / dfw
    F = (ssb / dfb) / msw if msw > 0 else np.inf
    p = stats.f.sf(F, dfb, dfw) if np.isfinite(F) else 0.0
    return F, p, msw, dfw

linhas_anova, linhas_tukey = [], []
for (sal, safra, etapa, cod), g in d.groupby(["sal", "safra", "etapa", "codigo"]):
    g = g.set_index("nivel").reindex(NIVEIS)
    if g.media.isna().any() or g.dp.isna().any(): continue
    F, p, msw, dfw = anova_resumo(g.reset_index())
    linhas_anova.append(dict(sal=sal, safra=safra, etapa=etapa, codigo=cod, F=F, p_valor=p))
    for a, b in itertools.combinations(NIVEIS, 2):
        if msw == 0: continue
        q = abs(g.loc[a, "media"] - g.loc[b, "media"]) / np.sqrt(msw / 3)
        p_t = stats.studentized_range.sf(q, 4, dfw)
        la, lb = str(g.loc[a, "letra_tukey"] or ""), str(g.loc[b, "letra_tukey"] or "")
        tese_difere = (la != "nan" and lb != "nan" and la and lb and not set(la) & set(lb))
        linhas_tukey.append(dict(sal=sal, safra=safra, etapa=etapa, codigo=cod, par=f"{a} x {b}",
                                 p_tukey=p_t, reproducao_difere=p_t < 0.05, tese_difere=bool(tese_difere)))
anova = pd.DataFrame(linhas_anova); tukey = pd.DataFrame(linhas_tukey)
anova.to_csv(OUT / "anova_reconstruida.csv", index=False); tukey.to_csv(OUT / "tukey_reconstruido.csv", index=False)
concord = (tukey.reproducao_difere == tukey.tese_difere).mean()

# --- 2. variação contra o controle do mesmo sal ---
ctrl = d[d.nivel == "controle"][["sal", "safra", "etapa", "codigo", "media", "letra_tukey"]].rename(columns={"media": "ctrl", "letra_tukey": "letra_ctrl"})
vs = d[d.nivel != "controle"].merge(ctrl, on=["sal", "safra", "etapa", "codigo"])
vs["var_pct"] = 100 * (vs.media - vs.ctrl) / vs.ctrl
vs["dif_abs"] = vs.media - vs.ctrl
vs["difere"] = vs.apply(lambda r: bool(r.letra_tukey) and bool(r.letra_ctrl) and isinstance(r.letra_tukey, str)
                        and isinstance(r.letra_ctrl, str) and not set(r.letra_tukey) & set(r.letra_ctrl), axis=1)
vs.to_csv(OUT / "variacao_vs_controle.csv", index=False)

# --- 3. placar por tratamento ---
def pick(cod, etapa, col="var_pct"):
    return vs[(vs.codigo == cod) & (vs.etapa == etapa)].set_index(["rotulo", "safra"])[col]
placar = pd.DataFrame({"produtividade_pct": pick("produtividade_t_ha", "vinhedo"),
                       "produtividade_dif_t_ha": pick("produtividade_t_ha", "vinhedo", "dif_abs"),
                       "ganho_significativo": pick("produtividade_t_ha", "vinhedo", "difere"),
                       "sst_mosto_pct": pick("SST", "mosto"), "alcool_vinho_pct": pick("Teor alcoólico", "vinho"),
                       "polifenois_vinho_pct": pick("FC", "vinho"), "antioxidante_vinho_pct": pick("ABTS", "vinho"),
                       "resveratrol_vinho_pct": pick("trans-resveratrol", "vinho")}).reset_index()
placar.round(1).to_csv(OUT / "placar_tratamentos.csv", index=False)

# --- 4. PCA do perfil fenólico do vinho (médias), por sal ---
fen = d[(d.etapa == "vinho") & (~d.grupo.isin(["Físico-químico", "Ácidos orgânicos", "Produtividade"]))]
pca_res = {}
for sal in ["Si", "Ca"]:
    w = fen[fen.sal == sal].pivot_table(index=["safra", "nivel"], columns="codigo", values="media").fillna(0)
    w = w.loc[:, w.std() > 0]
    Z = StandardScaler().fit_transform(w)
    p = PCA(n_components=2).fit(Z)
    pca_res[sal] = (pd.DataFrame(p.transform(Z), index=w.index, columns=["PC1", "PC2"]), p.explained_variance_ratio_)

# --- Figura 1: produtividade absoluta por tratamento (small multiples) ---
fig, axes = plt.subplots(2, 2, figsize=(10, 6.6))
prod = d[d.codigo == "produtividade_t_ha"]
for i, safra in enumerate([2017, 2018]):
    for j, sal in enumerate(["Si", "Ca"]):
        ax = axes[i, j]; g = prod[(prod.safra == safra) & (prod.sal == sal)].set_index("nivel").reindex(NIVEIS)
        topo = (prod[prod.safra == safra].media + prod[prod.safra == safra].dp).max()
        cores = [NEUTRO] + [COR[sal]] * 3
        bars = ax.bar(range(4), g.media, color=cores, width=0.56, zorder=2)
        ax.errorbar(range(4), g.media, yerr=g.dp, fmt="none", ecolor="#7d878a", elinewidth=1, capsize=2.5, zorder=3)
        for x, (m, s, l) in enumerate(zip(g.media, g.dp, g.letra_tukey)):
            ax.text(x, m + s + topo * 0.03, f"{m:.2f}".replace(".", ",") + f" {l}", ha="center", va="bottom", fontsize=9, color=INK2)
        ax.set_xticks(range(4), [f"{sal} controle"] + [f"{sal} {v:g} g/L" for v in g.dose_g_l[1:]], fontsize=9)
        ax.set_title(f"{'Silício' if sal=='Si' else 'Cálcio'}, safra {safra-1}/{safra}", fontsize=11, loc="left")
        ax.yaxis.grid(True, color=GRID, lw=0.8, zorder=0); ax.set_axisbelow(True)
        ax.set_ylim(0, topo * 1.25)
        if j == 0: ax.set_ylabel("Produtividade estimada (t/ha)")
fig.suptitle("Produtividade do vinhedo por tratamento", x=0.06, y=0.975, ha="left", fontsize=13, color=INK, fontweight="semibold")
fig.text(0.06, 0.895, "Média ± desvio padrão (n = 3 blocos). Letras diferentes indicam diferença pelo teste de Tukey (p ≤ 0,05) dentro do mesmo sal e safra.\n"
         "Atenção: as escalas das safras são diferentes; em 2017/2018 uma geada tardia reduziu o rendimento de todo o vinhedo.", fontsize=8.5, color=INK2)
fig.tight_layout(rect=(0, 0, 1, 0.88)); fig.savefig(FIG / "01_produtividade.png"); plt.close(fig)

# --- Figura 2: trade-off produtividade x teor alcoólico ---
fig, ax = plt.subplots(figsize=(8.6, 5.6))
ax.axhline(0, color="#9aa3a6", lw=0.9, zorder=1); ax.axvline(0, color="#9aa3a6", lw=0.9, zorder=1)
for sal in ["Si", "Ca"]:
    for safra, mk in [(2017, "o"), (2018, "s")]:
        g = placar[(placar.rotulo.str.startswith(sal)) & (placar.safra == safra)]
        ax.scatter(g.produtividade_pct, g.alcool_vinho_pct, s=85, marker=mk, color=COR[sal], edgecolor=SURF, linewidth=2, zorder=3,
                   label=f"{'Silício' if sal=='Si' else 'Cálcio'}, safra {safra-1}/{safra}")
        for _, r in g.iterrows():
            off = (6, -12) if (r.rotulo == "Ca 5 g/L" and safra == 2018) else (6, 4)
            ax.annotate(r.rotulo.replace(" g/L", ""), (r.produtividade_pct, r.alcool_vinho_pct), xytext=off,
                        textcoords="offset points", fontsize=8.5, color=INK2)
ax.set_xlabel("Variação da produtividade vs. controle (%)"); ax.set_ylabel("Variação do teor alcoólico do vinho vs. controle (%)")
ax.yaxis.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True)
ax.legend(frameon=False, fontsize=9, loc="lower right")
fig.suptitle("Produzir mais custa açúcar: o trade-off entre volume e teor alcoólico", x=0.02, y=0.98, ha="left", fontsize=12, fontweight="semibold")
fig.text(0.02, 0.915, "Quase todos os tratamentos aumentam a produtividade e reduzem o álcool do vinho. As exceções são Ca 10 e Ca 15 em 2017/2018.",
        fontsize=8.5, color=INK2, va="bottom")
fig.tight_layout(rect=(0, 0, 1, 0.91)); fig.savefig(FIG / "02_tradeoff_produtividade_alcool.png"); plt.close(fig)

# --- Figura 3: mapa de calor da variação vs controle ---
itens = [("produtividade_t_ha", "vinhedo", "Produtividade"), ("SST", "mosto", "Açúcar no mosto (°Brix)"),
         ("Teor alcoólico", "vinho", "Teor alcoólico do vinho"), ("Acidez titulável", "vinho", "Acidez titulável do vinho"),
         ("FC", "vinho", "Polifenóis totais do vinho"), ("ABTS", "vinho", "Capacidade antioxidante do vinho"),
         ("trans-resveratrol", "vinho", "Resveratrol do vinho"), ("trans-caftárico", "vinho", "Ácido trans-caftárico do vinho")]
ordem = [f"Si {x} g/L" for x in (4, 8, 12)] + [f"Ca {x} g/L" for x in (5, 10, 15)]
cmap = LinearSegmentedColormap.from_list("div", ["#a8462f", "#d9967f", "#f2f0eb", "#7fb0cb", "#046b96"])
fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
for ax, safra in zip(axes, [2017, 2018]):
    M = np.array([[vs[(vs.codigo == c) & (vs.etapa == e) & (vs.safra == safra) & (vs.rotulo == r)].var_pct.squeeze() for r in ordem] for c, e, _ in itens], dtype=float)
    S = np.array([[bool(vs[(vs.codigo == c) & (vs.etapa == e) & (vs.safra == safra) & (vs.rotulo == r)].difere.squeeze()) for r in ordem] for c, e, _ in itens])
    im = ax.imshow(np.clip(M, -60, 60), cmap=cmap, norm=TwoSlopeNorm(0, -60, 60), aspect="auto")
    for i, j in itertools.product(range(M.shape[0]), range(M.shape[1])):
        v = M[i, j]; txt = f"{v:+.0f}%" + ("" if S[i, j] else "*")
        ax.text(j, i, txt, ha="center", va="center", fontsize=8.5, color="#ffffff" if abs(v) > 40 else INK)
    ax.set_xticks(range(len(ordem)), ordem, rotation=0, fontsize=8.5); ax.set_yticks(range(len(itens)), [x[2] for x in itens])
    ax.set_title(f"Safra {safra-1}/{safra}", loc="left", fontsize=11)
    ax.set_xticks(np.arange(-.5, len(ordem)), minor=True); ax.set_yticks(np.arange(-.5, len(itens)), minor=True)
    ax.grid(which="minor", color=SURF, lw=2); ax.tick_params(which="minor", length=0)
    for s in ax.spines.values(): s.set_visible(False)
cax = fig.add_axes([0.885, 0.15, 0.012, 0.6]); cb = fig.colorbar(im, cax=cax); cb.set_label("Variação vs. controle (%)\n(escala limitada a ±60%)", color=INK2, fontsize=8.5); cb.outline.set_visible(False)
fig.suptitle("Efeito de cada tratamento em relação ao controle", x=0.02, ha="left", fontsize=13, fontweight="semibold")
fig.text(0.02, 0.9, "Azul-petróleo = acima do controle; terracota = abaixo. * = sem diferença estatística em relação ao controle (Tukey, p ≤ 0,05).", fontsize=8.5, color=INK2)
fig.subplots_adjust(left=0.2, right=0.86, top=0.82, bottom=0.08, wspace=0.08); fig.savefig(FIG / "03_mapa_variacao.png"); plt.close(fig)

# --- Figura 4: PCA ---
fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
for ax, sal in zip(axes, ["Si", "Ca"]):
    sc, var = pca_res[sal]
    usados = []
    for safra, mk in [(2017, "o"), (2018, "s")]:
        s = sc.xs(safra, level="safra").reindex(NIVEIS)
        ax.scatter(s.PC1, s.PC2, marker=mk, s=70, color=[NEUTRO] + [COR[sal]] * 3, edgecolor=SURF, linewidth=2, zorder=3)
        for nv, r in s.iterrows():
            lab = "controle" if nv == "controle" else f"{d[(d.sal==sal)&(d.nivel==nv)].dose_g_l.iloc[0]:g} g/L"
            perto = any(abs(r.PC1 - x) < 0.8 and abs(r.PC2 - y) < 0.45 for x, y in usados)
            ax.annotate(f"{lab} ({safra})", (r.PC1, r.PC2), xytext=(6, -12) if perto else (6, 4), textcoords="offset points", fontsize=8, color=INK2)
            usados.append((r.PC1, r.PC2))
    ax.axhline(0, color=GRID, lw=1); ax.axvline(0, color=GRID, lw=1)
    ax.set_xlabel(f"PC1 ({var[0]*100:.0f}%)"); ax.set_ylabel(f"PC2 ({var[1]*100:.0f}%)")
    ax.set_title(f"{'Silício' if sal=='Si' else 'Cálcio'}: perfil fenólico do vinho", loc="left", fontsize=11)
fig.suptitle("PCA do perfil fenólico do vinho: a safra separa mais que o tratamento", x=0.01, ha="left", fontsize=12, fontweight="semibold")
fig.text(0.01, 0.01, "Círculos = safra 2016/2017; quadrados = safra 2017/2018; cinza = controle. PCA sobre as médias padronizadas dos compostos fenólicos.",
         fontsize=8.5, color=INK2)
fig.tight_layout(rect=(0, 0.05, 1, 0.95)); fig.savefig(FIG / "04_pca_vinho.png"); plt.close(fig)

# --- resumo ---
print(f"ANOVAs reconstruídas: {len(anova)} | significativas (p<0,05): {(anova.p_valor<0.05).mean():.0%}")
print(f"Comparações de Tukey: {len(tukey)} | concordância com as letras da tese: {concord:.1%}")
print(f"PCA Si: {pca_res['Si'][1].round(3)} | PCA Ca: {pca_res['Ca'][1].round(3)}")
print(placar.round(1).to_string(index=False))
