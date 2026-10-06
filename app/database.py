"""
Camada de persistência de dados.
Compatível com MySQL (Railway) e SQLite (desenvolvimento local).
"""

import logging
import os
import re
from typing import Iterable, Optional, Set
from urllib.parse import unquote, urlparse

from app import config

logger = logging.getLogger(__name__)

_inicializado = False

# Marketplace + pelo menos 7 dígitos: evita confundir com IDs de categoria/promoção (MLB1430, etc.)
_ID_RE = re.compile(r"(MLBU?)-?(\d{7,})")


def _obter_database_url() -> Optional[str]:
    return (
        os.getenv("MYSQL_URL")
        or os.getenv("MYSQLURL")
        or os.getenv("DATABASE_URL")
        or getattr(config, "MYSQL_URL", None)
        or getattr(config, "DATABASE_URL", None)
    )


def _is_mysql() -> bool:
    url = _obter_database_url()
    return bool(url) and urlparse(url).scheme.lower().startswith("mysql")


def _placeholder() -> str:
    return "%s" if _is_mysql() else "?"


def _abrir_conexao():
    if _is_mysql():
        import pymysql

        p = urlparse(_obter_database_url())
        return pymysql.connect(
            host=p.hostname,
            user=unquote(p.username or ""),
            password=unquote(p.password or ""),
            port=p.port or 3306,
            database=p.path.lstrip("/"),
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=10,
            read_timeout=20,
            write_timeout=20,
        )

    import sqlite3

    caminho = getattr(config, "DATABASE_PATH", "promocoes.db")
    diretorio = os.path.dirname(caminho)
    if diretorio:
        os.makedirs(diretorio, exist_ok=True)
    return sqlite3.connect(caminho)


def _executar(sql: str, params: tuple = (), fetch: Optional[str] = None):
    """Abre conexão, executa, devolve resultado e sempre fecha tudo."""
    conn = _abrir_conexao()
    try:
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
            resultado = None
            if fetch == "one":
                resultado = cur.fetchone()
            elif fetch == "all":
                resultado = cur.fetchall()
            conn.commit()
            return resultado
        finally:
            cur.close()
    finally:
        conn.close()


def inicializar_banco() -> None:
    """Cria a tabela se não existir. Idempotente: só executa uma vez por processo."""
    global _inicializado
    if _inicializado:
        return

    if _is_mysql():
        logger.info("Banco de dados: [MySQL (Produção)]")
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
        if any(k.startswith("RAILWAY_") for k in os.environ):
            raise RuntimeError(
                "Rodando na Railway sem MYSQL_URL/DATABASE_URL válida. "
                "SQLite seria apagado a cada deploy e o bot repostaria ofertas antigas."
            )
        logger.warning("Banco de dados: [SQLite (fallback local)]. Nenhuma URL MySQL encontrada.")
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

    _executar(ddl)
    _inicializado = True


def extrair_produto_id(url: str) -> Optional[str]:
    """ID canônico do Mercado Livre (ex.: MLB29873777). Prioriza o caminho da URL."""
    if not url:
        return None
    caminho = unquote(urlparse(url).path)
    for trecho in (caminho, unquote(url)):
        m = _ID_RE.search(trecho)
        if m:
            return f"{m.group(1)}{m.group(2)}"
    return None


def ids_ja_publicados(ids: Iterable[str]) -> Set[str]:
    """Consulta em lote: devolve o subconjunto de `ids` que já está no banco."""
    unicos = list({str(i) for i in ids if i})
    encontrados: Set[str] = set()
    if not unicos:
        return encontrados
    ph = _placeholder()
    for i in range(0, len(unicos), 500):  # abaixo do limite de variáveis do SQLite
        lote = unicos[i : i + 500]
        marcadores = ",".join([ph] * len(lote))
        linhas = _executar(
            f"SELECT produto_id FROM promocoes WHERE produto_id IN ({marcadores});",
            tuple(lote),
            fetch="all",
        )
        encontrados.update(str(l[0]) for l in linhas)
    return encontrados


def produto_ja_publicado(produto_id: str) -> bool:
    return bool(ids_ja_publicados([produto_id]))


def salvar_promocao(promo: dict) -> None:
    """Persiste a promoção; duplicata é ignorada sem engolir outros erros."""
    if _is_mysql():
        sql = """
        INSERT INTO promocoes (
            produto_id, titulo, categoria, preco_atual, preco_anterior, desconto, url_produto, url_afiliado
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE produto_id = produto_id;
        """
    else:
        sql = """
        INSERT OR IGNORE INTO promocoes (
            produto_id, titulo, categoria, preco_atual, preco_anterior, desconto, url_produto, url_afiliado
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """

    _executar(
        sql,
        (
            promo.get("produto_id"),
            (promo.get("titulo") or "")[:500],
            (promo.get("categoria") or "")[:100],
            promo.get("preco_atual"),
            promo.get("preco_anterior"),
            promo.get("desconto"),
            promo.get("url_produto"),
            promo.get("url_afiliado"),
        ),
    )