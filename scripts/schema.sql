-- Modelo estrela: experimento de fertilizantes naturais (silício e cálcio) em Sauvignon Blanc
CREATE TABLE dim_tratamento (
  tratamento_id INTEGER PRIMARY KEY,
  sal TEXT NOT NULL CHECK (sal IN ('Si','Ca')),
  nivel TEXT NOT NULL CHECK (nivel IN ('controle','baixa','media','alta')),
  dose_g_l REAL NOT NULL,
  dose_pct REAL NOT NULL,
  rotulo TEXT NOT NULL,
  fertilizante TEXT NOT NULL,
  UNIQUE (sal, nivel)
);
CREATE TABLE dim_variavel (
  variavel_id INTEGER PRIMARY KEY,
  codigo TEXT NOT NULL UNIQUE,
  nome TEXT NOT NULL,
  grupo TEXT NOT NULL,
  unidade TEXT NOT NULL
);
CREATE TABLE dim_safra (safra INTEGER PRIMARY KEY, ciclo TEXT NOT NULL, observacao TEXT);
CREATE TABLE dim_etapa (etapa TEXT PRIMARY KEY, ordem INTEGER NOT NULL);
CREATE TABLE fato_medicao (
  medicao_id INTEGER PRIMARY KEY AUTOINCREMENT,
  tratamento_id INTEGER NOT NULL REFERENCES dim_tratamento(tratamento_id),
  safra INTEGER NOT NULL REFERENCES dim_safra(safra),
  etapa TEXT NOT NULL REFERENCES dim_etapa(etapa),
  variavel_id INTEGER NOT NULL REFERENCES dim_variavel(variavel_id),
  media REAL,                 -- NULL quando não detectado
  dp REAL,
  n_repeticoes INTEGER NOT NULL,
  letra_tukey TEXT,
  nao_detectado INTEGER NOT NULL CHECK (nao_detectado IN (0,1)),
  fonte_tabela TEXT NOT NULL,
  linha_pdf INTEGER,
  flag_qualidade TEXT,
  UNIQUE (tratamento_id, safra, etapa, variavel_id)
);
CREATE TABLE auditoria_qualidade (tema TEXT, problema TEXT, decisao TEXT);
CREATE INDEX ix_fato_var ON fato_medicao (variavel_id, etapa, safra);
