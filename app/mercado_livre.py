"""
Camada de comunicação com o Mercado Livre.
Faz o scraping da página pública de ofertas e buscas com suporte a paginação dinâmica.
"""

import logging
import random
import re
import time
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app import config
from app.afiliados import gerar_link_afiliado

logger = logging.getLogger(__name__)

BASE_URL = "https://www.mercadolivre.com.br"

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

_SESSAO = requests.Session()


# ------------------------------------------------------------------ helpers

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
    """Lê 'R$ 1.299,90' / '59,90' / '59'. Usa o PRIMEIRO número do texto."""
    if not texto:
        return None
    m = re.search(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?", texto)
    if not m:
        return None
    inteiro = m.group(1).replace(".", "")
    centavos = (m.group(2) or "0").ljust(2, "0")
    try:
        return float(f"{inteiro}.{centavos}")
    except ValueError:
        return None


def _preco_do_elemento(elemento) -> Optional[float]:
    """
    Lê fração e centavos separadamente. O get_text() do bloco inteiro cola os
    dois ('R$5990'), o que faria R$ 59,90 virar 5990.
    """
    fracao = elemento.select_one("span.andes-money-amount__fraction")
    if fracao:
        inteiro = re.sub(r"\D", "", fracao.get_text())
        if inteiro:
            cents = elemento.select_one("span.andes-money-amount__cents")
            centavos = re.sub(r"\D", "", cents.get_text())[:2] if cents else ""
            return float(f"{inteiro}.{(centavos or '0').ljust(2, '0')}")
    return _parse_preco(elemento.get_text(" ", strip=True))


def _primeiro_preco(card, seletores) -> Optional[float]:
    for seletor in seletores:
        elemento = card.select_one(seletor)
        if elemento:
            preco = _preco_do_elemento(elemento)
            if preco is not None:
                return preco
    return None


def _extrair_imagem(card) -> Optional[str]:
    """O ML usa lazy-load: o src costuma ser um placeholder 'data:image/...'."""
    for seletor in _SELETORES["imagem"]:
        elemento = card.select_one(seletor)
        if not elemento:
            continue
        for atributo in ("data-src", "src", "data-lazy"):
            valor = elemento.get(atributo)
            if valor and not valor.startswith("data:"):
                return "https:" + valor if valor.startswith("//") else valor
    return None


def calcular_desconto(preco_atual: float, preco_anterior: float) -> Optional[float]:
    if not preco_anterior or preco_anterior <= 0:
        return None
    desconto = ((preco_anterior - preco_atual) / preco_anterior) * 100
    return round(desconto, 1)


def montar_link_afiliado(url_produto: str) -> Optional[str]:
    """Link de afiliado ou None. Nunca devolve o link cru (sem comissão)."""
    if not url_produto:
        return None
    return gerar_link_afiliado(url_produto)  # a limpeza da URL é feita lá


# --------------------------------------------------------------------- rede

def _buscar_pagina_html(url: str, tentativas: int = 3) -> Optional[str]:
    headers = {
        "User-Agent": getattr(config, "SCRAPER_USER_AGENT", "Mozilla/5.0"),
        "Accept-Language": "pt-BR,pt;q=0.9",
    }
    for tentativa in range(1, tentativas + 1):
        try:
            resposta = _SESSAO.get(url, headers=headers, timeout=15)
        except requests.RequestException as erro:
            logger.warning(
                "Falha de rede em '%s' (%s), tentativa %d/%d",
                url, type(erro).__name__, tentativa, tentativas,
            )
        else:
            if resposta.status_code == 200:
                return resposta.text
            if resposta.status_code in (429, 500, 502, 503, 504):
                logger.warning(
                    "HTTP %d em '%s', tentativa %d/%d",
                    resposta.status_code, url, tentativa, tentativas,
                )
            else:
                logger.error("HTTP %d em '%s'", resposta.status_code, url)
                return None
        time.sleep(2 * tentativa + random.random())
    return None


# -------------------------------------------------------------- extração

def _extrair_promocao(card, categoria_nome: str = "Destaques") -> Optional[dict]:
    titulo = _primeiro_texto(card, _SELETORES["titulo"])
    url_produto = _primeiro_atributo(card, _SELETORES["link"], "href")
    preco_atual = _primeiro_preco(card, _SELETORES["preco_atual"])
    preco_anterior = _primeiro_preco(card, _SELETORES["preco_anterior"])

    if not titulo or not url_produto or preco_atual is None:
        return None

    # Teto de preço para evitar produtos fora do perfil de compras rápidas
    if preco_atual > getattr(config, "ML_PRECO_MAXIMO", 900.0):
        return None

    # Preço "de" que não é maior que o atual é leitura errada (ex.: parcela), não desconto
    if preco_anterior is not None and preco_anterior <= preco_atual:
        preco_anterior = None

    desconto = calcular_desconto(preco_atual, preco_anterior) if preco_anterior else None

    return {
        "origem": "mercado_livre",
        "titulo": titulo,
        "categoria": categoria_nome,
        "preco_atual": preco_atual,
        "preco_anterior": preco_anterior,
        "desconto": desconto,
        "imagem": _extrair_imagem(card),
        "url_produto": urljoin(BASE_URL, url_produto),
        "url_afiliado": None,
        "cupom": getattr(config, "CUPOM_DESCONTO", None),
    }


def _montar_url_paginada(base_url: str, pagina: int) -> str:
    """Monta a URL correta dependendo se é página de /ofertas ou busca em lista.mercadolivre."""
    url_base_limpa = base_url.split("#")[0]

    if pagina <= 1:
        return url_base_limpa

    if "lista.mercadolivre.com.br" in url_base_limpa:
        desde = ((pagina - 1) * 48) + 1
        return f"{url_base_limpa}_Desde_{desde}"

    divisor = "&" if "?" in url_base_limpa else "?"
    return f"{url_base_limpa}{divisor}page={pagina}"


def _salvar_html_debug(categoria_nome: str, html: str) -> None:
    nome = f"debug_{categoria_nome.replace(' ', '_').replace('&', 'e')}.html"
    try:
        with open(nome, "w", encoding="utf-8") as arquivo:
            arquivo.write(html)
        logger.info("[DEBUG] HTML salvo em '%s' (%d caracteres)", nome, len(html))
    except OSError as erro:
        logger.warning("[DEBUG] Não foi possível salvar o HTML: %s", erro)


def buscar_ofertas(
    url_categoria: Optional[str] = None, max_paginas: Optional[int] = None
) -> List[Dict]:
    paginas_para_buscar = max_paginas or getattr(config, "SCRAPER_MAX_PAGINAS", 3)
    promocoes: List[Dict] = []

    base_url = url_categoria or getattr(
        config, "MERCADO_LIVRE_OFERTAS_URL", f"{BASE_URL}/ofertas"
    )

    categoria_nome = "Ofertas"
    for nicho in NICHOS_ESTRATEGICOS:
        if nicho["url"] == url_categoria:
            categoria_nome = nicho["nome"]
            break

    # Buscas com volume menor (lista) começam na página 1; vitrines grandes alternam 1 e 2
    if "lista.mercadolivre.com.br" in base_url:
        pagina_inicial = 1
    else:
        pagina_inicial = random.choice([1, 2])

    for pagina in range(pagina_inicial, pagina_inicial + paginas_para_buscar):
        url = _montar_url_paginada(base_url, pagina)
        logger.info("Buscando ofertas: %s (Página %d) -> %s", categoria_nome, pagina, url)

        html = _buscar_pagina_html(url)
        if not html:
            break

        if getattr(config, "DEBUG_SALVAR_HTML", False) and pagina == pagina_inicial:
            _salvar_html_debug(categoria_nome, html)

        soup = BeautifulSoup(html, "html.parser")

        cards = []
        for seletor in _SELETORES["card"]:
            cards = soup.select(seletor)
            if cards:
                break

        if not cards:
            if pagina == pagina_inicial:
                logger.error(
                    "Nenhum card em %s: os seletores podem estar desatualizados "
                    "ou a página foi bloqueada. Ative DEBUG_SALVAR_HTML=true para inspecionar.",
                    url,
                )
            else:
                logger.warning("Nenhum card encontrado em %s", url)
            break

        for card in cards:
            promocao = _extrair_promocao(card, categoria_nome=categoria_nome)
            if promocao:
                promocoes.append(promocao)

        time.sleep(
            getattr(config, "SCRAPER_REQUEST_DELAY_SECONDS", 2) + random.random()
        )

    logger.info("%d produtos válidos minerados para [%s]", len(promocoes), categoria_nome)
    return promocoes