"""
Camada de comunicação com o Mercado Livre.
Coleta produtos e ofertas via API REST oficial e rotação de categorias.
"""

import logging
import re
import time
from typing import Optional, List, Dict
from urllib.parse import urlparse, parse_qs, urlunparse

from curl_cffi import requests

from app import config
from app.afiliados import gerar_link_afiliado

logger = logging.getLogger(__name__)

_session = requests.Session(impersonate="chrome124")

# Nichos estratégicos configurados por termo de busca ou ID de categoria
NICHOS_ESTRATEGICOS = [
    {
        "nome": "Aura Beauty",
        "tipo": "busca",
        "termo": "aura beauty",
    },
    {
        "nome": "Roupas leves e esportivas",
        "tipo": "busca",
        "termo": "camisa corrida unissex secagem rapida",
    },
    {
        "nome": "Smartphones & Celulares",
        "tipo": "categoria",
        "categoria_id": "MLB1051",
    },
    {
        "nome": "Moda & Calçados",
        "tipo": "categoria",
        "categoria_id": "MLB1430",
    },
    {
        "nome": "Corrida & Esportes",
        "tipo": "categoria",
        "categoria_id": "MLB1276",
    },
    {
        "nome": "Estética Automotiva",
        "tipo": "categoria",
        "categoria_id": "MLB1747",
    },
    {
        "nome": "Informática & Games",
        "tipo": "categoria",
        "categoria_id": "MLB1648",
    },
    {
        "nome": "Casa & Eletrodomésticos",
        "tipo": "categoria",
        "categoria_id": "MLB1574",
    },
    {
        "nome": "Ferramentas & Construção",
        "tipo": "categoria",
        "categoria_id": "MLB1500",
    },
    {
        "nome": "Beleza & Cuidados",
        "tipo": "categoria",
        "categoria_id": "MLB1246",
    },
]


def calcular_desconto(preco_atual: float, preco_anterior: float) -> Optional[float]:
    if not preco_anterior or preco_anterior <= preco_atual:
        return None
    desconto = ((preco_anterior - preco_atual) / preco_anterior) * 100
    return round(desconto, 1)


def limpar_url_produto(url: str) -> str:
    if not url:
        return url
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def montar_link_afiliado(url_produto: str) -> str:
    if not url_produto:
        return url_produto
    url_limpa = limpar_url_produto(url_produto)
    link_oficial = gerar_link_afiliado(url_limpa)
    return link_oficial or url_produto


def _consultar_api_ml(params: dict) -> Optional[dict]:
    """Consulta a API aberta de busca do Mercado Livre Brasil (MLB)."""
    url_api = "https://api.mercadolibre.com/sites/MLB/search"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    try:
        resp = _session.get(url_api, params=params, headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        logger.error("API ML retornou status %d: %s", resp.status_code, resp.text[:200])
        return None
    except Exception as e:
        logger.error("Erro ao chamar API do ML: %s", e)
        return None


def _formatar_item_api(item: dict, categoria_nome: str) -> Optional[dict]:
    titulo = item.get("title")
    permalink = item.get("permalink")
    preco_atual = item.get("price")
    preco_anterior = item.get("original_price")
    thumbnail = item.get("thumbnail", "").replace("-I.jpg", "-O.jpg")

    if not titulo or not permalink or preco_atual is None:
        return None

    # Trava de pertinência para Aura Beauty
    if categoria_nome == "Aura Beauty" and "aura" not in titulo.lower():
        return None

    desconto = calcular_desconto(preco_atual, preco_anterior) if preco_anterior else None

    return {
        "titulo": titulo,
        "categoria": categoria_nome,
        "preco_atual": float(preco_atual),
        "preco_anterior": float(preco_anterior) if preco_anterior else None,
        "desconto": desconto,
        "imagem": thumbnail,
        "url_produto": permalink,
        "url_afiliado": montar_link_afiliado(permalink),
        "cupom": getattr(config, "CUPOM_DESCONTO", None),
    }


def buscar_ofertas(
    url_categoria: Optional[str] = None, max_paginas: Optional[int] = None
) -> List[Dict]:
    max_paginas = max_paginas or getattr(config, "SCRAPER_MAX_PAGINAS", 1)
    promocoes: List[Dict] = []

    # Identifica o nicho atual ou usa padrão
    nicho_atual = None
    if url_categoria:
        for n in NICHOS_ESTRATEGICOS:
            if n.get("url") == url_categoria or n.get("termo") in url_categoria:
                nicho_atual = n
                break

    if not nicho_atual:
        nicho_atual = NICHOS_ESTRATEGICOS[0]

    categoria_nome = nicho_atual["nome"]
    logger.info("Buscando produtos via API para [%s]...", categoria_nome)

    limite_por_pagina = 48

    for pagina in range(1, max_paginas + 1):
        offset = (pagina - 1) * limite_por_pagina
        params = {
            "limit": limite_por_pagina,
            "offset": offset,
        }

        if nicho_atual.get("tipo") == "categoria":
            params["category"] = nicho_atual["categoria_id"]
        else:
            params["q"] = nicho_atual["termo"]

        dados = _consultar_api_ml(params)
        if not dados:
            break

        resultados = dados.get("results", [])
        if not resultados:
            logger.warning("Nenhum item retornado pela API para [%s]", categoria_nome)
            break

        for item in resultados:
            prod = _formatar_item_api(item, categoria_nome)
            if prod:
                promocoes.append(prod)

        if pagina < max_paginas:
            time.sleep(getattr(config, "SCRAPER_REQUEST_DELAY_SECONDS", 2))

    logger.info("%d produtos encontrados para [%s]", len(promocoes), categoria_nome)
    return promocoes