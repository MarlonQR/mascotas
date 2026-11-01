import os
import psycopg2

def obtener_conexion():
    # En Supabase se puede pegar la cadena de conexión completa
    # (Connect > Transaction pooler) en DATABASE_URL.
    # strip() quita espacios o saltos de línea pegados por error.
    url = os.getenv("DATABASE_URL", "").strip()

    try:
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

    except psycopg2.Error as error:
        # Queda en los Logs de Vercel. El mensaje no incluye la contraseña.
        print(f"Error de conexión a PostgreSQL (DATABASE_URL definida: {bool(url)}): {error}")
        raise
