"""
Camada de comunicação com o Mercado Livre.
Faz o scraping da página pública de ofertas e buscas com suporte a paginação dinâmica.
"""

import logging
import random
import re
import time
from typing import Optional, List, Dict
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from app import config
from app.afiliados import gerar_link_afiliado

logger = logging.getLogger(__name__)

# Categorias oficiais, buscas e nichos estratégicos com alta conversão
NICHOS_ESTRATEGICOS = [
    
    {
        "nome": "Super Queimas & Liquidação",
        "url": "https://www.mercadolivre.com.br/ofertas",
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
        "nome": "Informática & Games",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1648",
    },
    {
        "nome": "Casa & Eletrodomésticos",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1574",
    },
    {
        "nome": "Beleza & Cuidados",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1246",
    },
    {
        # Reaproveita a categoria "Corrida & Esportes" (MLB1276), que já
        # funciona, e adiciona um filtro de busca por texto (&q=...) em
        # cima dela, em vez de usar lista.mercadolivre.com.br (que não
        # retorna cards pro scraper atual, provavelmente por carregar
        # os produtos via JavaScript).
        "nome": "Carbogel para Corredores",
        "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1276&q=gel+carboidrato",
    },
]

_SELETORES = {
    "card": [
        "div.andes-card.poly-card",
        "div.poly-card",
        "li.promotion-item",
        "li.ui-search-layout__item",
        "div.ui-search-result__wrapper",
    ],
    "titulo": [
        "a.poly-component__title",
        "h2.poly-component__title",
        "a.promotion-item__link",
        "h2.ui-search-item__title",
        "a.ui-search-link",
    ],
    "link": [
        "a.poly-component__title",
        "a.promotion-item__link",
        "a.ui-search-link",
        "a.ui-search-item__group__element",
    ],
    "imagem": [
        "img.poly-component__picture",
        "img.promotion-item__img",
        "img.ui-search-result-image__element",
    ],
    "preco_atual": [
        "div.poly-price__current span.andes-money-amount",
        "div.ui-search-price__second-line span.andes-money-amount",
        "div.ui-search-price--size-medium span.andes-money-amount",
    ],
    "preco_anterior": [
        "s.andes-money-amount--previous",
        "span.promotion-item__price-previous",
        "s.ui-search-price__part--medium",
        "s.ui-search-price__part",
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
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
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

    # Teto de preço inteligente para evitar produtos fora do perfil de compras rápidas
    if preco_atual > 900.0:
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


def _montar_url_paginada(base_url: str, pagina: int) -> str:
    """Monta a URL correta dependendo se é página de /ofertas ou busca em lista.mercadolivre."""
    # Remove qualquer âncora/hash residual
    url_base_limpa = base_url.split("#")[0]

    if pagina <= 1:
        return url_base_limpa

    if "lista.mercadolivre.com.br" in url_base_limpa:
        desde = ((pagina - 1) * 48) + 1
        return f"{url_base_limpa}_Desde_{desde}"
    else:
        divisor = "&" if "?" in url_base_limpa else "?"
        return f"{url_base_limpa}{divisor}page={pagina}"


def buscar_ofertas(
    url_categoria: Optional[str] = None, max_paginas: Optional[int] = None
) -> List[Dict]:
    paginas_para_buscar = max_paginas or getattr(config, "SCRAPER_MAX_PAGINAS", 3)
    promocoes: List[Dict] = []

    base_url = url_categoria or getattr(
        config, "MERCADO_LIVRE_OFERTAS_URL", "https://www.mercadolivre.com.br/ofertas"
    )

    categoria_nome = "Ofertas"
    for nicho in NICHOS_ESTRATEGICOS:
        if nicho["url"] == url_categoria:
            categoria_nome = nicho["nome"]
            break

    # Para buscas com volume menor (ex: lista), sempre começa da página 1
    # Para vitrines com grande volume (/ofertas), pode alternar entre 1 e 2
    if "lista.mercadolivre.com.br" in base_url:
        pagina_inicial = 1
    else:
        pagina_inicial = random.choice([1, 2])

    pagina_final = pagina_inicial + paginas_para_buscar

    for pagina in range(pagina_inicial, pagina_final):
        url = _montar_url_paginada(base_url, pagina)
        logger.info("Buscando ofertas: %s (Página %d) -> %s", categoria_nome, pagina, url)

        html = _buscar_pagina_html(url)
        if not html:
            break

        # --- DEBUG TEMPORÁRIO ---
        # Salva o HTML bruto recebido na primeira página de cada nicho,
        # só pra podermos inspecionar o que o Mercado Livre realmente
        # devolveu (ex: página de produtos com outras classes CSS,
        # tela de carregamento via JS, bloqueio/captcha, etc).
        # Remova este bloco depois de diagnosticar o problema.
        if pagina == pagina_inicial:
            nome_arquivo_debug = f"debug_{categoria_nome.replace(' ', '_').replace('&', 'e')}.html"
            try:
                with open(nome_arquivo_debug, "w", encoding="utf-8") as f:
                    f.write(html)
                logger.info(
                    "[DEBUG] HTML salvo em '%s' (%d caracteres)",
                    nome_arquivo_debug,
                    len(html),
                )
            except OSError as erro:
                logger.warning("[DEBUG] Não foi possível salvar o HTML: %s", erro)
        # --- FIM DEBUG TEMPORÁRIO ---

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

        time.sleep(getattr(config, "SCRAPER_REQUEST_DELAY_SECONDS", 2))

    logger.info("%d produtos válidos minerados para [%s]", len(promocoes), categoria_nome)
    return promocoes