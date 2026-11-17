"""Consulta a Open API Shopee ou lê o arquivo legado de ofertas."""

import hashlib
import json
import logging
import math
import os
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote, urlparse, urlunparse

import requests

from app import config

logger = logging.getLogger(__name__)

IMG_BASE = "https://down-br.img.susercontent.com/file/"
API_URL = "https://open-api.affiliate.shopee.com.br/graphql"
API_REFRESH_SECONDS = 15 * 60
API_RETRY_SECONDS = 60
API_CACHE_MAX_SECONDS = 60 * 60
_api_offers = []
_api_fetched_at = None
_api_next_fetch = 0.0

# Nichos para classificação automática baseada no título do produto
NICHO_KEYWORDS = {
    "Perfumes & Fragrâncias": ["perfume", "colônia", "colonia", "eau de", "fragrancia", "fragrância", "body splash", "lattafa", "deo"],
    "Fitness & Suplementos": ["creatina", "whey", "suplemento", "pre-treino", "pré-treino", "bcaa", "malas de academia", "garrafa", "termogenico"],
    "Malas & Viagem": ["mala de bordo", "mala de viagem", "mochila", "necessaire", "cadeado", "frasqueira"],
    "Moda & Vestuário": ["camisa", "camiseta", "bermuda", "calça", "vestido", "short", "jaqueta", "blusa", "casaco", "conjunto"],
    "Tecnologia & Gadgets": ["fone", "bluetooth", "carregador", "smartwatch", "cabo", "suporte", "mouse", "teclado", "power bank"],
}


def _caminho_arquivo() -> Path:
    caminho = Path(getattr(config, "SHOPEE_JSON_PATH", "data/shopee_oferta.json"))
    if not caminho.is_absolute():
        caminho = Path(__file__).resolve().parent.parent / caminho
    return caminho


ARQUIVO = _caminho_arquivo()


def _preco(valor) -> Optional[float]:
    """Normaliza o preço vindo da API da Shopee para Reais reais."""
    try:
        if not valor:
            return None
        num = int(valor)
        # Se vier no formato interno cheio de zeros da Shopee (ex: 799000 ou 1990000)
        if num > 10000:
            return round(num / 100000, 2)
        return round(float(num), 2)
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
    titulo_lower = titulo.lower()
    for categoria, palavras in NICHO_KEYWORDS.items():
        if any(palavra in titulo_lower for palavra in palavras):
            return categoria
    return "Achados Shopee"


def _arquivo_desatualizado() -> bool:
    limite_h = getattr(config, "SHOPEE_MAX_IDADE_HORAS", 72)
    if not limite_h:
        return False
    if not ARQUIVO.exists():
        return False
    idade_h = (time.time() - ARQUIVO.stat().st_mtime) / 3600
    if idade_h > limite_h:
        logger.error(
            "Shopee: %s foi atualizado há %.0f h (limite %d h).",
            ARQUIVO.name, idade_h, limite_h,
        )
        return True
    return False


def _ler_itens() -> List[dict]:
    if not ARQUIVO.exists():
        logger.error("Arquivo %s não encontrado.", ARQUIVO)
        return []
    if _arquivo_desatualizado():
        return []

    texto = ARQUIVO.read_text(encoding="utf-8-sig").strip()
    
    # Blindagem: se o conteúdo começar com HTML, avisa claramente em vez de quebrar
    if texto.startswith("<!DOCTYPE") or texto.startswith("<html"):
        logger.error("Shopee: O arquivo %s contém código HTML (página web), mas é esperado o JSON da API de afiliados.", ARQUIVO.name)
        return []

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

    # CORREÇÃO: Força a montagem dinâmica do link de afiliado limpo para evitar links longos expirados
    url_produto = item.get("product_link") or f"https://shopee.com.br/product/{shop_id}/{item_id}"
    url_afiliado = montar_link_afiliado(url_produto) or item.get("long_link")
    
    if not url_afiliado:
        return None
        
    img = info.get("image")
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
        "cupom": getattr(config, "SHOPEE_CUPOM", None),
    }


def _consultar_api(app_id: str, secret: str) -> list:
    ofertas = []
    for pagina in range(1, 4):
        consulta = f"""{{ productOfferV2(page: {pagina}, limit: 20, listType: 2) {{
            nodes {{ itemId shopId productName priceMin priceDiscountRate imageUrl
                     productLink offerLink periodStartTime periodEndTime }}
            pageInfo {{ hasNextPage }}
        }} }}"""
        corpo = json.dumps({"query": consulta}, separators=(",", ":"))
        timestamp = str(int(time.time()))
        assinatura = hashlib.sha256(f"{app_id}{timestamp}{corpo}{secret}".encode()).hexdigest()
        resposta = requests.post(
            API_URL,
            data=corpo.encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"SHA256 Credential={app_id}, Timestamp={timestamp}, Signature={assinatura}",
            },
            timeout=(5, 15),
            allow_redirects=False,
        )
        if resposta.status_code != 200:
            resposta.raise_for_status()
            raise ValueError("status inesperado")
        dados = resposta.json()
        if dados.get("errors"):
            raise ValueError("consulta GraphQL rejeitada")
        pagina_ofertas = dados["data"]["productOfferV2"]
        ofertas.extend(pagina_ofertas["nodes"])
        if not pagina_ofertas["pageInfo"]["hasNextPage"]:
            break
    return ofertas


def _oferta_da_api(item: dict, min_desc: float, preco_max: float, agora: float) -> Optional[dict]:
    try:
        titulo = item["productName"].strip()
        atual = float(item["priceMin"])
        desconto = float(item["priceDiscountRate"])
        inicio = int(item.get("periodStartTime") or 0)
        fim = int(item.get("periodEndTime") or 0)
        shop_id = int(item["shopId"])
        item_id = int(item["itemId"])
        url_produto = item["productLink"]
        url_afiliado = item["offerLink"]
        if not isinstance(url_produto, str) or not isinstance(url_afiliado, str):
            return None
        urls = [urlparse(url) for url in (url_produto, url_afiliado)]
    except (KeyError, AttributeError, TypeError, ValueError):
        return None

    if (
        not titulo or shop_id <= 0 or item_id <= 0
        or not math.isfinite(atual) or not 0 < atual <= preco_max
        or not math.isfinite(desconto) or not min_desc <= desconto <= 100
        or (inicio and inicio > agora) or (fim and fim <= agora)
        or any(
            url.scheme != "https"
            or not (url.hostname == "shopee.com.br" or (url.hostname or "").endswith(".shopee.com.br"))
            for url in urls
        )
    ):
        return None

    return {
        "produto_id": f"shopee_{shop_id}_{item_id}",
        "origem": "shopee",
        "titulo": titulo,
        "categoria": _classificar_categoria(titulo),
        "preco_atual": atual,
        "preco_anterior": None,
        "desconto": desconto,
        "imagem": item.get("imageUrl"),
        "url_produto": url_produto,
        "url_afiliado": url_afiliado,
        "cupom": None,
    }


def _buscar_ofertas_api(app_id: str, secret: str, min_desc: float, preco_max: float) -> List[Dict]:
    global _api_offers, _api_fetched_at, _api_next_fetch
    if time.monotonic() >= _api_next_fetch:
        try:
            _api_offers = _consultar_api(app_id, secret)
        except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as erro:
            _api_next_fetch = time.monotonic() + API_RETRY_SECONDS
            status = erro.response.status_code if isinstance(erro, requests.HTTPError) else None
            logger.warning("Shopee Open API: falha ao atualizar ofertas (%s).", status or type(erro).__name__)
        else:
            _api_fetched_at = time.monotonic()
            _api_next_fetch = _api_fetched_at + API_REFRESH_SECONDS
            logger.info("Shopee Open API: %d ofertas recebidas.", len(_api_offers))

    if _api_fetched_at is None or time.monotonic() - _api_fetched_at >= API_CACHE_MAX_SECONDS:
        return []
    agora = time.time()
    validas = {}
    for item in _api_offers:
        oferta = _oferta_da_api(item, min_desc, preco_max, agora)
        if oferta:
            validas[oferta["produto_id"]] = oferta
    return sorted(validas.values(), key=lambda oferta: oferta["desconto"], reverse=True)


def buscar_ofertas(
    url_categoria: Optional[str] = None, max_paginas: Optional[int] = None
) -> List[Dict]:
    min_desc = float(getattr(config, "SHOPEE_MIN_DESCONTO", 20.0))
    preco_max = float(getattr(config, "SHOPEE_PRECO_MAXIMO", 50000.0))

    app_id = os.getenv("SHOPEE_API_APP_ID", "").strip()
    secret = os.getenv("SHOPEE_API_SECRET", "").strip()
    if app_id and secret:
        return _buscar_ofertas_api(app_id, secret, min_desc, preco_max)

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
