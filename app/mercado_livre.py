"""
Camada de comunicação com o Mercado Livre — Fase 3.

Faz o scraping da página pública de ofertas do Mercado Livre e devolve
uma lista de promoções no formato usado pelo restante do bot.
"""

import logging
import re
import time
from typing import Optional
from urllib.parse import urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from app import config
from app.afiliados import gerar_link_afiliado

logger = logging.getLogger(__name__)

# Seletores CSS usados para extrair cada campo do card de produto.
_SELETORES = {
    "card": [
        "div.andes-card.poly-card",
        "li.promotion-item",
        "div.poly-card",
    ],
    "titulo": ["a.poly-component__title", "h2.poly-component__title", "a.promotion-item__link"],
    "link": ["a.poly-component__title", "a.promotion-item__link"],
    "imagem": ["img.poly-component__picture", "img.promotion-item__img"],
    "preco_atual": ["div.poly-price__current span.andes-money-amount"],
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
    """Converte '1.234,56' ou '1234' (texto do site) para float."""
    if not texto:
        return None
    limpo = re.sub(r"[^\d,]", "", texto)
    limpo = limpo.replace(".", "").replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return None


def calcular_desconto(preco_atual: float, preco_anterior: float) -> Optional[float]:
    """Calcula o percentual de desconto entre o preço anterior e o atual."""
    if not preco_anterior or preco_anterior <= 0:
        return None
    desconto = ((preco_anterior - preco_atual) / preco_anterior) * 100
    return round(desconto, 1)


def limpar_url_produto(url: str) -> str:
    """
    Remove parâmetros desnecessários de tracking e hash da URL do produto
    para enviar uma URL limpa para a API de afiliados.
    """
    if not url:
        return url
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def montar_link_afiliado(url_produto: str) -> str:
    """
    Gera o link oficial de afiliado (/social/...) usando a API interna
    do portal de afiliados. Se falhar, retorna a URL original.
    """
    if not url_produto:
        return url_produto

    url_limpa = limpar_url_produto(url_produto)
    link_oficial = gerar_link_afiliado(url_limpa)
    return link_oficial or url_produto


def _buscar_pagina_html(url: str) -> Optional[str]:
    headers = {"User-Agent": getattr(config, "SCRAPER_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")}
    try:
        resposta = requests.get(url, headers=headers, timeout=15)
        resposta.raise_for_status()
        return resposta.text
    except requests.RequestException as erro:
        logger.error("Falha ao consultar página de ofertas do Mercado Livre: %s", erro)
        return None


def _extrair_promocao(card) -> Optional[dict]:
    titulo = _primeiro_texto(card, _SELETORES["titulo"])
    url_produto = _primeiro_atributo(card, _SELETORES["link"], "href")
    imagem = _primeiro_atributo(card, _SELETORES["imagem"], "src") or \
        _primeiro_atributo(card, _SELETORES["imagem"], "data-src")

    preco_atual = _parse_preco(_primeiro_texto(card, _SELETORES["preco_atual"]))
    preco_anterior = _parse_preco(_primeiro_texto(card, _SELETORES["preco_anterior"]))

    if not titulo or not url_produto or preco_atual is None:
        return None

    desconto = calcular_desconto(preco_atual, preco_anterior) if preco_anterior else None

    return {
        "titulo": titulo,
        "preco_atual": preco_atual,
        "preco_anterior": preco_anterior,
        "desconto": desconto,
        "imagem": imagem,
        "url_produto": url_produto,
        "url_afiliado": None,
        "cupom": getattr(config, "CUPOM_DESCONTO", None),
    }


def buscar_ofertas(max_paginas: Optional[int] = None) -> list[dict]:
    """
    Busca ofertas na página pública do Mercado Livre e devolve uma lista
    de dicts com os links já convertidos para o formato oficial de afiliado.
    """
    max_paginas = max_paginas or config.SCRAPER_MAX_PAGINAS
    promocoes: list[dict] = []

    for pagina in range(1, max_paginas + 1):
        url = config.MERCADO_LIVRE_OFERTAS_URL
        if pagina > 1:
            url = f"{config.MERCADO_LIVRE_OFERTAS_URL}?{urlencode({'page': pagina})}"

        logger.info("Buscando ofertas (página %s)", pagina)
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
            logger.warning("Nenhum card de produto encontrado na página %s", pagina)
            break

        for card in cards:
            promocao = _extrair_promocao(card)
            if promocao:
                promocoes.append(promocao)

        if pagina < max_paginas:
            time.sleep(config.SCRAPER_REQUEST_DELAY_SECONDS)

    logger.info("%s produtos encontrados", len(promocoes))
    return promocoes


def testar_conexao() -> bool:
    """Diagnóstico rápido para testar o scraper e a geração de links."""
    print(f"Testando acesso a: {config.MERCADO_LIVRE_OFERTAS_URL}")
    html = _buscar_pagina_html(config.MERCADO_LIVRE_OFERTAS_URL)

    if not html:
        print("❌ Não foi possível acessar a página.")
        return False

    soup = BeautifulSoup(html, "html.parser")
    cards = []
    for seletor in _SELETORES["card"]:
        cards = soup.select(seletor)
        if cards:
            print(f"✅ Página acessada. {len(cards)} cards encontrados.")
            break

    if not cards:
        print("⚠️ Nenhum card encontrado com os seletores atuais.")
        return False

    link_exemplo = cards[0].select_one("a") and cards[0].select_one("a").get("href", "")
    if link_exemplo:
        exemplo = montar_link_afiliado(link_exemplo)
        print(f"✅ Teste de link gerado:\n{exemplo}")

    return True