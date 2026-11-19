"""Fonte experimental de ofertas via busca autenticada do Mercado Livre."""

import logging
import math
import os
import time
from urllib.parse import urlsplit

import requests

from app import mercado_livre
from app.mercado_livre_api import MercadoLivreAPI

logger = logging.getLogger(__name__)
_CATEGORIAS = {"Smartphones & Celulares": "MLB1051", "Moda & Calçados": "MLB1430"}
_proxima_tentativa = {}
_cliente = None


def buscar_ofertas(url_categoria):
    global _cliente
    if os.getenv("ML_USAR_API", "").strip().lower() != "true":
        return []
    nicho = next((n["nome"] for n in mercado_livre.NICHOS_ESTRATEGICOS if n["url"] == url_categoria), None)
    categoria = _CATEGORIAS.get(nicho)
    if not categoria or time.monotonic() < _proxima_tentativa.get(categoria, 0):
        return []

    try:
        if _cliente is None:
            _cliente = MercadoLivreAPI(
                os.environ["ML_CLIENT_ID"], os.environ["ML_CLIENT_SECRET"],
                os.environ["ML_REDIRECT_URI"],
            )
        resposta = requests.get(
            "https://api.mercadolibre.com/sites/MLB/search",
            params={"category": categoria, "limit": 50},
            headers={"Authorization": f"Bearer {_cliente.get_token_valido()}"},
            timeout=(5, 15),
            allow_redirects=False,
        )
        if resposta.status_code != 200:
            _proxima_tentativa[categoria] = time.monotonic() + 900
            logger.warning("Busca API Mercado Livre [%s]: HTTP %d.", categoria, resposta.status_code)
            return []
        itens = resposta.json()["results"]
        if not isinstance(itens, list):
            raise ValueError("Formato inválido")
    except (OSError, KeyError, TypeError, ValueError) as erro:
        _proxima_tentativa[categoria] = time.monotonic() + 900
        logger.warning("Busca API Mercado Livre [%s] indisponível (%s).", categoria, type(erro).__name__)
        return []

    _proxima_tentativa[categoria] = time.monotonic() + 300
    ofertas = [oferta for item in itens if (oferta := _oferta(item, nicho))]
    logger.info("Busca API Mercado Livre [%s]: %d ofertas com preço original.", categoria, len(ofertas))
    return ofertas


def _oferta(item, nicho):
    try:
        atual, anterior = float(item["price"]), float(item["original_price"])
        link = item["permalink"]
        destino = urlsplit(link)
        titulo = item["title"].strip()
        produto_id = item["id"]
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    if (
        item.get("currency_id") != "BRL" or not titulo or not produto_id
        or not math.isfinite(anterior) or not 0 < atual < anterior
        or destino.scheme != "https"
        or destino.hostname not in {"www.mercadolivre.com.br", "produto.mercadolivre.com.br"}
    ):
        return None
    return {
        "origem": "mercado_livre",
        "produto_id": produto_id,
        "titulo": titulo,
        "categoria": nicho,
        "preco_atual": atual,
        "preco_anterior": anterior,
        "desconto": mercado_livre.calcular_desconto(atual, anterior),
        "url_produto": link,
        "imagem": item.get("thumbnail"),
    }
