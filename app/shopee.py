"""
Shopee: lê as ofertas copiadas do painel de afiliados (resposta da chamada
"offer/product/list") de um arquivo e entrega prontas para o bot.
O link de afiliado (long_link) já vem pronto da própria Shopee.

Arquivo lido: data/shopee_oferta.json (pode ter várias respostas coladas em sequência)
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote, urlparse, urlunparse

from app import config

logger = logging.getLogger(__name__)

IMG_BASE = "https://down-br.img.susercontent.com/file/"

# Nichos para classificação automática baseada no título do produto
NICHO_KEYWORDS = {
    "Perfumes & Fragrâncias": ["perfume", "colônia", "colonia", "eau de", "fragrancia", "fragrância", "body splash", "lattafa", "deo"],
    "Fitness & Suplementos": ["creatina", "whey", "suplemento", "pre-treino", "pré-treino", "bcaa", "malas de academia", "garrafa", "termogenico"],
    "Malas & Viagem": ["mala de bordo", "mala de viagem", "mochila", "necessaire", "necessaire", "cadeado", "frasqueira"],
    "Moda & Vestuário": ["camisa", "camiseta", "bermuda", "calça", "vestido", "short", "jaqueta", "blusa", "casaco", "conjunto"],
    "Tecnologia & Gadgets": ["fone", "bluetooth", "carregador", "smartwatch", "cabo", "suporte", "mouse", "teclado", "power bank"],
}


def _caminho_arquivo() -> Path:
    """Caminho relativo é resolvido a partir da raiz do projeto, não da pasta onde o bot foi iniciado."""
    caminho = Path(getattr(config, "SHOPEE_JSON_PATH", "data/shopee_oferta.json"))
    if not caminho.is_absolute():
        caminho = Path(__file__).resolve().parent.parent / caminho
    return caminho


ARQUIVO = _caminho_arquivo()


def _preco(valor) -> Optional[float]:
    try:
        return round(int(valor) / 100000, 2)
    except (TypeError, ValueError):
        return None


def calcular_desconto(preco_atual: float, preco_anterior: float) -> Optional[float]:
    if not preco_anterior or preco_anterior <= 0:
        return None
    return round(((preco_anterior - preco_atual) / preco_anterior) * 100, 1)


def limpar_url_produto(url: str) -> str:
    if not url:
        return url
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))


def montar_link_afiliado(url_produto: str) -> Optional[str]:
    """Reserva, usada só se a resposta vier sem long_link. Sem IDs de afiliado => None."""
    affiliate_id = getattr(config, "SHOPEE_AFFILIATE_ID", "")
    sub_id = getattr(config, "SHOPEE_USER_ID", "")
    if not affiliate_id or not url_produto:
        return None
    url_limpa = limpar_url_produto(url_produto)
    link = (
        "https://s.shopee.com.br/an_redir"
        f"?origin_link={quote(url_limpa, safe='')}"
        f"&affiliate_id={affiliate_id}"
    )
    if sub_id:
        link += f"&sub_id={sub_id}"
    return link


def _classificar_categoria(titulo: str) -> str:
    """Identifica o nicho estrategicamente com base no título do produto."""
    titulo_lower = titulo.lower()
    for categoria, palavras in NICHO_KEYWORDS.items():
        if any(palavra in titulo_lower for palavra in palavras):
            return categoria
    return "Achados Shopee"


def _arquivo_desatualizado() -> bool:
    """True se o arquivo está mais velho que SHOPEE_MAX_IDADE_HORAS (0 desliga a checagem)."""
    limite_h = getattr(config, "SHOPEE_MAX_IDADE_HORAS", 72)
    if not limite_h:
        return False
    idade_h = (time.time() - ARQUIVO.stat().st_mtime) / 3600
    if idade_h > limite_h:
        logger.error(
            "Shopee: %s foi atualizado há %.0f h (limite %d h). Cole respostas novas do painel; "
            "oferta antiga pode estar expirada. Shopee ignorada neste ciclo.",
            ARQUIVO.name, idade_h, limite_h,
        )
        return True
    return False


def _ler_itens() -> List[dict]:
    if not ARQUIVO.exists():
        logger.error("Arquivo %s não encontrado. Cole ali as respostas do painel.", ARQUIVO)
        return []
    if _arquivo_desatualizado():
        return []

    texto = ARQUIVO.read_text(encoding="utf-8-sig")
    decoder = json.JSONDecoder()
    itens: List[dict] = []
    i, n = 0, len(texto)

    while i < n:
        while i < n and texto[i].isspace():
            i += 1
        if i >= n:
            break
        try:
            obj, fim = decoder.raw_decode(texto, i)
        except ValueError as erro:
            logger.error("JSON inválido em %s perto do caractere %d: %s", ARQUIVO, i, erro)
            break
        i = fim
        if isinstance(obj, dict):
            itens.extend((obj.get("data") or {}).get("list") or [])

    return itens


def _extrair_promocao(item: dict, min_desc: float, preco_max: float) -> Optional[dict]:
    info = item.get("batch_item_for_item_card_full") or {}
    titulo = (info.get("name") or "").strip()
    item_id = str(item.get("item_id") or info.get("itemid") or "")
    shop_id = str(info.get("shopid") or "")
    if not titulo or not item_id or not shop_id:
        return None

    atual = _preco(info.get("price_min") or info.get("price"))
    antes = _preco(info.get("price_min_before_discount") or info.get("price_before_discount"))
    if atual is None:
        return None
    if antes is not None and antes <= atual:
        antes = None

    try:
        desconto = float(info.get("raw_discount") or 0)
    except (TypeError, ValueError):
        desconto = 0.0
    if not desconto and antes:
        desconto = calcular_desconto(atual, antes) or 0.0

    if desconto < min_desc or atual > preco_max:
        return None

    url_produto = item.get("product_link") or f"https://shopee.com.br/product/{shop_id}/{item_id}"
    url_afiliado = item.get("long_link") or montar_link_afiliado(url_produto)
    if not url_afiliado:
        logger.warning("Shopee: item %s sem long_link e sem IDs de afiliado; ignorado.", item_id)
        return None
    img = info.get("image")

    # Classifica dinamicamente a categoria com base no título
    categoria = _classificar_categoria(titulo)

    return {
        "produto_id": f"shopee_{shop_id}_{item_id}",
        "origem": "shopee",
        "titulo": titulo,
        "categoria": categoria,
        "preco_atual": atual,
        "preco_anterior": antes,
        "desconto": desconto,
        "imagem": f"{IMG_BASE}{img}" if img else None,
        "url_produto": url_produto,
        "url_afiliado": url_afiliado,
        # Cupom próprio da Shopee: nunca reaproveita o cupom do Mercado Livre
        "cupom": getattr(config, "SHOPEE_CUPOM", None),
    }


def buscar_ofertas(
    url_categoria: Optional[str] = None, max_paginas: Optional[int] = None
) -> List[Dict]:
    # Reduzido para 20.0 por padrão para flexibilizar as capturas de novos nichos
    min_desc = float(getattr(config, "SHOPEE_SHOPEE_MIN_DESCONTO", getattr(config, "SHOPEE_MIN_DESCONTO", 20.0)))
    preco_max = float(getattr(config, "SHOPEE_PRECO_MAXIMO", 900.0))

    itens = _ler_itens()
    logger.info("Shopee: %d itens lidos de %s", len(itens), ARQUIVO)

    vistos = set()
    promocoes: List[Dict] = []
    for item in itens:
        promo = _extrair_promocao(item, min_desc, preco_max)
        if promo and promo["produto_id"] not in vistos:
            vistos.add(promo["produto_id"])
            promocoes.append(promo)

    promocoes.sort(key=lambda p: p.get("desconto") or 0, reverse=True)
    logger.info("%d produtos válidos na Shopee (desconto >= %.0f%%)", len(promocoes), min_desc)
    return promocoes