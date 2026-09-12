"""
Camada de persistência de dados.
Compatível com MySQL (Produção no Railway) e SQLite (Desenvolvimento local).
"""

import logging
import os
import re
from typing import Optional
from urllib.parse import urlparse

from app import config

logger = logging.getLogger(__name__)

# O Railway pode disponibilizar como MYSQL_URL ou DATABASE_URL
DATABASE_URL = (
    os.getenv("MYSQL_URL")
    or os.getenv("DATABASE_URL")
    or getattr(config, "DATABASE_URL", None)
)


def _get_connection():
    if DATABASE_URL and ("mysql" in DATABASE_URL.lower()):
        import pymysql

        # Parseia a URL mysql://user:password@host:port/database
        parsed = urlparse(DATABASE_URL)
        return pymysql.connect(
            host=parsed.hostname,
            user=parsed.username,
            password=parsed.password,
            port=parsed.port or 3306,
            database=parsed.path.lstrip("/"),
            charset="utf8mb4",
            autocommit=False,
        )
    else:
        import sqlite3

        caminho_banco = getattr(config, "DATABASE_PATH", "promocoes.db")
        diretorio = os.path.dirname(caminho_banco)
        if diretorio:
            os.makedirs(diretorio, exist_ok=True)
        return sqlite3.connect(caminho_banco)


def inicializar_banco() -> None:
    """Cria a tabela de promoções enviadas se ainda não existir."""
    is_mysql = DATABASE_URL and ("mysql" in DATABASE_URL.lower())

    if is_mysql:
        ddl = """
        CREATE TABLE IF NOT EXISTS promocoes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            produto_id VARCHAR(50) NOT NULL UNIQUE,
            titulo VARCHAR(500),
            categoria VARCHAR(100),
            preco_atual DECIMAL(10, 2),
            preco_anterior DECIMAL(10, 2),
            desconto DECIMAL(5, 2),
            url_produto TEXT,
            url_afiliado TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
    else:
        ddl = """
        CREATE TABLE IF NOT EXISTS promocoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id TEXT UNIQUE NOT NULL,
            titulo TEXT,
            categoria TEXT,
            preco_atual REAL,
            preco_anterior REAL,
            desconto REAL,
            url_produto TEXT,
            url_afiliado TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()


def extrair_produto_id(url: str) -> Optional[str]:
    """Extrai o ID canônico do Mercado Livre a partir da URL."""
    if not url:
        return None
    match = re.search(r"(MLB[U]?\d+)", url)
    return match.group(1) if match else None


def produto_ja_publicado(produto_id: str) -> bool:
    """Verifica se o ID já foi salvo anteriormente."""
    query = "SELECT 1 FROM promocoes WHERE produto_id = %s LIMIT 1;" if (DATABASE_URL and "mysql" in DATABASE_URL.lower()) else "SELECT 1 FROM promocoes WHERE produto_id = ? LIMIT 1;"

    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (produto_id,))
            resultado = cur.fetchone()
            return resultado is not None


def salvar_promocao(promo: dict) -> None:
    """Persiste a promoção aprovada garantindo integridade de duplicados."""
    is_mysql = DATABASE_URL and ("mysql" in DATABASE_URL.lower())

    if is_mysql:
        sql = """
        INSERT IGNORE INTO promocoes (
            produto_id, titulo, categoria, preco_atual, preco_anterior, desconto, url_produto, url_afiliado
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """
    else:
        sql = """
        INSERT OR IGNORE INTO promocoes (
            produto_id, titulo, categoria, preco_atual, preco_anterior, desconto, url_produto, url_afiliado
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """

    valores = (
        promo.get("produto_id"),
        (promo.get("titulo") or "")[:500],
        promo.get("categoria"),
        promo.get("preco_atual"),
        promo.get("preco_anterior"),
        promo.get("desconto"),
        promo.get("url_produto"),
        promo.get("url_afiliado"),
    )

    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, valores)
        conn.commit()