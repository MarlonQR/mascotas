import os
import psycopg2

def obtener_conexion():
    # En Supabase se puede pegar la cadena de conexión completa
    # (Connect > Transaction pooler) en DATABASE_URL.
    url = os.getenv("DATABASE_URL")

    if url:
        return psycopg2.connect(url, connect_timeout=10)

    conexion = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        port=os.getenv("DB_PORT", "5432"),
        sslmode=os.getenv("DB_SSLMODE", "prefer"),
        connect_timeout=10
    )
    return conexion
