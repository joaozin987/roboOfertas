"""
Camada de banco de dados (SQLite) — Fase 2.

Responsável por registrar promoções já publicadas, para que o bot
nunca publique a mesma oferta duas vezes.
"""

import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from app import config

logger = logging.getLogger(__name__)

_CRIAR_TABELA = """
CREATE TABLE IF NOT EXISTS promocoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_id TEXT UNIQUE NOT NULL,
    titulo TEXT NOT NULL,
    preco_atual REAL,
    preco_anterior REAL,
    desconto REAL,
    url_afiliado TEXT,
    cupom TEXT,
    enviado_em TEXT NOT NULL
);
"""


def _get_connection() -> sqlite3.Connection:
    caminho = Path(config.DATABASE_PATH)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(caminho)


def inicializar_banco() -> None:
    """Cria a tabela `promocoes`, se ainda não existir."""
    with _get_connection() as conexao:
        conexao.execute(_CRIAR_TABELA)


def extrair_produto_id(url_produto: str) -> Optional[str]:
    """
    Extrai o identificador do produto (ex.: 'MLB65588451') a partir da
    URL do Mercado Livre. Usado como chave única para evitar duplicidade.
    """
    if not url_produto:
        return None
    encontrado = re.search(r"(MLB-?\d+)", url_produto, re.IGNORECASE)
    if encontrado:
        return encontrado.group(1).upper().replace("-", "")
    return None


def produto_ja_publicado(produto_id: Optional[str]) -> bool:
    """Verifica se um produto (pelo produto_id) já foi publicado antes."""
    if not produto_id:
        return False

    with _get_connection() as conexao:
        resultado = conexao.execute(
            "SELECT 1 FROM promocoes WHERE produto_id = ? LIMIT 1", (produto_id,)
        ).fetchone()
        return resultado is not None


def salvar_promocao(promocao: dict) -> None:
    """Registra a promoção publicada no banco, para não repetir depois."""
    produto_id = extrair_produto_id(promocao.get("url_produto", ""))
    if not produto_id:
        logger.warning(
            "Não foi possível extrair produto_id de '%s' — promoção não será "
            "registrada no banco (pode ser publicada de novo no futuro).",
            promocao.get("url_produto"),
        )
        return

    with _get_connection() as conexao:
        try:
            conexao.execute(
                """
                INSERT INTO promocoes (
                    produto_id, titulo, preco_atual, preco_anterior,
                    desconto, url_afiliado, cupom, enviado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    produto_id,
                    promocao.get("titulo"),
                    promocao.get("preco_atual"),
                    promocao.get("preco_anterior"),
                    promocao.get("desconto"),
                    promocao.get("url_afiliado"),
                    promocao.get("cupom"),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
        except sqlite3.IntegrityError:
            # Corrida rara: já foi salvo entre a checagem e o insert.
            logger.info("Produto %s já estava salvo no banco.", produto_id)