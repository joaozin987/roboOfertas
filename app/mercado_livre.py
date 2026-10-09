"""
Camada de comunicação com o Mercado Livre.
Faz o scraping otimizado de ofertas e buscas com suporte a paginação e trava anti-lixo.
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

# ==============================================================
# NICHOS ESTRATEGICOS (Com Perfumes Árabes e Nacionais Inclusos)
# ==============================================================
NICHOS_ESTRATEGICOS = [
    {"nome": "Perfumes Árabes Hype", "url": "https://lista.mercadolivre.com.br/beleza-cuidado-pessoal/perfumes/perfumes-arabes"},
    {"nome": "Perfumaria Nacional Top", "url": "https://lista.mercadolivre.com.br/beleza-cuidado-pessoal/perfumes/boticario-natura"},
    {"nome": "Nutrição & Performance Fitness",   "url": "https://lista.mercadolivre.com.br/esportes-fitness/suplementos/nutricao-esportiva"},
    {"nome": "Malas & Viagem", "url": "https://lista.mercadolivre.com.br/calcados-roupas/malas-bolsas/malas-viagem"},
    {"nome": "Moda & Vestuário", "url": "https://lista.mercadolivre.com.br/calcados-roupas/roupas"},
    {"nome": "Super Queimas & Liquidação", "url": "https://www.mercadolivre.com.br/ofertas"},
    {"nome": "Smartphones & Celulares", "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1051"},
    {"nome": "Moda & Calçados", "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1430"},
    {"nome": "Corrida & Esportes", "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1276"},
    {"nome": "Informática & Games", "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1648"},
    {"nome": "Casa & Eletrodomésticos", "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1574"},
    {"nome": "Beleza & Cuidados", "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1246"},
    
]

# ==============================================================
# SELETORES CSS
# ==============================================================
_SELETORES = {
    "card": ["div.andes-card.poly-card", "div.poly-card", "li.promotion-item", "li.ui-search-layout__item", "div.ui-search-result__wrapper"],
    "titulo": ["a.poly-component__title", "h2.poly-component__title", "a.promotion-item__link", "h2.ui-search-item__title", "a.ui-search-link"],
    "link": ["a.poly-component__title", "a.promotion-item__link", "a.ui-search-link", "a.ui-search-item__group__element"],
    "imagem": ["img.poly-component__picture", "img.promotion-item__img", "img.ui-search-result-image__element"],
    "preco_atual": ["div.poly-price__current span.andes-money-amount", "div.ui-search-price__second-line span.andes-money-amount", "div.ui-search-price--size-medium span.andes-money-amount"],
    "preco_anterior": ["s.andes-money-amount--previous", "span.promotion-item__price-previous", "s.ui-search-price__part--medium", "s.ui-search-price__part"],
}

# ==============================================================
# TERMOS OBRIGATÓRIOS (TRAVA ANTI-LIXO)
# ==============================================================
TERMOS_OBRIGATORIOS_POR_CATEGORIA = {
    "Smartphones & Celulares": ["smartphone", "celular", "iphone", "samsung", "galaxy", "xiaomi", "motorola", "moto"],
    "Moda & Calçados": ["tênis", "sapato", "camisa", "camiseta", "calça", "bermuda", "sandália", "chinelo", "mochila"],
    "Corrida & Esportes": ["tênis", "corrida", "esporte", "academia", "treino", "chuteira", "bicicleta", "whey", "creatina", "suplemento"],
    "Informática & Games": ["notebook", "laptop", "placa de vídeo", "processador", "monitor", "teclado", "mouse", "headset", "ssd", "gamer"],
    "Casa & Eletrodomésticos": ["air fryer", "liquidificador", "aspirador", "panela", "ventilador", "cafeteira", "micro-ondas"],
    "Beleza & Cuidados": ["perfume", "colônia", "desodorante", "creme", "shampoo", "secador", "prancha"],
    "Perfumes Árabes Hype": ["lattafa", "armaf", "rasasi", "al haramain", "perfume", "eau de", "colônia", "asado", "yara", "khamrah", "club de nuit", "fakhar", "hawas"],
    "Perfumaria Nacional Top": ["boticario", "boticário", "natura", "malbec", "egeo", "kaiak", "essencial", "humor", "perfume", "colônia", "ekos", "quasar", "floratta"]
}

def _validar_relevancia_titulo(titulo: str, categoria_nome: str) -> bool:
    """Garante que o produto pertence de fato à categoria, evitando falsos positivos."""
    if not titulo:
        return False
    titulo_lower = titulo.lower()
    termos = TERMOS_OBRIGATORIOS_POR_CATEGORIA.get(categoria_nome, [])
    if not termos:
        return True
    return any(termo in titulo_lower for termo in termos)

_SESSAO = requests.Session()

# ==============================================================
# HELPERS DE PARSE E EXTRAÇÃO
# ==============================================================
def _primeiro_texto(elemento, seletores) -> Optional[str]:
    for seletor in seletores:
        if (encontrado := elemento.select_one(seletor)) and (texto := encontrado.get_text(strip=True)):
            return texto
    return None

def _primeiro_atributo(elemento, seletores, atributo) -> Optional[str]:
    for seletor in seletores:
        if (encontrado := elemento.select_one(seletor)) and encontrado.get(atributo):
            return encontrado.get(atributo)
    return None

def _parse_preco(texto: Optional[str]) -> Optional[float]:
    if not texto:
        return None
    m = re.search(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?", texto)
    if not m:
        return None
    try:
        return float(f"{m.group(1).replace('.', '')}.{(m.group(2) or '0').ljust(2, '0')}")
    except ValueError:
        return None

def _preco_do_elemento(elemento) -> Optional[float]:
    if fracao := elemento.select_one("span.andes-money-amount__fraction"):
        if inteiro := re.sub(r"\D", "", fracao.get_text()):
            cents = elemento.select_one("span.andes-money-amount__cents")
            centavos = re.sub(r"\D", "", cents.get_text())[:2] if cents else ""
            return float(f"{inteiro}.{(centavos or '0').ljust(2, '0')}")
    return _parse_preco(elemento.get_text(" ", strip=True))

def _primeiro_preco(card, seletores) -> Optional[float]:
    for seletor in seletores:
        if (elemento := card.select_one(seletor)) and (preco := _preco_do_elemento(elemento)) is not None:
            return preco
    return None

def _extrair_imagem(card) -> Optional[str]:
    for seletor in _SELETORES["imagem"]:
        if elemento := card.select_one(seletor):
            for atributo in ("data-src", "src", "data-lazy"):
                if (valor := elemento.get(atributo)) and not valor.startswith("data:"):
                    return "https:" + valor if valor.startswith("//") else valor
    return None

def calcular_desconto(preco_atual: float, preco_anterior: float) -> Optional[float]:
    if not preco_anterior or preco_anterior <= 0:
        return None
    return round(((preco_anterior - preco_atual) / preco_anterior) * 100, 1)

def montar_link_afiliado(url_produto: str) -> Optional[str]:
    return gerar_link_afiliado(url_produto) if url_produto else None

# ==============================================================
# REDE E SCRAPER
# ==============================================================
def _buscar_pagina_html(url: str, tentativas: int = 3) -> Optional[str]:
    headers = {
        "User-Agent": getattr(config, "SCRAPER_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if cookie := getattr(config, "MELI_COOKIE_HEADER", "").strip():
        headers["Cookie"] = cookie

    for tentativa in range(1, tentativas + 1):
        try:
            resposta = _SESSAO.get(url, headers=headers, timeout=20, allow_redirects=True)
            if resposta.status_code == 200:
                return resposta.text
            if resposta.status_code not in (403, 429, 500, 502, 503, 504):
                return None
        except requests.RequestException:
            pass
        time.sleep(2 * tentativa + random.random())
    return None

def _extrair_promocao(card, categoria_nome: str = "Destaques") -> Optional[dict]:
    titulo = _primeiro_texto(card, _SELETORES["titulo"])
    url_produto = _primeiro_atributo(card, _SELETORES["link"], "href")
    preco_atual = _primeiro_preco(card, _SELETORES["preco_atual"])
    preco_anterior = _primeiro_preco(card, _SELETORES["preco_anterior"])

    if not titulo or not url_produto or preco_atual is None:
        return None

    # Aplicação da Trava Anti-Lixo
    if not _validar_relevancia_titulo(titulo, categoria_nome):
        logger.warning(f"Descartado por irrelevância em '{categoria_nome}': {titulo}")
        return None

    if preco_atual > getattr(config, "ML_PRECO_MAXIMO", 900.0):
        return None

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
    url_limpa = base_url.split("#")[0]
    if pagina <= 1:
        return url_limpa
    if "lista.mercadolivre.com.br" in url_limpa:
        desde = ((pagina - 1) * 48) + 1
        return f"{url_limpa}_Desde_{desde}"
    divisor = "&" if "?" in url_limpa else "?"
    return f"{url_limpa}{divisor}page={pagina}"

def buscar_ofertas(url_categoria: Optional[str] = None, max_paginas: Optional[int] = None) -> List[Dict]:
    paginas_para_buscar = max_paginas or getattr(config, "SCRAPER_MAX_PAGINAS", 3)
    promocoes = []
    base_url = url_categoria or getattr(config, "MERCADO_LIVRE_OFERTAS_URL", f"{BASE_URL}/ofertas")
    
    categoria_nome = next((n["nome"] for n in NICHOS_ESTRATEGICOS if n["url"] == url_categoria), "Ofertas")
    pagina_inicial = 1 if "lista.mercadolivre.com.br" in base_url else random.choice([1, 2])

    for pagina in range(pagina_inicial, pagina_inicial + paginas_para_buscar):
        url = _montar_url_paginada(base_url, pagina)
        html = _buscar_pagina_html(url)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        cards = []
        for seletor in _SELETORES["card"]:
            if encontrados := soup.select(seletor):
                cards = encontrados
                break

        if not cards:
            break

        for card in cards:
            if promocao := _extrair_promocao(card, categoria_nome=categoria_nome):
                promocoes.append(promocao)

        time.sleep(getattr(config, "SCRAPER_REQUEST_DELAY_SECONDS", 2) + random.random())

    return promocoes