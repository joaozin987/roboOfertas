"""
Camada de comunicação com o Mercado Livre — Fase 3.

Faz o scraping da página pública de ofertas do Mercado Livre e devolve
uma lista de promoções no formato usado pelo restante do bot.

⚠️ IMPORTANTE — leia antes de rodar em produção:

O Mercado Livre muda o layout/classes CSS da página de ofertas com
frequência, e tem proteção anti-bot ativa. Este módulo foi escrito com
os seletores mais comuns observados na estrutura atual do site, mas
PRECISA ser validado manualmente antes de rodar de forma automática:

    python -c "from app.mercado_livre import buscar_ofertas; import json; print(json.dumps(buscar_ofertas(), indent=2, ensure_ascii=False))"

Se a lista vier vazia, os seletores em `_SELETORES` provavelmente
precisam ser atualizados (inspecione a página no navegador e ajuste).

Este módulo não faz nenhuma tentativa de burlar bloqueios, captcha ou
login — se o Mercado Livre bloquear as requisições, o correto é reduzir
a frequência (`SCRAPER_REQUEST_DELAY_SECONDS`) ou migrar para a API
oficial de afiliados.
"""

import logging
import re
import time
from typing import Optional
from urllib.parse import urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from app import config

logger = logging.getLogger(__name__)

# Seletores CSS usados para extrair cada campo do card de produto.
# Mantidos centralizados aqui para facilitar ajustes quando o Mercado
# Livre mudar o layout.
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


def montar_link_afiliado(url_produto: str) -> str:
    """
    Acrescenta a tag de afiliado configurada (AFILIADO_ID) na URL do
    produto. Se não houver tag configurada, devolve a URL original.
    """
    if not config.AFILIADO_ID or not url_produto:
        return url_produto

    partes = urlparse(url_produto)
    query = f"matt_word={config.AFILIADO_ID}"
    if partes.query:
        query = f"{partes.query}&{query}"

    return urlunparse(partes._replace(query=query))


def _buscar_pagina_html(url: str) -> Optional[str]:
    headers = {"User-Agent": config.SCRAPER_USER_AGENT}
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
        # Card incompleto (ex.: propaganda, banner) — ignorar.
        return None

    desconto = calcular_desconto(preco_atual, preco_anterior) if preco_anterior else None

    return {
        "titulo": titulo,
        "preco_atual": preco_atual,
        "preco_anterior": preco_anterior,
        "desconto": desconto,
        "imagem": imagem,
        "url_produto": url_produto,
        "url_afiliado": montar_link_afiliado(url_produto),
        # Cupons não ficam disponíveis na página pública de ofertas;
        # fica como None a menos que seja preenchido manualmente depois.
        "cupom": None,
    }


def buscar_ofertas(max_paginas: Optional[int] = None) -> list[dict]:
    """
    Busca ofertas na página pública do Mercado Livre e devolve uma lista
    de dicts no formato usado pelo restante do bot (ver README).

    Aplica um intervalo entre requisições (SCRAPER_REQUEST_DELAY_SECONDS)
    para reduzir o risco de bloqueio.
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
            logger.warning(
                "Nenhum card de produto encontrado na página %s — os seletores "
                "em _SELETORES provavelmente precisam ser atualizados.",
                pagina,
            )
            break

        for card in cards:
            promocao = _extrair_promocao(card)
            if promocao:
                promocoes.append(promocao)

        if pagina < max_paginas:
            time.sleep(config.SCRAPER_REQUEST_DELAY_SECONDS)

    logger.info("%s produtos encontrados", len(promocoes))
    return promocoes


def debug_dump_primeiro_card(max_chars: int = 3000) -> None:
    """
    Função de apoio para ajustar os seletores: busca a página de ofertas,
    localiza o primeiro card com o seletor que está funcionando, e
    imprime o HTML dele formatado (truncado em `max_chars`).

    Use isso quando `buscar_ofertas()` estiver retornando 0 itens mesmo
    com `testar_conexao()` encontrando cards — o resultado impresso
    mostra exatamente as classes reais de título, link, preço e imagem
    pra ajustar `_SELETORES`.
    """
    html = _buscar_pagina_html(config.MERCADO_LIVRE_OFERTAS_URL)
    if not html:
        print("Não foi possível baixar a página.")
        return

    soup = BeautifulSoup(html, "html.parser")
    card = None
    for seletor in _SELETORES["card"]:
        card = soup.select_one(seletor)
        if card:
            print(f"Usando seletor de card: '{seletor}'\n")
            break

    if not card:
        print("Nenhum card encontrado com os seletores atuais.")
        return

    trecho = card.prettify()[:max_chars]
    print(trecho)
    if len(card.prettify()) > max_chars:
        print(f"\n... (truncado — HTML completo tem {len(card.prettify())} caracteres)")


def testar_conexao() -> bool:
    """
    Diagnóstico rápido: confirma se conseguimos acessar a página de
    ofertas do Mercado Livre e encontrar produtos nela.

    Como o scraper não usa login/token, "conectado" aqui significa:
    (1) a requisição HTTP teve sucesso (status 200) e
    (2) pelo menos um card de produto foi encontrado com os seletores
        atuais.

    Retorna True se ambas as condições forem atendidas.
    """
    print(f"Testando acesso a: {config.MERCADO_LIVRE_OFERTAS_URL}")
    html = _buscar_pagina_html(config.MERCADO_LIVRE_OFERTAS_URL)

    if not html:
        print("❌ Não foi possível acessar a página (veja o log de erro acima).")
        return False

    soup = BeautifulSoup(html, "html.parser")
    cards = []
    for seletor in _SELETORES["card"]:
        cards = soup.select(seletor)
        if cards:
            print(f"✅ Página acessada. {len(cards)} cards encontrados com o seletor '{seletor}'.")
            break

    if not cards:
        print(
            "⚠️ Página acessada com sucesso, mas nenhum card de produto foi "
            "encontrado. Os seletores em _SELETORES provavelmente precisam "
            "ser atualizados (inspecione a página no navegador)."
        )
        return False

    if config.AFILIADO_ID:
        exemplo = montar_link_afiliado(cards[0].select_one("a") and cards[0].select_one("a").get("href", "") or "https://produto.mercadolivre.com.br/exemplo")
        print(f"✅ Tag de afiliado configurada. Exemplo de link gerado:\n{exemplo}")
    else:
        print("⚠️ AFILIADO_ID não configurado no .env — os links não terão tag de afiliado.")

    return True