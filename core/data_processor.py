import os
import json
import time
import requests
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from core.config import (
    DATA_DIR, UPLOADS_DIR, DEFAULT_DATA_FILE, ACTIVE_DATA_FILE, CACHE_FILE,
    GOOGLE_SHEET_EXPORT_URL, TARGET_LIQUIDATION_RATE, TARGET_EXECUTION_RATE,
    TARGET_SLA_DAYS, ANOMALY_SLA_DAYS
)

class DataProcessor:
    def __init__(self):
        self.df: Optional[pd.DataFrame] = None
        self.last_updated: Optional[str] = None
        self.data_source: str = "Local Baseline"
        self.total_records: int = 0
        self.is_processing: bool = False
        self._cache: Dict[str, Any] = {}
        
    def _clean_brl(self, val) -> float:
        """Parse Brazilian currency string '1.234,56' to float."""
        if pd.isna(val):
            return 0.0
        s = str(val).strip().replace('.', '').replace(',', '.')
        try:
            return float(s)
        except Exception:
            return 0.0

    def load_and_process(self, file_path: Optional[Path] = None, source_label: Optional[str] = None) -> bool:
        """Load CSV or Excel file, clean data, compute SLAs and cache analytics."""
        self.is_processing = True
        try:
            target_path = file_path or ACTIVE_DATA_FILE
            if not target_path.exists():
                target_path = DEFAULT_DATA_FILE
                
            if not target_path.exists():
                print(f"[ERROR] Data file not found at {target_path}")
                self.is_processing = False
                return False

            print(f"[INFO] Loading data from {target_path.name}...")
            if target_path.suffix.lower() in ['.xlsx', '.xls']:
                raw_df = pd.read_excel(target_path)
            else:
                # Try UTF-8 first, fallback to Latin1
                try:
                    raw_df = pd.read_csv(target_path, encoding='utf-8')
                except UnicodeDecodeError:
                    raw_df = pd.read_csv(target_path, encoding='latin1')

            raw_df.columns = [str(c).strip() for c in raw_df.columns]

            # Identify core columns dynamically
            def find_col(patterns):
                for p in patterns:
                    for c in raw_df.columns:
                        if p.upper() in c.upper():
                            return c
                return None

            col_emp = find_col(['EMPENHO'])
            col_liq = find_col(['LIQUID'])
            col_pag = find_col(['PAGAM'])
            col_credor = find_col(['CREDOR', 'FORNECEDOR']) or 'Credor'
            col_tema = find_col(['TEMA', 'CATEGORIA']) or 'Tema'
            col_ano = find_col(['ANO']) or 'Ano'
            col_mes = find_col(['MÊS', 'MES']) or 'Mês'
            col_dt_emiss = find_col(['DATA EMISS', 'DT_EMISS']) or 'Data Emissão'
            col_dt_pag = find_col(['DATA PAGAM', 'DT_PAG']) or 'Data Pagamento'
            col_doc_ne = find_col(['DOCUMENTONE', 'NE']) or 'DocumentoNE'
            col_doc_nl = find_col(['DOCUMENTONL', 'NL']) or 'DocumentoNL'
            col_doc_ob = find_col(['DOCUMENTOOB', 'OB']) or 'DocumentoOB'

            # Parse monetary columns
            raw_df['empenho_val'] = raw_df[col_emp].apply(self._clean_brl) if col_emp else 0.0
            raw_df['liquidado_val'] = raw_df[col_liq].apply(self._clean_brl) if col_liq else 0.0
            raw_df['pagamento_val'] = raw_df[col_pag].apply(self._clean_brl) if col_pag else 0.0

            # Normalize strings
            raw_df['credor_clean'] = raw_df[col_credor].fillna('NÃO INFORMADO').astype(str).str.strip()
            raw_df['tema_clean'] = raw_df[col_tema].fillna('Outros').astype(str).str.strip()
            raw_df['ano_clean'] = pd.to_numeric(raw_df[col_ano], errors='coerce').fillna(2025).astype(int)
            raw_df['mes_clean'] = raw_df[col_mes].fillna('ind').astype(str).str.lower().str.strip()

            # Clean Credor display name (remove leading CNPJ if present for clean UI)
            def clean_credor_name(c):
                parts = c.split(' - ', 1)
                return parts[1].strip() if len(parts) > 1 else c

            raw_df['credor_display'] = raw_df['credor_clean'].apply(clean_credor_name)

            # Parse dates
            raw_df['dt_emissao'] = pd.to_datetime(raw_df[col_dt_emiss], format='%d/%m/%Y', errors='coerce')
            raw_df['dt_pagamento'] = pd.to_datetime(raw_df[col_dt_pag], format='%d/%m/%Y', errors='coerce')

            # Calculate SLA (Liquidação -> Pagamento & Empenho -> Pagamento)
            nl_dates = raw_df[raw_df[col_doc_nl] != '-'].groupby(col_doc_nl)['dt_emissao'].min() if col_doc_nl in raw_df else pd.Series(dtype='datetime64[ns]')
            ne_dates = raw_df[raw_df[col_doc_ne] != '-'].groupby(col_doc_ne)['dt_emissao'].min() if col_doc_ne in raw_df else pd.Series(dtype='datetime64[ns]')

            raw_df['dt_nl_emissao'] = raw_df[col_doc_nl].map(nl_dates) if col_doc_nl in raw_df else pd.NaT
            raw_df['dt_ne_emissao'] = raw_df[col_doc_ne].map(ne_dates) if col_doc_ne in raw_df else pd.NaT

            # SLA in days
            sla_liq = (raw_df['dt_pagamento'] - raw_df['dt_nl_emissao']).dt.days
            # Fallback to direct difference if NL not mapped
            sla_direct = (raw_df['dt_pagamento'] - raw_df['dt_emissao']).dt.days
            raw_df['sla_dias'] = np.where(sla_liq.notna() & (sla_liq >= 0), sla_liq, np.where(sla_direct >= 0, sla_direct, np.nan))
            # Clip unreasonable anomalies beyond 365 days
            raw_df['sla_dias'] = raw_df['sla_dias'].apply(lambda x: x if 0 <= x <= 365 else np.nan)

            self.df = raw_df
            self.total_records = len(raw_df)
            self.last_updated = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self.data_source = source_label or target_path.name
            
            # Clear cached aggregations
            self._cache.clear()
            print(f"[SUCCESS] Processed {self.total_records} records from {self.data_source}.")
            self.is_processing = False
            return True
        except Exception as e:
            print(f"[ERROR] Failed to load data: {e}")
            import traceback
            traceback.print_exc()
            self.is_processing = False
            return False

    def sync_from_google_sheets(self) -> Dict[str, Any]:
        """Fetch daily updated sheet from Google Sheets, save to active_data.csv and reprocess."""
        try:
            print(f"[INFO] Fetching latest sheet from Google Sheets: {GOOGLE_SHEET_EXPORT_URL}")
            resp = requests.get(GOOGLE_SHEET_EXPORT_URL, timeout=30)
            if resp.status_code != 200:
                return {
                    "success": False,
                    "error": f"Erro HTTP ao acessar Google Sheets: {resp.status_code}"
                }
            
            # Save downloaded content to active_data.csv
            with open(ACTIVE_DATA_FILE, "wb") as f:
                f.write(resp.content)

            ok = self.load_and_process(ACTIVE_DATA_FILE, source_label="Google Sheets Online (Sincronizado)")
            if ok:
                return {
                    "success": True,
                    "records": self.total_records,
                    "last_updated": self.last_updated,
                    "source": "Google Sheets Online"
                }
            else:
                return {"success": False, "error": "Falha no processamento dos dados baixados"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def import_uploaded_file(self, file_path: Path, filename: str) -> Dict[str, Any]:
        """Import a newly uploaded CSV or Excel file, archive into active_data and reprocess."""
        try:
            # Overwrite active data file
            import shutil
            if file_path.suffix.lower() == '.csv':
                shutil.copyfile(file_path, ACTIVE_DATA_FILE)
            ok = self.load_and_process(file_path, source_label=f"Arquivo Upload: {filename}")
            if ok:
                return {
                    "success": True,
                    "records": self.total_records,
                    "last_updated": self.last_updated,
                    "filename": filename
                }
            return {"success": False, "error": "Falha no processamento do arquivo"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _filter_df(self, year: Optional[Any] = None, month: Optional[Any] = None, tema: Optional[Any] = None) -> pd.DataFrame:
        if self.df is None or self.df.empty:
            self.load_and_process()
            
        filtered = self.df
        
        # Safe year filter
        if year is not None and not isinstance(year, (int, float, str)):
            year = None
        if year is not None and str(year).strip() not in ["", "0", "all", "None"]:
            try:
                filtered = filtered[filtered['ano_clean'] == int(year)]
            except (ValueError, TypeError):
                pass

        # Safe month filter
        if month is not None and not isinstance(month, str):
            month = None
        if month and str(month).strip() not in ["", "all", "None"]:
            filtered = filtered[filtered['mes_clean'] == str(month).lower().strip()]

        # Safe tema filter
        if tema is not None and not isinstance(tema, str):
            tema = None
        if tema and str(tema).strip() not in ["", "all", "None"]:
            filtered = filtered[filtered['tema_clean'] == str(tema).strip()]

        return filtered

    def get_filter_options(self) -> Dict[str, Any]:
        """Return available years, months, and themes for dashboard filters."""
        if self.df is None or self.df.empty:
            self.load_and_process()
            
        years = sorted(self.df['ano_clean'].unique().tolist())
        # Ordered months
        month_order = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
        available_months = self.df['mes_clean'].unique().tolist()
        months = [m for m in month_order if m in available_months]
        
        # Temas sorted by payment volume
        temas = self.df.groupby('tema_clean')['pagamento_val'].sum().sort_values(ascending=False).index.tolist()
        
        return {
            "years": years,
            "months": months,
            "temas": temas,
            "total_records": self.total_records,
            "last_updated": self.last_updated,
            "source": self.data_source
        }

    def get_summary_kpis(self, year: Optional[int] = None, month: Optional[str] = None, tema: Optional[str] = None) -> Dict[str, Any]:
        """Compute top executive KPIs with adherence, SLA, and IGEO."""
        df = self._filter_df(year, month, tema)
        
        total_emp = float(df['empenho_val'].sum())
        total_liq = float(df['liquidado_val'].sum())
        total_pag = float(df['pagamento_val'].sum())
        
        # Operational Efficiency Rates
        taxa_liquidacao = (total_liq / total_emp * 100) if total_emp > 0 else 100.0
        taxa_execucao = (total_pag / total_liq * 100) if total_liq > 0 else 100.0
        
        # SLA Calculation (on paid transactions)
        sla_series = df[df['pagamento_val'] > 0]['sla_dias'].dropna()
        sla_medio = float(sla_series.mean()) if not sla_series.empty else TARGET_SLA_DAYS
        sla_mediana = float(sla_series.median()) if not sla_series.empty else TARGET_SLA_DAYS
        sla_compliance_rate = float((sla_series <= TARGET_SLA_DAYS).mean() * 100) if not sla_series.empty else 100.0
        
        # IGEO - Índice Global de Eficiência Operacional (0 - 100)
        # Factors: Taxa de Liquidação (35%), Taxa de Execução (35%), Cumprimento do SLA (30%)
        score_liq = min(100.0, taxa_liquidacao)
        score_exec = min(100.0, taxa_execucao)
        score_sla = sla_compliance_rate
        igeo = round(0.35 * score_liq + 0.35 * score_exec + 0.30 * score_sla, 1)
        igeo = max(0.0, min(100.0, igeo))
        
        # Status classification
        if igeo >= 88.0:
            status_class = "Excelente"
            status_color = "emerald"
        elif igeo >= 75.0:
            status_class = "Bom / Estável"
            status_color = "blue"
        elif igeo >= 60.0:
            status_class = "Atenção"
            status_color = "amber"
        else:
            status_class = "Crítico"
            status_color = "rose"

        # Restos a pagar / Pendências operacionais
        saldo_empenhado_aberto = max(0.0, total_emp - total_liq)
        saldo_liquidado_pendente = max(0.0, total_liq - total_pag)
        
        # Total counts
        total_transacoes = len(df)
        total_credores = int(df['credor_clean'].nunique())
        total_temas = int(df['tema_clean'].nunique())

        # Anomaly count (transactions with SLA > ANOMALY_SLA_DAYS)
        anomalias_sla_count = int((sla_series > ANOMALY_SLA_DAYS).sum())

        return {
            "total_empenhado": round(total_emp, 2),
            "total_liquidado": round(total_liq, 2),
            "total_pago": round(total_pag, 2),
            "taxa_liquidacao": round(taxa_liquidacao, 1),
            "taxa_execucao": round(taxa_execucao, 1),
            "sla_medio_dias": round(sla_medio, 1),
            "sla_mediana_dias": round(sla_mediana, 1),
            "sla_compliance_rate": round(sla_compliance_rate, 1),
            "target_sla_days": TARGET_SLA_DAYS,
            "igeo_score": igeo,
            "status_class": status_class,
            "status_color": status_color,
            "saldo_empenhado_aberto": round(saldo_empenhado_aberto, 2),
            "saldo_liquidado_pendente": round(saldo_liquidado_pendente, 2),
            "total_transacoes": total_transacoes,
            "total_credores": total_credores,
            "total_temas": total_temas,
            "anomalias_sla_count": anomalias_sla_count,
            "last_updated": self.last_updated,
            "data_source": self.data_source
        }

    def get_monthly_trends(self, year: Optional[int] = None, tema: Optional[str] = None) -> Dict[str, Any]:
        """Compute chronological evolution of values and SLA across months."""
        df = self._filter_df(year, month=None, tema=tema)
        
        month_order = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
        
        # Group by Ano and Mês
        grouped = df.groupby(['ano_clean', 'mes_clean']).agg(
            empenho=('empenho_val', 'sum'),
            liquidado=('liquidado_val', 'sum'),
            pagamento=('pagamento_val', 'sum'),
            sla_medio=('sla_dias', 'mean'),
            transacoes=('pagamento_val', 'count')
        ).reset_index()

        # Custom sorting
        def month_sort_key(row):
            m_idx = month_order.index(row['mes_clean']) if row['mes_clean'] in month_order else 99
            return (row['ano_clean'], m_idx)

        grouped['sort_key'] = grouped.apply(month_sort_key, axis=1)
        grouped = grouped.sort_values('sort_key').drop(columns=['sort_key'])

        labels = [f"{r['mes_clean'].upper()}/{r['ano_clean']}" for _, r in grouped.iterrows()]
        empenho = [round(float(v), 2) for v in grouped['empenho']]
        liquidado = [round(float(v), 2) for v in grouped['liquidado']]
        pagamento = [round(float(v), 2) for v in grouped['pagamento']]
        sla = [round(float(v), 1) if pd.notna(v) else TARGET_SLA_DAYS for v in grouped['sla_medio']]

        return {
            "labels": labels,
            "empenhado": empenho,
            "liquidado": liquidado,
            "pago": pagamento,
            "sla_medio": sla
        }

    def get_thematic_pareto(self, year: Optional[Any] = None, month: Optional[Any] = None, top_n: int = 10) -> Dict[str, Any]:
        """Compute thematic Pareto curve (volume, share, cumulative %, SLA)."""
        if not isinstance(top_n, int):
            try: top_n = int(str(top_n))
            except Exception: top_n = 10
        df = self._filter_df(year, month, tema=None)
        
        grouped = df.groupby('tema_clean').agg(
            total_pago=('pagamento_val', 'sum'),
            total_liquidado=('liquidado_val', 'sum'),
            sla_medio=('sla_dias', 'mean'),
            qtd_transacoes=('pagamento_val', 'count')
        ).reset_index().sort_values('total_pago', ascending=False)

        total_executado = grouped['total_pago'].sum()
        if total_executado == 0:
            total_executado = 1.0

        grouped['percentual'] = (grouped['total_pago'] / total_executado) * 100
        grouped['acumulado'] = grouped['percentual'].cumsum()

        # Classificação ABC
        def class_abc(cum):
            if cum <= 80: return 'A'
            elif cum <= 95: return 'B'
            return 'C'

        grouped['classe'] = grouped['acumulado'].apply(class_abc)

        top_slice = grouped.head(top_n)
        
        items = []
        for _, r in top_slice.iterrows():
            items.append({
                "tema": r['tema_clean'],
                "total_pago": round(float(r['total_pago']), 2),
                "total_liquidado": round(float(r['total_liquidado']), 2),
                "sla_medio": round(float(r['sla_medio']), 1) if pd.notna(r['sla_medio']) else 0.0,
                "qtd_transacoes": int(r['qtd_transacoes']),
                "percentual": round(float(r['percentual']), 1),
                "acumulado": round(float(r['acumulado']), 1),
                "classe": r['classe']
            })

        return {
            "labels": [i['tema'] for i in items],
            "valores": [i['total_pago'] for i in items],
            "percentual_acumulado": [i['acumulado'] for i in items],
            "sla": [i['sla_medio'] for i in items],
            "detalhes": items
        }

    def get_credor_rankings(self, year: Optional[Any] = None, month: Optional[Any] = None, tema: Optional[Any] = None, limit: int = 40) -> List[Dict[str, Any]]:
        """Compute multidimensional ranking of Credores with performance scoring."""
        if not isinstance(limit, int):
            try: limit = int(str(limit))
            except Exception: limit = 40
        df = self._filter_df(year, month, tema)
        
        # Filter for credores with active payments or liquidations
        grouped = df.groupby(['credor_clean', 'credor_display']).agg(
            total_pago=('pagamento_val', 'sum'),
            total_liquidado=('liquidado_val', 'sum'),
            total_empenhado=('empenho_val', 'sum'),
            sla_medio=('sla_dias', 'mean'),
            transacoes=('pagamento_val', 'count'),
            temas=('tema_clean', lambda s: list(s.unique())[:3])
        ).reset_index()

        # Sort by total pago
        grouped = grouped.sort_values('total_pago', ascending=False)

        max_pago = grouped['total_pago'].max() if not grouped.empty else 1.0

        rankings = []
        for idx, r in enumerate(grouped.head(limit).iterrows()):
            data = r[1]
            sla = float(data['sla_medio']) if pd.notna(data['sla_medio']) else TARGET_SLA_DAYS
            
            # Score logic:
            # 1. SLA efficiency: 100 if SLA <= 10, penalize as SLA exceeds 15
            score_sla = max(10.0, 100.0 - max(0.0, (sla - TARGET_SLA_DAYS) * 3.5))
            # 2. Execution rate: Liquidado vs Empenhado
            taxa_exec = (data['total_pago'] / data['total_liquidado'] * 100) if data['total_liquidado'] > 0 else 100.0
            score_exec = min(100.0, max(20.0, taxa_exec))
            
            # Global Credor Score (0-100)
            score_global = round(0.55 * score_sla + 0.45 * score_exec, 1)
            score_global = max(10.0, min(100.0, score_global))

            if score_global >= 85.0:
                badge = "Excelente"
                badge_color = "emerald"
            elif score_global >= 70.0:
                badge = "Atenção"
                badge_color = "amber"
            else:
                badge = "Crítico"
                badge_color = "rose"

            rankings.append({
                "posicao": idx + 1,
                "credor_completo": data['credor_clean'],
                "credor_nome": data['credor_display'],
                "total_pago": round(float(data['total_pago']), 2),
                "total_liquidado": round(float(data['total_liquidado']), 2),
                "sla_medio": round(sla, 1),
                "transacoes": int(data['transacoes']),
                "score": score_global,
                "badge": badge,
                "badge_color": badge_color,
                "principais_temas": data['temas']
            })

        return rankings

    def get_deviations_and_anomalies(self, year: Optional[int] = None, month: Optional[str] = None, tema: Optional[str] = None) -> List[Dict[str, Any]]:
        """Identify critical operational deviations, bottlenecks, and anomalies."""
        df = self._filter_df(year, month, tema)
        anomalies = []

        # 1. Bottlenecks: Credores with High SLA (> 30 days) and substantial payment (> R$ 100k)
        credor_sla = df[df['pagamento_val'] > 0].groupby('credor_display').agg(
            total_pago=('pagamento_val', 'sum'),
            sla_medio=('sla_dias', 'mean'),
            qtd=('pagamento_val', 'count'),
            tema=('tema_clean', lambda s: s.iloc[0])
        ).reset_index()

        critical_sla = credor_sla[(credor_sla['sla_medio'] > ANOMALY_SLA_DAYS) & (credor_sla['total_pago'] > 50000)].sort_values('sla_medio', ascending=False)
        for _, r in critical_sla.head(4).iterrows():
            anomalies.append({
                "tipo": "Gargalo de Processamento (SLA)",
                "severidade": "Alta",
                "cor": "rose",
                "titulo": f"SLA Crítico: {r['credor_display'][:35]}...",
                "descricao": f"Tempo médio de liquidação para pagamento atingiu {r['sla_medio']:.1f} dias (meta: {TARGET_SLA_DAYS} dias). Montante executado: R$ {r['total_pago']:,.2f}.",
                "tema": r['tema'],
                "acao_sugerida": "Auditar fluxo de ateste e liberação de ordem bancária com a gerência setorial."
            })

        # 2. Concentração Excessiva (Pareto Risk): Top Credores representing high % of theme
        tema_groups = df.groupby('tema_clean')['pagamento_val'].sum()
        for t_name, t_total in tema_groups.items():
            if t_total > 5000000: # Temas com mais de 5M
                df_tema = df[df['tema_clean'] == t_name]
                top_credor = df_tema.groupby('credor_display')['pagamento_val'].sum().sort_values(ascending=False)
                if not top_credor.empty:
                    top_name = top_credor.index[0]
                    top_val = top_credor.iloc[0]
                    pct = (top_val / t_total) * 100
                    if pct > 45.0:
                        anomalies.append({
                            "tipo": "Concentração de Fornecedor",
                            "severidade": "Média",
                            "cor": "amber",
                            "titulo": f"Alta Concentração em {t_name}",
                            "descricao": f"O fornecedor '{top_name[:35]}' concentra {pct:.1f}% de todos os pagamentos da categoria (R$ {top_val:,.2f} de R$ {t_total:,.2f}).",
                            "tema": t_name,
                            "acao_sugerida": "Avaliar diversificação de fornecedores ou revisão de edital de contratação."
                        })

        # 3. Empenhos não liquidados (Risco de restos a pagar cancelados)
        pendencias_emp = df.groupby('tema_clean').agg(
            emp=('empenho_val', 'sum'),
            liq=('liquidado_val', 'sum')
        )
        pendencias_emp['diferenca'] = pendencias_emp['emp'] - pendencias_emp['liq']
        critical_emp = pendencias_emp[pendencias_emp['diferenca'] > 2000000].sort_values('diferenca', ascending=False)
        for t_name, r in critical_emp.head(2).iterrows():
            anomalies.append({
                "tipo": "Desvio de Liquidação Orçamentária",
                "severidade": "Média",
                "cor": "blue",
                "titulo": f"Empenho Não Liquidado em {t_name}",
                "descricao": f"Existe uma defasagem de R$ {r['diferenca']:,.2f} entre empenhado e liquidado.",
                "tema": t_name,
                "acao_sugerida": "Verificar se as entregas dos prestadores foram atestadas para evitar perda de dotação."
            })

        return anomalies[:8]

    def generate_decision_insights(self, year: Optional[int] = None, month: Optional[str] = None, tema: Optional[str] = None) -> List[Dict[str, Any]]:
        """Generate high-level Decision Intelligence recommendations."""
        df = self._filter_df(year, month, tema)
        
        total_pago = float(df['pagamento_val'].sum())
        sla_medio = float(df[df['pagamento_val'] > 0]['sla_dias'].mean()) if not df[df['pagamento_val'] > 0].empty else 15.0

        # Estimate savings on 3% optimization in top operational contracts
        terceirizados_val = float(df[df['tema_clean'] == 'Terceirizados']['pagamento_val'].sum())
        saving_potential = terceirizados_val * 0.035

        insights = [
            {
                "categoria": "Eficiência de Contratos",
                "icone": "sparkles",
                "impacto_estimado": f"R$ {saving_potential:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                "titulo": "Oportunidade de Otimização em Terceirizados",
                "narrativa": f"A rubrica de Terceirizados totaliza R$ {terceirizados_val:,.2f}. Uma padronização de postos de trabalho e renegociação em contratos vigentes pode gerar uma economia anual estimada de 3,5%, liberando recursos para investimentos prioritários.",
                "prioridade": "Alta",
                "badge_cor": "emerald"
            },
            {
                "categoria": "Desgargalamento de SLA",
                "icone": "clock",
                "impacto_estimado": f"-{max(3, round(sla_medio - TARGET_SLA_DAYS, 1))} dias no ciclo",
                "titulo": "Aceleração do Fluxo de Liquidação para Pagamento",
                "narrativa": f"O SLA atual médio é de {sla_medio:.1f} dias. Implementar assinatura digital pré-aprovada para notas fiscais recorrentes (energia e bilhetagem) reduzirá o tempo de ciclo em até 40%, melhorando a pontuação de conformidade com os fornecedores.",
                "prioridade": "Média",
                "badge_cor": "blue"
            },
            {
                "categoria": "Governança e Risco",
                "icone": "shield",
                "impacto_estimado": "Mitigação de Multas",
                "titulo": "Monitoramento Pró-ativo de Vencimentos em Utilities",
                "narrativa": "Faturas de energia e saneamento possuem prazos rígidos de adimplemento. Recomenda-se a automação da rotina de empenho automático estimado no primeiro dia útil do mês para zerar qualquer incidência de encargos moratórios.",
                "prioridade": "Alta",
                "badge_cor": "amber"
            }
        ]
        return insights

    def simulate_what_if(self, sla_improvement_pct: float, cost_reduction_pct: float, year: Optional[int] = None) -> Dict[str, Any]:
        """Executive What-If Scenario Simulator."""
        df = self._filter_df(year)
        total_pago = float(df['pagamento_val'].sum())
        sla_medio = float(df[df['pagamento_val'] > 0]['sla_dias'].mean()) if not df[df['pagamento_val'] > 0].empty else 15.0

        # Simulated Values
        reais_economizados = total_pago * (cost_reduction_pct / 100.0)
        novo_sla = max(1.0, sla_medio * (1.0 - (sla_improvement_pct / 100.0)))
        dias_poupados = sla_medio - novo_sla

        # Simulated IGEO gain
        ganho_igeo = round((cost_reduction_pct * 0.4) + (sla_improvement_pct * 0.3), 1)

        return {
            "custo_atual_total": round(total_pago, 2),
            "economia_projetada_reais": round(reais_economizados, 2),
            "sla_atual_dias": round(sla_medio, 1),
            "novo_sla_projetado": round(novo_sla, 1),
            "dias_poupados_ciclo": round(dias_poupados, 1),
            "ganho_pontos_igeo": ganho_igeo,
            "cenario": f"Redução de {cost_reduction_pct}% em custos + Otimização de {sla_improvement_pct}% no SLA"
        }

# Singleton instance
data_processor = DataProcessor()
