"""Crea la base de datos y aplica schema.sql.

Uso:
    python init_db.py

Requiere PGPASSWORD (o DATABASE_URL) configurada en Proyecto/.env.
"""
import os
import sys
from pathlib import Path

import database


def statements():
    text = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.strip().startswith("--")]
    buffer, in_quote = [], False
    for character in "\n".join(lines):
        if character == "'":
            in_quote = not in_quote
            buffer.append(character)
        elif character == ";" and not in_quote:
            statement = "".join(buffer).strip()
            if statement and statement.upper() not in ("BEGIN", "COMMIT"):
                yield statement
            buffer = []
        else:
            buffer.append(character)
    statement = "".join(buffer).strip()
    if statement and statement.upper() not in ("BEGIN", "COMMIT"):
        yield statement


def main():
    if not database.is_configured():
        sys.exit("Configura PGPASSWORD o DATABASE_URL en Proyecto/.env y vuelve a ejecutar.")

    target = os.environ.get("PGDATABASE", "objetos_perdidos")
    os.environ.setdefault("PGDATABASE", target)

    try:
        from psycopg import sql
    except ImportError:
        sys.exit("Falta psycopg. Ejecuta: pip install -r requirements.txt.")

    try:
        with database.connect(dbname="postgres") as admin:
            admin.autocommit = True
            with admin.cursor() as cursor:
                cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target,))
                if cursor.fetchone() is None:
                    cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target)))
                    print(f"Base de datos «{target}» creada.")
                else:
                    print(f"Base de datos «{target}» ya existe.")

        with database.connect() as connection:
            with connection.cursor() as cursor:
                for statement in statements():
                    cursor.execute(statement)
    except Exception as error:
        sys.exit(f"No se pudo inicializar la base de datos: {error}")

    print("Esquema aplicado correctamente.")


if __name__ == "__main__":
    main()
