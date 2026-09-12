"""
Camada de comunicação com o Mercado Livre.
Faz o scraping da página pública de ofertas com rotação por categorias oficiais.
"""

import logging
import re
import time
from typing import Optional, List, Dict
from urllib.parse import urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from app import config
from app.afiliados import gerar_link_afiliado

logger = logging.getLogger(__name__)

# Categorias oficiais do Mercado Livre Ofertas que usam o layout estável
# Categorias oficiais do Mercado Livre Ofertas com rotação balanceada
NICHOS_ESTRATEGICOS = [
    {
        "nome": "Smartphones & Celulares",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1051#deal_ids=MLB1051",
    },
    {
        "nome": "Moda & Calçados",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1430",
    },
    {
        "nome": "corrida e esportes",
        "url": "https://lista.mercadolivre.com.br/corrida#D[A:corrida]"
    },
    {
        "nome": "Estetica Automotiva",
        "url": "https://lista.mercadolivre.com.br/estetica-automotiva#D[A:Estetica%20automotiva]"
    },
    {
        "nome": "Itens para Setup",
        "url": "https://lista.mercadolivre.com.br/monitores-teclados#D[A:monitores%20teclados]"
    },
    {
        "nome": "Roupas para praticar Esportes",
        "url": "https://lista.mercadolivre.com.br/roupas-academia?sb=all_mercadolibre#D[A:roupas%20academia]"
    },
    {
        "nome": "Casa & Eletrodomésticos",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1574",
    },
    {
        "nome": "Esportes & Suplementos",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1276",
    },
    {
        "nome": "Informática & Games",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1648",
    },
    {
        "nome": "Ferramentas & Construção",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1500",
    },
    {
        "nome": "Beleza & Cuidados",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1246",
    },
    {
        "nome": " Banheiro",
        "url" : "https://lista.mercadolivre.com.br/banheiro?sb=all_mercadolibre#D[A:banheiro]"
    },
]

_SELETORES = {
    "card": [
        "div.andes-card.poly-card",
        "li.promotion-item",
        "div.poly-card",
    ],
    "titulo": [
        "a.poly-component__title",
        "h2.poly-component__title",
        "a.promotion-item__link",
    ],
    "link": [
        "a.poly-component__title",
        "a.promotion-item__link",
    ],
    "imagem": [
        "img.poly-component__picture",
        "img.promotion-item__img",
    ],
    "preco_atual": [
        "div.poly-price__current span.andes-money-amount",
    ],
    "preco_anterior": [
        "s.andes-money-amount--previous",
        "span.promotion-item__price-previous",
    ],
}


def _primeiro_texto(elemento, seletores) -> Optional[str]:
    for seletor in seletores:
        encontrado = elemento.select_one(seletor)
        if encontrado:
            texto = encontrado.get_text(strip=True)
            if texto:
                return texto
    return None


def _primeiro_atributo(elemento, seletores, atributo) -> Optional[str]:
    for seletor in seletores:
        encontrado = elemento.select_one(seletor)
        if encontrado and encontrado.get(atributo):
            return encontrado.get(atributo)
    return None


def _parse_preco(texto: Optional[str]) -> Optional[float]:
    if not texto:
        return None
    limpo = re.sub(r"[^\d,]", "", texto)
    limpo = limpo.replace(".", "").replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return None


def calcular_desconto(preco_atual: float, preco_anterior: float) -> Optional[float]:
    if not preco_anterior or preco_anterior <= 0:
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


def _buscar_pagina_html(url: str) -> Optional[str]:
    headers = {
        "User-Agent": getattr(
            config,
            "SCRAPER_USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
    }
    try:
        resposta = requests.get(url, headers=headers, timeout=15)
        resposta.raise_for_status()
        return resposta.text
    except requests.RequestException as erro:
        logger.error("Falha ao consultar URL '%s': %s", url, erro)
        return None


def _extrair_promocao(card, categoria_nome: str = "Destaques") -> Optional[dict]:
    titulo = _primeiro_texto(card, _SELETORES["titulo"])
    url_produto = _primeiro_atributo(card, _SELETORES["link"], "href")
    imagem = (
        _primeiro_atributo(card, _SELETORES["imagem"], "src")
        or _primeiro_atributo(card, _SELETORES["imagem"], "data-src")
    )

    preco_atual = _parse_preco(_primeiro_texto(card, _SELETORES["preco_atual"]))
    preco_anterior = _parse_preco(_primeiro_texto(card, _SELETORES["preco_anterior"]))

    if not titulo or not url_produto or preco_atual is None:
        return None

    desconto = calcular_desconto(preco_atual, preco_anterior) if preco_anterior else None

    return {
        "titulo": titulo,
        "categoria": categoria_nome,
        "preco_atual": preco_atual,
        "preco_anterior": preco_anterior,
        "desconto": desconto,
        "imagem": imagem,
        "url_produto": url_produto,
        "url_afiliado": None,
        "cupom": getattr(config, "CUPOM_DESCONTO", None),
    }

def buscar_ofertas(
    url_categoria: Optional[str] = None, max_paginas: Optional[int] = None
) -> List[Dict]:
    max_paginas = max_paginas or getattr(config, "SCRAPER_MAX_PAGINAS", 1)
    promocoes: List[Dict] = []

    base_url = url_categoria or getattr(config, "MERCADO_LIVRE_OFERTAS_URL", "https://www.mercadolivre.com.br/ofertas")

    # Identifica o nome legível do nicho a partir da URL
    categoria_nome = "Ofertas"
    for nicho in NICHOS_ESTRATEGICOS:
        if nicho["url"] == url_categoria:
            categoria_nome = nicho["nome"]
            break

    for pagina in range(1, max_paginas + 1):
        if pagina > 1:
            divisor = "&" if "?" in base_url else "?"
            url = f"{base_url}{divisor}page={pagina}"
        else:
            url = base_url

        logger.info("Buscando ofertas da URL: %s", url)
        html = _buscar_pagina_html(url)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")

        cards = []
        for seletor in _SELETORES["card"]:
            cards = soup.select(seletor)
            if cards:
                break

        if not cards:
            logger.warning("Nenhum card encontrado em %s", url)
            break

        for card in cards:
            promocao = _extrair_promocao(card, categoria_nome=categoria_nome)
            if promocao:
                promocoes.append(promocao)

        if pagina < max_paginas:
            time.sleep(getattr(config, "SCRAPER_REQUEST_DELAY_SECONDS", 2))

    logger.info("%d produtos encontrados para [%s]", len(promocoes), categoria_nome)
    return promocoes