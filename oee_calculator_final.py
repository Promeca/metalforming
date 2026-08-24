import polars as pl
from pathlib import Path

# --- CONFIGURAÇÃO ---
CAMINHO_BASE = Path(r'M:\NTA2\LMD\Evento Lean\Dados e Documentos Gerais JBMC1\vscode\work_sheets')
CAMINHO_ENTRADA = CAMINHO_BASE / 'a.csv'
ARQUIVO_INPUT_HORAS = CAMINHO_BASE / 'horas_planejadas_por_item.csv'
ARQUIVO_SAIDA = CAMINHO_BASE / 'oee_final_consolidado.csv'

def converter_numero_br(col_name):
    """
    USAR APENAS PARA O ARQUIVO DO ERP (que vem como 1.000,00)
    Remove pontos de milhar e troca vírgula por ponto.
    """
    return (
        pl.col(col_name)
        .cast(pl.Utf8)                 
        .str.replace_all(r"\.", "")    # Remove ponto de milhar
        .str.replace(",", ".")         # Troca vírgula por ponto
        .cast(pl.Float64, strict=False)
        .fill_null(0)
    )

def preparar_df(caminho):
    try:
        df = pl.read_csv(caminho, separator=';', encoding='latin1', infer_schema_length=0)
    except:
        df = pl.read_csv(caminho, separator=';', infer_schema_length=0)

    # Limpeza dos nomes das colunas
    df = df.rename({c: c.strip().replace('\r', '').replace('\n', '') for c in df.columns})
    
    mapeamento = {}
    for col in df.columns:
        c_up = col.upper()
        if "BWMANR" in c_up: mapeamento[col] = "Maquina"
        elif "BWTENR" in c_up: mapeamento[col] = "NumerodaPeca"
        elif "AGMAZT" in c_up: mapeamento[col] = "TM"
        # Pega Quantidade Boa (BWRMMG ou qualquer coluna com QTD e BOA)
        elif "BWRMMG" in c_up or ("PRODUZIDA" in c_up and "BOA" in c_up): 
            mapeamento[col] = "QtdeProduzidaBoa"
    
    return df.rename(mapeamento)

def calcular():
    print("\n" + "="*80)
    print("      PASSO 3: RELATÓRIO OEE (CORREÇÃO DE PONTO DECIMAL)")
    print("==================================================================================")
    
    try:
        # 1. CARREGAR
        print("📂 Lendo arquivos...")
        df = preparar_df(CAMINHO_ENTRADA)
        df_in = preparar_df(ARQUIVO_INPUT_HORAS)

        # 2. LIMPEZA DE DADOS
        mapa_turnos = {"Primeiro Turno": "T1", "Segundo Turno": "T2", "Terceiro Turno": "T3", "Administrativo": "ADM"}

        # >>> TRATAMENTO DO ERP (APONTAMENTOS) <<<
        # Aqui usamos o conversor BR porque o SAP/ERP manda 1.200,50
        df = df.with_columns([
            pl.col("Maquina").cast(pl.Utf8).str.strip_chars().str.strip_chars_start("0"),
            pl.col("NumerodaPeca").str.strip_chars(),
            pl.col("Turno").str.strip_chars().replace(mapa_turnos, default=pl.col("Turno")),
            
            converter_numero_br("TM").alias("TM"),
            converter_numero_br("QtdeProduzidaBoa").alias("QtdeProduzidaBoa")
        ])

        # >>> TRATAMENTO DO INPUT DE HORAS (CORREÇÃO AQUI) <<<
        # O arquivo do Passo 2 já vem com ponto (7.4), NÃO podemos usar o conversor BR nele
        df_in = df_in.with_columns([
            pl.col("Maquina").cast(pl.Utf8).str.strip_chars().str.strip_chars_start("0"),
            pl.col("NumerodaPeca").str.strip_chars(),
            pl.col("Turno").str.strip_chars().replace(mapa_turnos, default=pl.col("Turno")),
            
            # AQUI MUDOU: Apenas convertemos para Float direto, pois já está no formato 7.4 ou 7.5
            pl.col("Horas_Disponiveis").cast(pl.Utf8).str.replace(",", ".").cast(pl.Float64, strict=False).fill_null(0)
        ])

        # 3. VERIFICAÇÃO RÁPIDA
        print("🔍 Verificando Horas (Deve ser algo como 7.4, 8.8... e NÃO 74.0):")
        print(df_in.select(["Maquina", "Horas_Disponiveis"]).head(3))

        # 4. CÁLCULOS
        df = df.with_columns(
            pl.when(pl.col("TM") > 0).then(6000 / pl.col("TM")).otherwise(0).cast(pl.Int64).alias("Taxa_Nominal_PH")
        )

        # Agrega somando a produção
        df_agg = df.group_by(["Maquina", "Turno", "NumerodaPeca"]).agg([
            pl.col("Taxa_Nominal_PH").mean().cast(pl.Int64), 
            pl.col("QtdeProduzidaBoa").sum()
        ])

        # 5. JOIN
        final = df_agg.join(
            df_in.select(["Maquina", "Turno", "NumerodaPeca", "Horas_Disponiveis"]), 
            on=["Maquina", "Turno", "NumerodaPeca"], 
            how="left"
        ).fill_null(0)

        # 6. CÁLCULO OEE
        final = final.with_columns([
            (pl.col("Taxa_Nominal_PH") * pl.col("Horas_Disponiveis")).cast(pl.Int64).alias("Prod_Planejada_Total")
        ]).with_columns([
            pl.when(pl.col("Prod_Planejada_Total") > 0)
            .then(pl.col("QtdeProduzidaBoa") / pl.col("Prod_Planejada_Total"))
            .otherwise(0)
            .alias("OEE_Decimal")
        ])

        final = final.with_columns([
            ((pl.col("OEE_Decimal") * 100).round(0).cast(pl.Int64).cast(pl.Utf8) + "%").alias("OEE_Simplificado_%")
        ])

        # 7. EXPORTAÇÃO
        final = final.select([
            "Maquina", "Turno", "NumerodaPeca", "QtdeProduzidaBoa", "Horas_Disponiveis", "Taxa_Nominal_PH", "Prod_Planejada_Total", "OEE_Simplificado_%"
        ]).sort(["Maquina", "Turno", "NumerodaPeca"])

        final.write_csv(ARQUIVO_SAIDA, separator=';')
        print("\n" + "-"*50)
        print(f"✅ RELATÓRIO CORRIGIDO: {ARQUIVO_SAIDA.name}")

    except Exception as e:
        print(f"❌ ERRO: {e}")

if __name__ == "__main__":
    calcular()  