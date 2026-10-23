"""
Camada de comunicação com o Mercado Livre.

buscar_ofertas() tenta primeiro a API OFICIAL (OAuth 2.0 via MercadoLivreAPI)
e só cai no scraping com curl_cffi como último recurso caso a API não esteja ativa.
"""

import logging
import os
import random
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from app import config
from app.afiliados import gerar_link_afiliado

logger = logging.getLogger(__name__)
BASE_URL = "https://www.mercadolivre.com.br"
API_BASE = "https://api.mercadolibre.com"

_API_CLIENTE = None


def _preco_maximo() -> float:
    """Preço máximo aceito no ML: variável ML_PRECO_MAXIMO do .env > config > 900."""
    try:
        return float(os.getenv("ML_PRECO_MAXIMO") or getattr(config, "ML_PRECO_MAXIMO", 900.0))
    except (TypeError, ValueError):
        return 900.0


def _env_bool(nome: str, padrao: bool) -> bool:
    valor = os.getenv(nome)
    if valor is None or valor.strip() == "":
        return padrao
    return valor.strip().lower() in ("1", "true", "sim", "yes", "on")


# ==============================================================
# NICHOS ESTRATÉGICOS
# ==============================================================
NICHOS_ESTRATEGICOS = [
    {"nome": "Smartphones & Celulares", "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1051"},
    {"nome": "Moda & Calçados", "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1430"},
    {"nome": "Corrida & Esportes", "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1276"},
    {"nome": "Informática & Games", "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1648"},
    {"nome": "Casa & Eletrodomésticos", "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1574"},
    {"nome": "Beleza & Cuidados", "url": "https://www.mercadolivre.com.br/ofertas?category=MLB1246"},
]

# ==============================================================
# SELETORES CSS (Para o Scraping de Fallback)
# ==============================================================
_SELETORES = {
    "card": ["div.andes-card.poly-card", "div.poly-card", "li.promotion-item", "li.ui-search-layout__item", "div.ui-search-result__wrapper"],
    "titulo": ["a.poly-component__title", "h2.poly-component__title", "a.promotion-item__link", "h2.ui-search-item__title", "a.ui-search-link"],
    "link": ["a.poly-component__title", "a.promotion-item__link", "a.ui-search-link", "a.ui-search-item__group__element"],
    "imagem": ["img.poly-component__picture", "img.promotion-item__img", "img.ui-search-result-image__element"],
    "preco_atual": ["div.poly-price__current span.andes-money-amount", "div.ui-search-price__second-line span.andes-money-amount", "div.ui-search-price--size-medium span.andes-money-amount"],
    "preco_anterior": ["s.andes-money-amount--previous", "span.promotion-item__price-previous", "s.ui-search-price__part--medium", "s.ui-search-price__part"],
}

# TERMOS OBRIGATÓRIOS (TRAVA ANTI-LIXO)
TERMOS_OBRIGATORIOS_POR_CATEGORIA = {
    "Smartphones & Celulares": ["smartphone", "celular", "iphone", "samsung", "galaxy", "xiaomi", "motorola", "moto"],
    "Moda & Calçados": ["tênis", "sapato", "camisa", "camiseta", "calça", "bermuda", "sandália", "chinelo", "mochila"],
    "Corrida & Esportes": ["tênis", "corrida", "esporte", "academia", "treino", "chuteira", "bicicleta", "whey", "creatina", "suplemento"],
    "Informática & Games": ["notebook", "laptop", "placa de vídeo", "processador", "monitor", "teclado", "mouse", "headset", "ssd", "gamer"],
    "Casa & Eletrodomésticos": ["air fryer", "liquidificador", "aspirador", "panela", "ventilador", "cafeteira", "micro-ondas"],
    "Beleza & Cuidados": ["perfume", "colônia", "desodorante", "creme", "shampoo", "secador", "prancha"],
    "Perfumes Árabes Hype": ["lattafa", "armaf", "rasasi", "al haramain", "perfume", "eau de", "colônia", "asado", "yara", "khamrah", "club de nuit", "fakhar", "hawas"],
    "Perfumaria Nacional Top": ["boticario", "boticário", "natura", "malbec", "egeo", "kaiak", "essencial", "humor", "perfume", "colônia", "ekos", "quasar", "floratta"],
}


def _validar_relevancia_titulo(titulo: str, categoria_nome: str) -> bool:
    if not titulo:
        return False
    titulo_lower = titulo.lower()
    termos = TERMOS_OBRIGATORIOS_POR_CATEGORIA.get(categoria_nome, [])
    if not termos:
        return True
    return any(termo in titulo_lower for termo in termos)


def calcular_desconto(preco_atual: float, preco_anterior: float) -> Optional[float]:
    if not preco_anterior or preco_anterior <= 0:
        return None
    return round(((preco_anterior - preco_atual) / preco_anterior) * 100, 1)


def montar_link_afiliado(url_produto: str) -> Optional[str]:
    return gerar_link_afiliado(url_produto) if url_produto else None


# ==============================================================
# AUTENTICAÇÃO E TOKEN OAUTH (API OFICIAL)
# ==============================================================
def _obter_token() -> Optional[str]:
    """Obtém um access_token válido usando a classe MercadoLivreAPI."""
    global _API_CLIENTE
    try:
        if _API_CLIENTE is None:
            from app.mercado_livre_api import MercadoLivreAPI

            client_id = getattr(config, "ML_CLIENT_ID", None) or os.getenv("ML_CLIENT_ID", "")
            client_secret = getattr(config, "ML_CLIENT_SECRET", None) or os.getenv("ML_CLIENT_SECRET", "")
            redirect_uri = getattr(config, "ML_REDIRECT_URI", None) or os.getenv("ML_REDIRECT_URI", "")
            
            if not client_id or not client_secret:
                logger.error("ML API: ML_CLIENT_ID ou ML_CLIENT_SECRET não configurados.")
                return None
            _API_CLIENTE = MercadoLivreAPI(client_id, client_secret, redirect_uri)
            
        token = _API_CLIENTE.get_token_valido()
        logger.info("ML API: Token OAuth validado com sucesso.")
        return token
    except Exception as erro:
        logger.error("ML API: Falha ao obter access_token: %s", erro)
    return None


def _get_api(caminho: str, params: dict, token: Optional[str], tentativas: int = 2) -> Tuple[Optional[int], Optional[object]]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{API_BASE}{caminho}"
    
    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=20)
            logger.info("ML API GET %s -> %s [tentativa %d/%d]", caminho, resp.status_code, tentativa, tentativas)
            if resp.status_code == 200:
                return 200, resp.json()
            if resp.status_code in (401, 403):
                logger.warning("ML API: Acesso negado (%s): %s", resp.status_code, resp.text[:200])
                return resp.status_code, None
            time.sleep(2 * tentativa)
        except Exception as erro:
            logger.warning("ML API: Erro em %s: %s", caminho, erro)
            time.sleep(2 * tentativa)
    return None, None


def _para_promocao(item: dict, categoria_nome: str) -> Optional[Dict]:
    titulo = item.get("title")
    preco_atual = item.get("price")
    link = item.get("permalink")
    
    if not titulo or not link or preco_atual is None:
        return None
    try:
        preco_atual = float(preco_atual)
    except (TypeError, ValueError):
        return None

    if not _validar_relevancia_titulo(titulo, categoria_nome):
        return None

    if preco_atual > _preco_maximo():
        return None

    preco_anterior = item.get("original_price")
    try:
        preco_anterior = float(preco_anterior) if preco_anterior else None
    except (TypeError, ValueError):
        preco_anterior = None
        
    if preco_anterior is not None and preco_anterior <= preco_atual:
        preco_anterior = None

    imagem = item.get("thumbnail") or ""
    if imagem:
        imagem = imagem.replace("http://", "https://").replace("-I.jpg", "-O.jpg")

    return {
        "origem": "mercado_livre",
        "titulo": titulo,
        "categoria": categoria_nome,
        "preco_atual": preco_atual,
        "preco_anterior": preco_anterior,
        "desconto": calcular_desconto(preco_atual, preco_anterior) if preco_anterior else None,
        "imagem": imagem or None,
        "url_produto": link,
        "url_afiliado": None,
        "cupom": getattr(config, "CUPOM_DESCONTO", None),
    }


def _id_categoria(url_categoria: Optional[str]) -> Optional[str]:
    if not url_categoria:
        return None
    m = re.search(r"category=(MLB\d+)", url_categoria)
    return m.group(1) if m else None


# ==============================================================
# CAMINHOS DA API OFICIAL
# ==============================================================
def _via_busca(cat_id: str, categoria_nome: str, token: str, paginas: int) -> List[Dict]:
    resultado = []
    limite = 50
    for pagina in range(paginas):
        status, dados = _get_api(
            "/sites/MLB/search",
            {"category": cat_id, "limit": limite, "offset": pagina * limite},
            token,
        )
        if status != 200 or not dados:
            break
        itens = dados.get("results", [])
        if not itens:
            break
        for item in itens:
            if promo := _para_promocao(item, categoria_nome):
                resultado.append(promo)
        time.sleep(0.5)
    logger.info("ML API [busca]: %d promoções encontradas em [%s]", len(resultado), categoria_nome)
    return resultado


def _via_highlights(cat_id: str, categoria_nome: str, token: str) -> List[Dict]:
    status, dados = _get_api(f"/highlights/MLB/category/{cat_id}", {}, token)
    if status != 200 or not dados:
        return []
    ids = [c.get("id") for c in dados.get("content", []) if c.get("type") == "ITEM" and c.get("id")]
    
    resultado = []
    for i in range(0, len(ids), 20):
        lote = ids[i:i + 20]
        status, itens = _get_api("/items", {"ids": ",".join(lote)}, token)
        if status != 200 or not isinstance(itens, list):
            continue
        for entrada in itens:
            if entrada.get("code") == 200 and (corpo := entrada.get("body")):
                if promo := _para_promocao(corpo, categoria_nome):
                    resultado.append(promo)
    logger.info("ML API [highlights]: %d promoções encontradas em [%s]", len(resultado), categoria_nome)
    return resultado


# ==============================================================
# SCRAPER DE FALLBACK (curl_cffi)
# ==============================================================
def _obter_html_cffi(url: str, tentativas: int = 3) -> Optional[str]:
    cookie = (getattr(config, "MELI_COOKIE_HEADER", "") or "").strip()
    for tentativa in range(1, tentativas + 1):
        try:
            resposta = cffi_requests.get(
                url,
                impersonate="chrome",
                timeout=20,
                allow_redirects=True,
                headers={"Cookie": cookie} if cookie else {}
            )
            if resposta.status_code == 200 and "captcha" not in resposta.url:
                return resposta.text
            logger.warning("ML CFFI: Bloqueio/Captcha detectado em %s", url)
        except Exception as erro:
            logger.warning("ML CFFI: Erro em %s: %s", url, erro)
        time.sleep(2 * tentativa)
    return None


def _buscar_ofertas_scraper(url_categoria: Optional[str] = None, max_paginas: Optional[int] = None) -> List[Dict]:
    paginas = max_paginas or getattr(config, "SCRAPER_MAX_PAGINAS", 3)
    promocoes = []
    base_url = url_categoria or getattr(config, "MERCADO_LIVRE_OFERTAS_URL", f"{BASE_URL}/ofertas")
    categoria_nome = next((n["nome"] for n in NICHOS_ESTRATEGICOS if n["url"] == url_categoria), "Ofertas")

    for pagina in range(1, paginas + 1):
        url = f"{base_url}&page={pagina}" if "?" in base_url else f"{base_url}?page={pagina}"
        html = _obter_html_cffi(url)
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
            titulo = card.select_one(_SELETORES["titulo"][0])
            if titulo and (promo := _para_promocao({"title": titulo.text, "permalink": BASE_URL, "price": 100}, categoria_nome)):
                promocoes.append(promo)

    return promocoes


# ==============================================================
# PONTO DE ENTRADA UNIFICADO
# ==============================================================
def buscar_ofertas(url_categoria: Optional[str] = None, max_paginas: Optional[int] = None) -> List[Dict]:
    """
    Executa a busca de ofertas. Se ML_USAR_API for True, consome a API oficial OAuth.
    Caso contrário ou se a API falhar, recorre ao scraper de fallback.
    """
    categoria_nome = next((n["nome"] for n in NICHOS_ESTRATEGICOS if n["url"] == url_categoria), "Ofertas")
    cat_id = _id_categoria(url_categoria)
    paginas = max_paginas or getattr(config, "SCRAPER_MAX_PAGINAS", 3)

    # Verifica se o uso da API Oficial está ativo
    if _env_bool("ML_USAR_API", True):
        logger.info("ML API: Iniciando busca [%s] (Categoria: %s)", categoria_nome, cat_id)
        token = _obter_token()
        
        if token and cat_id:
            # Tenta via Busca por Categoria
            promocoes = _via_busca(cat_id, categoria_nome, token, paginas)
            if promocoes:
                return promocoes

            # Tenta via Highlights/Destaques
            promocoes = _via_highlights(cat_id, categoria_nome, token)
            if promocoes:
                return promocoes
        elif not cat_id:
            logger.warning("ML API: Não foi possível identificar o ID da categoria na URL %r", url_categoria)

        logger.warning("ML API: Nenhum produto retornado pela API oficial para [%s]; tentando scraper.", categoria_nome)

    # Fallback para o scraper
    try:
        return _buscar_ofertas_scraper(url_categoria, max_paginas)
    except Exception as erro:
        logger.error("ML: Scraper de fallback falhou: %s", erro)
        return []