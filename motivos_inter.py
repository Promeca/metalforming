import polars as pl

# 1. Caminho completo
caminho_entrada = r"C:\Users\santosgu\OneDrive - American Axle & Manufacturing, Inc\Dados JBMC\\m.csv"

# 2. Lendo com latin1 para aceitar cedilha e acentos
df = pl.read_csv(
    caminho_entrada,
    separator=";",
    encoding="latin1",  # <--- MUDANÇA AQUI
    infer_schema_length=10000
)

# 3. Criando a coluna de Turno
df = df.with_columns(
    pl.when((pl.col("as\nexpr_1") >= "05:00") & (pl.col("as\nexpr_1") < "14:00"))
    .then(pl.lit("T1"))
    .when((pl.col("as\nexpr_1") >= "14:00") & (pl.col("as\nexpr_1") < "22:00"))
    .then(pl.lit("T2"))
    .otherwise(pl.lit("T3"))
    .alias("Turno")
)

# 4. Salvando o resultado
caminho_saida = r"M:\\NTA2\\LMD\Evento Lean\\Dados e Documentos Gerais JBMC1\\vscode\\work_sheets\\m.csv"
df.write_csv(caminho_saida, separator=";")

print("Sucesso! O arquivo foi processado ignorando o erro de codificação.")
