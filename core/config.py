import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
DEFAULT_DATA_FILE = DATA_DIR / "sample_data.csv"
ACTIVE_DATA_FILE = DATA_DIR / "active_data.csv"
CACHE_FILE = DATA_DIR / "metrics_cache.json"

# Google Sheets Config (From user request)
GOOGLE_SHEET_ID = "1uQcCEjud5tnj9vpbRzYJq-J89GMgl_3-YwoCHaurnmU"
GOOGLE_SHEET_GID = "507908437"
GOOGLE_SHEET_EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=csv&gid={GOOGLE_SHEET_GID}"

# JWT / Security Settings
SECRET_KEY = os.getenv("APP_SECRET_KEY", "eficiencia_operacional_super_secret_jwt_2026_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Operational Target Thresholds (KPIs de Eficiência)
TARGET_LIQUIDATION_RATE = 92.0    # %
TARGET_EXECUTION_RATE = 95.0      # %
TARGET_SLA_DAYS = 15.0            # Dias entre emissão e pagamento
ANOMALY_SLA_DAYS = 30.0           # Alerta de gargalo crítico

# Pre-configured Users
USERS_DB = {
    "admin@operacoes.gov.br": {
        "username": "admin@operacoes.gov.br",
        "name": "Cristiano Sena",
        "role": "admin",
        "role_title": "Diretor de Operações e Estratégia",
        "password_hash": "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9", # admin123
        "avatar": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"
    },
    "gestor@operacoes.gov.br": {
        "username": "gestor@operacoes.gov.br",
        "name": "Mariana Albuquerque",
        "role": "gestor",
        "role_title": "Gestora de Eficiência Operacional",
        "password_hash": "18f2b94d784d03c222cb7c47148cdb8457f1ef3eaf3e317711f25d55747f6a35", # gestor123
        "avatar": "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=120&auto=format&fit=crop&q=80"
    },
    "analista@operacoes.gov.br": {
        "username": "analista@operacoes.gov.br",
        "name": "Lucas Vasconcelos",
        "role": "analista",
        "role_title": "Analista de Processos & Dados",
        "password_hash": "9cd268397030111adacb4268e51f0dbbb0dbc8c59eb34f8f7d55f72d4c888349", # analista123
        "avatar": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=120&auto=format&fit=crop&q=80"
    }
}
