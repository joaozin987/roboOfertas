"""
Camada de comunicação com o Mercado Livre.
Scraping com evasão de bloqueio TLS via curl_cffi.
"""

import logging
import re
import time
from typing import Optional, List, Dict
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup
from curl_cffi import requests

from app import config
from app.afiliados import gerar_link_afiliado

logger = logging.getLogger(__name__)

# Sessão que emula o aperto de mão TLS/JA3 idêntico ao Google Chrome real
_session = requests.Session(impersonate="chrome124")

NICHOS_ESTRATEGICOS = [
    {
        "nome": "Aura Beauty",
        "url": "https://lista.mercadolivre.com.br/aura-beauty_NoIndex_True",
    },
    {
        "nome": "Roupas leves e esportivas",
        "url": "https://lista.mercadolivre.com.br/confira-camisa-de-corrida-unissex-ultraleve-de-secagem-r%C3%A1pid?sb=all_mercadolibre",
    },
    {
        "nome": "Smartphones & Celulares",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1051",
    },
    {
        "nome": "Moda & Calçados",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1430",
    },
    {
        "nome": "Corrida & Esportes",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1276",
    },
    {
        "nome": "Estética Automotiva",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1747",
    },
    {
        "nome": "Informática & Games",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1648",
    },
    {
        "nome": "Casa & Eletrodomésticos",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1574",
    },
    {
        "nome": "Ferramentas & Construção",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1500",
    },
    {
        "nome": "Beleza & Cuidados",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1246",
    },
]

_SELETORES = {
    "card": [
        "li.ui-search-layout__item",
        "div.ui-search-result__wrapper",
        "div.andes-card.poly-card",
        "div.poly-card",
        "li.promotion-item",
        "div.ui-search-result",
    ],
    "titulo": [
        "a.poly-component__title",
        "h2.poly-component__title",
        "h2.ui-search-item__title",
        "a.promotion-item__link",
        "a.ui-search-link",
    ],
    "link": [
        "a.poly-component__title",
        "a.ui-search-link",
        "a.ui-search-item__group__element",
        "a.promotion-item__link",
    ],
    "imagem": [
        "img.poly-component__picture",
        "img.ui-search-result-image__element",
        "img.promotion-item__img",
    ],
    "preco_atual": [
        "div.poly-price__current span.andes-money-amount",
        "div.ui-search-price__second-line span.andes-money-amount",
        "div.ui-search-price--size-medium span.andes-money-amount",
        "span.andes-money-amount.ui-search-price__part",
    ],
    "preco_anterior": [
        "s.andes-money-amount--previous",
        "s.ui-search-price__part--medium",
        "s.ui-search-price__part",
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
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    try:
        # curl_cffi resolve o handshake TLS sem cair no filtro anti-bot básico
        resposta = _session.get(url, headers=headers, timeout=20)
        resposta.raise_for_status()

        # Checagem de integridade: páginas reais de produtos têm dezenas/centenas de KB
        if len(resposta.text) < 15000:
            logger.warning(
                "Possível bloqueio: resposta muito curta (%d bytes) para a URL: %s",
                len(resposta.text),
                url,
            )
            return None

        return resposta.text
    except Exception as erro:
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

    # Trava de segurança para nicho de marca específica
    if categoria_nome == "Aura Beauty" and "aura" not in titulo.lower():
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
        "url_afiliado": montar_link_afiliado(url_produto),
        "cupom": getattr(config, "CUPOM_DESCONTO", None),
    }


def _montar_url_paginacao(base_url: str, pagina: int) -> str:
    if pagina <= 1:
        return base_url

    parsed = urlparse(base_url)
    if "lista.mercadolivre.com.br" in parsed.netloc:
        offset = (pagina - 1) * 48 + 1
        path = f"{parsed.path}_Desde_{offset}"
        return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))

    divisor = "&" if "?" in base_url else "?"
    return f"{base_url}{divisor}page={pagina}"


def buscar_ofertas(
    url_categoria: Optional[str] = None, max_paginas: Optional[int] = None
) -> List[Dict]:
    max_paginas = max_paginas or getattr(config, "SCRAPER_MAX_PAGINAS", 1)
    promocoes: List[Dict] = []

    base_url = url_categoria or getattr(config, "MERCADO_LIVRE_OFERTAS_URL", "https://www.mercadolivre.com.br/ofertas")

    categoria_nome = "Ofertas"
    for nicho in NICHOS_ESTRATEGICOS:
        if nicho["url"] == url_categoria:
            categoria_nome = nicho["nome"]
            break

    for pagina in range(1, max_paginas + 1):
        url = _montar_url_paginacao(base_url, pagina)

        logger.info("Buscando ofertas da URL: %s", url)
        html = _buscar_pagina_html(url)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")

        cards = []
        for seletor in _SELETORES["card"]:
            encontrados = soup.select(seletor)
            if encontrados:
                cards = encontrados
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