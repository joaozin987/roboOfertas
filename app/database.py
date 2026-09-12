"""
Camada de banco de dados (SQLite) — Fase 2.

Responsável por registrar promoções já publicadas, para que o bot
nunca publique a mesma oferta duas vezes.
"""

import hashlib
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

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
    Extrai o identificador único do produto da URL do Mercado Livre.
    Cobre catálogo (/p/), anúncios padrão (/MLB-), parâmetros wid e redirects.
    Se nenhum padrão de MLB for encontrado, gera um hash único da URL base.
    """
    if not url_produto:
        return None

    url_decodificada = unquote(url_produto)

    # 1. Anúncio de catálogo: /p/MLB12345678
    encontrado = re.search(r"/p/(MLB\d+)", url_decodificada, re.IGNORECASE)
    if encontrado:
        return encontrado.group(1).upper()

    # 2. Produto padrão: /MLB-1234567890 ou /MLB1234567890
    encontrado = re.search(r"/(MLB-?\d{6,14})", url_decodificada, re.IGNORECASE)
    if encontrado:
        return encontrado.group(1).replace("-", "").upper()

    # 3. Parâmetro wid: wid=MLB12345678
    encontrado = re.search(r"[?&]wid=(MLB\d+)", url_decodificada, re.IGNORECASE)
    if encontrado:
        return encontrado.group(1).upper()

    # 4. URL /up/MLBU...
    encontrado = re.search(r"/up/(MLBU\d+)", url_decodificada, re.IGNORECASE)
    if encontrado:
        return encontrado.group(1).upper()

    # 5. Qualquer menção explícita a MLB seguida de números (ex: tracking links)
    encontrado = re.search(r"(MLB-?\d{8,14})", url_decodificada, re.IGNORECASE)
    if encontrado:
        return encontrado.group(1).replace("-", "").upper()

    # 6. Fallback final: se a URL for atípica, usa hash da URL sem parâmetros
    url_base = url_decodificada.split("?")[0].rstrip("/")
    if url_base:
        return "HASH_" + hashlib.sha256(url_base.encode("utf-8")).hexdigest()[:16].upper()

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
    # Usa o produto_id já injetado no dict ou extrai da URL
    produto_id = promocao.get("produto_id") or extrair_produto_id(promocao.get("url_produto", ""))
    
    if not produto_id:
        logger.warning(
            "Não foi possível obter identificador de '%s' — produto não será gravado.",
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
            conexao.commit()
        except sqlite3.IntegrityError:
            logger.info("Produto %s já estava salvo no banco.", produto_id)