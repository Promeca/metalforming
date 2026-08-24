import polars as pl
from pathlib import Path

# --- CONFIGURAÇÃO ---
CAMINHO_BASE = Path(r'M:\\NTA2\\LMD\\Evento Lean\\Dados e Documentos Gerais JBMC1\\vscode\\work_sheets')
CAMINHO_ENTRADA = CAMINHO_BASE / 'a.csv'
ARQUIVO_SAIDA_HORAS = CAMINHO_BASE / 'horas_planejadas_por_item.csv'

def preparar_df(caminho):
    """Lê o CSV, limpa cabeçalhos e normaliza o ID das máquinas."""
    df = pl.read_csv(caminho, separator=';', encoding='latin1', infer_schema_length=0)
    
    # Limpa espaços e quebras de linha nos nomes das colunas
    df = df.rename({c: c.strip().replace('\r', '').replace('\n', '') for c in df.columns})
    
    mapeamento = {}
    for col in df.columns:
        if "BWMANR" in col: mapeamento[col] = "Maquina"
        elif "BWTENR" in col: mapeamento[col] = "NumerodaPeca"
    
    df = df.rename(mapeamento)
    
    # Padronização: Remove espaços e zeros à esquerda (ex: "00114" -> "114")
    df = df.with_columns(
        pl.col("Maquina").str.strip_chars().str.strip_chars_start("0")
    )
    return df

def coletar_input_maquinas():
    print("\n" + "="*80)
    print("      PASSO 2: INPUT DE HORAS (CORREÇÃO DE MÁQUINAS E SOMA)")
    print("="*80)

    try:
        df = preparar_df(CAMINHO_ENTRADA)
        
        # Pega as combinações únicas para atribuir as horas
        df_base = df.select(["Maquina", "Turno", "NumerodaPeca"]).unique()
        
        # 1. DEFINIÇÃO DA JORNADA BASE
        df_base = df_base.with_columns(
            pl.when(pl.col("Turno").str.contains("Administrativo")).then(8.75)
            .when(pl.col("Turno").str.contains("Primeiro Turno")).then(7.4)
            .when(pl.col("Turno").str.contains("Segundo Turno")).then(7.4)
            .when(pl.col("Turno").str.contains("Terceiro Turno")).then(5.8)
            .otherwise(7.4)
            .alias("Horas_Base")
        )

        print(f"✔ Base Aplicada: T1/T2=7.4h | T3=5.97h | ADM=8.75h")

        # 2. INPUT DE EXCEÇÕES (REVEZAMENTO E HORA EXTRA)
        print("\n--- EXCEÇÕES ---")
        
        # Revezamento
        print("Digite as MÁQUINAS com REVEZAMENTO (separadas por espaço). Ex: 114 105")
        input_revez = input("Máquinas: ").strip().split()
        maqs_revez = [m.lstrip("0") for m in input_revez]
        
        horas_revez = 0.0
        if maqs_revez:
            val = input(f"Quantas HORAS de revezamento para {maqs_revez}? (ex: 0.5): ").replace(',', '.')
            horas_revez = float(val) if val else 0.0

        # Hora Extra
        print("\nDigite as MÁQUINAS com HORA EXTRA (separadas por espaço). Ex: 120 130")
        input_extras = input("Máquinas: ").strip().split()
        maqs_extras = [m.lstrip("0") for m in input_extras]
        
        valor_extra = 0.0
        if maqs_extras:
            val = input(f"Quantas HORAS EXTRAS para {maqs_extras}? (ex: 2): ").replace(',', '.')
            valor_extra = float(val) if val else 0.0

        # 3. CÁLCULO FINAL (Base - Revez + Extra)
        # Aplicamos as subtrações e somas de forma condicional
        df_final = df_base.with_columns(
            pl.when(pl.col("Maquina").is_in(maqs_revez))
            .then(pl.col("Horas_Base") - horas_revez)
            .otherwise(pl.col("Horas_Base"))
            .alias("Horas_Temp")
        ).with_columns(
            pl.when(pl.col("Maquina").is_in(maqs_extras))
            .then(pl.col("Horas_Temp") + valor_extra)
            .otherwise(pl.col("Horas_Temp"))
            .alias("Horas_Disponiveis")
        )

        # 4. VERIFICAÇÃO E SALVAMENTO
        if maqs_extras or maqs_revez:
            print("\n🔍 Verificação de Alterações:")
            maqs_alteradas = maqs_revez + maqs_extras
            print(df_final.filter(pl.col("Maquina").is_in(maqs_alteradas))
                  .select(["Maquina", "Turno", "Horas_Disponiveis"]).head(10))

        df_export = df_final.select(["Maquina", "Turno", "NumerodaPeca", "Horas_Disponiveis"])
        df_export.write_csv(ARQUIVO_SAIDA_HORAS, separator=';')
        
        print("\n" + "-"*50)
        print(f"✅ PASSO 2 CONCLUÍDO! Arquivo salvo: {ARQUIVO_SAIDA_HORAS.name}")

    except Exception as e:
        print(f"❌ ERRO CRÍTICO: {e}")

if __name__ == "__main__":
    coletar_input_maquinas()