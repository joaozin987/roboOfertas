"""
Camada de comunicação com o Mercado Livre (Requests + Cookies do .env + URLs Públicas).
"""

import logging
import os
import random
import re
import time
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app import config, whatsapp
from app.afiliados import gerar_link_afiliado

logger = logging.getLogger(__name__)
BASE_URL = "https://www.mercadolivre.com.br"
_proxima_busca_http = 0.0
_alerta_verificacao_entregue = False
INTERVALO_VERIFICACAO_S = 30 * 60


def _preco_maximo() -> float:
    # Prioridade: ML_PRECO_MAXIMO -> PRECO_MAXIMO -> config -> 900
    valor = os.getenv("ML_PRECO_MAXIMO") or os.getenv("PRECO_MAXIMO") or getattr(config, "ML_PRECO_MAXIMO", 900.0)
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 900.0


NICHOS_ESTRATEGICOS = [
    # --- nichos originais ---
    {"nome": "Smartphones & Celulares", "url": "https://lista.mercadolivre.com.br/celulares-smartphones_NoIndex_True"},
    {"nome": "Moda & Calçados", "url": "https://lista.mercadolivre.com.br/calcados-roupas_NoIndex_True"},
    {"nome": "Corrida & Esportes", "url": "https://lista.mercadolivre.com.br/esportes-fitness_NoIndex_True"},
    {"nome": "Informática & Games", "url": "https://lista.mercadolivre.com.br/informatica-games_NoIndex_True"},
    {"nome": "Casa & Eletrodomésticos", "url": "https://lista.mercadolivre.com.br/eletrodomesticos_NoIndex_True"},
    {"nome": "Beleza & Cuidados", "url": "https://lista.mercadolivre.com.br/beleza-cuidado-pessoal_NoIndex_True"},
    # --- novos nichos ---
    {"nome": "Perfumes & Fragrâncias", "url": "https://lista.mercadolivre.com.br/perfumes_NoIndex_True"},
    {"nome": "Maquiagem & Skincare", "url": "https://lista.mercadolivre.com.br/maquiagem_NoIndex_True"},
    {"nome": "Relógios & Acessórios", "url": "https://lista.mercadolivre.com.br/relogios_NoIndex_True"},
    {"nome": "Áudio & Fones", "url": "https://lista.mercadolivre.com.br/fone-bluetooth_NoIndex_True"},
    {"nome": "Brinquedos & Infantil", "url": "https://lista.mercadolivre.com.br/brinquedos_NoIndex_True"},
    {"nome": "Bebê & Maternidade", "url": "https://lista.mercadolivre.com.br/bebe_NoIndex_True"},
    {"nome": "Pet Shop", "url": "https://lista.mercadolivre.com.br/pet-shop_NoIndex_True"},
    {"nome": "Ferramentas & Construção", "url": "https://lista.mercadolivre.com.br/ferramentas_NoIndex_True"},
    {"nome": "Automotivo", "url": "https://lista.mercadolivre.com.br/acessorios-automotivos_NoIndex_True"},
    {"nome": "Cozinha & Utensílios", "url": "https://lista.mercadolivre.com.br/utensilios-cozinha_NoIndex_True"},
    {"nome": "Cama, Mesa & Banho", "url": "https://lista.mercadolivre.com.br/cama-mesa-banho_NoIndex_True"},
    {"nome": "Móveis & Decoração", "url": "https://lista.mercadolivre.com.br/decoracao-casa_NoIndex_True"},
    {"nome": "Suplementos & Saúde", "url": "https://lista.mercadolivre.com.br/suplementos_NoIndex_True"},
    {"nome": "Segurança & Casa Inteligente", "url": "https://lista.mercadolivre.com.br/camera-seguranca_NoIndex_True"},
]

_SELETORES = {
    "card": ["div.andes-card.poly-card", "div.poly-card", "li.promotion-item", "li.ui-search-layout__item", "div.ui-search-result__wrapper"],
    "titulo": ["a.poly-component__title", "h2.poly-component__title", "a.promotion-item__link", "h2.ui-search-item__title", "a.ui-search-link"],
    "link": ["a.poly-component__title", "a.promotion-item__link", "a.ui-search-link", "a.ui-search-item__group__element"],
    "imagem": ["img.poly-component__picture", "img.promotion-item__img", "img.ui-search-result-image__element"],
    "preco_atual": ["div.poly-price__current span.andes-money-amount", "div.ui-search-price__second-line span.andes-money-amount", "div.ui-search-price--size-medium span.andes-money-amount"],
    "preco_anterior": ["s.andes-money-amount--previous", "span.promotion-item__price-previous", "s.ui-search-price__part--medium", "s.ui-search-price__part"],
}

TERMOS_OBRIGATORIOS_POR_CATEGORIA = {
    # --- nichos originais (perfume e suplementos saíram daqui para não duplicar) ---
    "Moda & Calçados": ["tênis", "sapato", "camisa", "camiseta", "calça", "bermuda", "sandália", "chinelo", "mochila"],
    "Smartphones & Celulares": ["smartphone", "celular", "iphone", "samsung", "galaxy", "xiaomi", "motorola", "moto"],
    "Corrida & Esportes": ["tênis", "corrida", "esporte", "academia", "treino", "chuteira", "bicicleta"],
    "Informática & Games": ["notebook", "laptop", "placa de vídeo", "processador", "monitor", "teclado", "mouse", "headset", "ssd", "gamer"],
    "Casa & Eletrodomésticos": ["air fryer", "liquidificador", "aspirador", "panela", "ventilador", "cafeteira", "micro-ondas"],
    "Beleza & Cuidados": ["desodorante", "creme", "shampoo", "condicionador", "secador", "prancha", "barbeador", "escova"],
    # --- novos nichos ---
    "Perfumes & Fragrâncias": ["perfume", "colônia", "colonia", "eau de parfum", "eau de toilette", "parfum", "toilette", "fragrância", "fragrancia", "body splash"],
    "Maquiagem & Skincare": ["maquiagem", "batom", "base líquida", "base liquida", "rímel", "rimel", "máscara de cílios", "paleta", "sombra", "corretivo", "gloss", "protetor solar", "sérum", "serum", "hidratante", "skincare"],
    "Relógios & Acessórios": ["relógio", "relogio", "smartwatch", "pulseira", "óculos", "oculos", "carteira", "cinto", "bolsa"],
    "Áudio & Fones": ["fone", "headphone", "earbuds", "caixa de som", "soundbar", "bluetooth", "jbl", "airpods"],
    "Brinquedos & Infantil": ["brinquedo", "boneca", "carrinho", "lego", "quebra-cabeça", "quebra-cabeca", "pelúcia", "pelucia", "bloco", "infantil", "massinha"],
    "Bebê & Maternidade": ["bebê", "bebe", "fralda", "mamadeira", "berço", "berco", "chupeta", "babá eletrônica", "enxoval", "carrinho de bebê"],
    "Pet Shop": ["ração", "racao", "pet", "cachorro", "gato", "coleira", "petisco", "areia higiênica", "areia higienica", "cama pet"],
    "Ferramentas & Construção": ["furadeira", "parafusadeira", "chave", "alicate", "serra", "esmerilhadeira", "lixadeira", "jogo de ferramentas", "maleta", "trena"],
    "Automotivo": ["automotivo", "veicular", "carro", "pneu", "óleo", "oleo", "farol", "limpador", "tapete", "capacete", "moto"],
    "Cozinha & Utensílios": ["panela", "frigideira", "faca", "pote", "marmita", "garrafa térmica", "garrafa termica", "copo", "assadeira", "tábua", "tabua", "organizador", "kit"],
    "Cama, Mesa & Banho": ["lençol", "lencol", "edredom", "cobertor", "toalha", "travesseiro", "colcha", "fronha", "manta", "jogo de cama"],
    "Móveis & Decoração": ["decoração", "decoracao", "quadro", "luminária", "luminaria", "espelho", "prateleira", "estante", "cadeira", "poltrona", "rack", "sofá", "sofa", "puff"],
    "Suplementos & Saúde": ["whey", "creatina", "vitamina", "colágeno", "colageno", "ômega", "omega", "pré-treino", "pre-treino", "proteína", "proteina", "multivitamínico", "bcaa", "suplemento"],
    "Segurança & Casa Inteligente": ["câmera", "camera", "wifi", "wi-fi", "fechadura", "inteligente", "sensor", "alarme", "interfone", "smart"],
}


def _termo_no_titulo(termo: str, titulo_lower: str) -> bool:
    # Termos curtos (até 4 letras) só valem como palavra inteira, aceitando plural:
    # evita "pet" casar com "tapete" ou "kit" com "skit".
    if len(termo) <= 4:
        return re.search(rf"(?<!\w){re.escape(termo)}(?:s|es)?(?!\w)", titulo_lower) is not None
    return termo in titulo_lower


def _validar_relevancia_titulo(titulo: str, categoria_nome: str) -> bool:
    if not titulo:
        return False
    titulo_lower = titulo.lower()
    termos = TERMOS_OBRIGATORIOS_POR_CATEGORIA.get(categoria_nome, [])
    if not termos:
        return True
    return any(_termo_no_titulo(termo, titulo_lower) for termo in termos)


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


def _obter_headers_com_cookies() -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    cookie_header = (getattr(config, "MELI_COOKIE_HEADER", "") or os.getenv("MELI_COOKIE_HEADER", "") or "").strip()
    if cookie_header:
        headers["Cookie"] = cookie_header
    return headers


def _extrair_promocao(card, categoria_nome: str = "Destaques") -> Optional[dict]:
    titulo = _primeiro_texto(card, _SELETORES["titulo"])
    url_produto = _primeiro_atributo(card, _SELETORES["link"], "href")
    preco_atual = _primeiro_preco(card, _SELETORES["preco_atual"])
    preco_anterior = _primeiro_preco(card, _SELETORES["preco_anterior"])

    if not titulo or not url_produto or preco_atual is None:
        return None

    if not _validar_relevancia_titulo(titulo, categoria_nome):
        return None

    if preco_atual > _preco_maximo():
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
        sufixo = "_NoIndex_True"
        if url_limpa.endswith(sufixo):
            # Formato do próprio site: ..._Desde_49_NoIndex_True
            return f"{url_limpa[:-len(sufixo)]}_Desde_{desde}{sufixo}"
        return f"{url_limpa}_Desde_{desde}"
    divisor = "&" if "?" in url_limpa else "?"
    return f"{url_limpa}{divisor}page={pagina}"


def _url_indica_verificacao(url: str) -> bool:
    url_lower = url.lower()
    return any(indicador in url_lower for indicador in ("account-verification", "captcha", "/login", "/gz/"))


def buscar_ofertas(url_categoria: Optional[str] = None, max_paginas: Optional[int] = None) -> List[Dict]:
    """Busca ofertas no Mercado Livre via requisições HTTP requests + cookies injetados."""
    global _proxima_busca_http, _alerta_verificacao_entregue
    if time.monotonic() < _proxima_busca_http:
        return []

    paginas_para_buscar = max_paginas or getattr(config, "SCRAPER_MAX_PAGINAS", 3)
    promocoes = []
    vistos = set()
    base_url = url_categoria or getattr(config, "MERCADO_LIVRE_OFERTAS_URL", f"{BASE_URL}/ofertas")

    categoria_nome = next((n["nome"] for n in NICHOS_ESTRATEGICOS if n["url"] == url_categoria), "Ofertas")
    pagina_inicial = 1

    logger.info("ML HTTP: iniciando busca [%s] | páginas=%d | preço máx R$ %s", categoria_nome, paginas_para_buscar, _preco_maximo())
    headers = _obter_headers_com_cookies()

    for pagina in range(pagina_inicial, pagina_inicial + paginas_para_buscar):
        url = _montar_url_paginada(base_url, pagina)
        try:
            response = requests.get(url, headers=headers, timeout=20)
            if _url_indica_verificacao(response.url):
                _proxima_busca_http = time.monotonic() + INTERVALO_VERIFICACAO_S
                logger.warning(
                    "ML HTTP: acesso redirecionado para verificação de conta; "
                    "use coletar_ml.py no navegador para atualizar as ofertas."
                )
                if not _alerta_verificacao_entregue:
                    _alerta_verificacao_entregue = whatsapp.enviar_alerta_privado(
                        "Robô de Ofertas: Mercado Livre solicitou verificação de conta. "
                        "A busca HTTP foi pausada por 30 minutos. Confira a conta pelo canal oficial."
                    )
                break
            if response.status_code != 200:
                logger.warning("ML HTTP status %d em %s", response.status_code, url)
                break

            html = response.text
            soup = BeautifulSoup(html, "html.parser")

            cards = []
            for seletor in _SELETORES["card"]:
                if encontrados := soup.select(seletor):
                    cards = encontrados
                    break

            if not cards:
                logger.warning(
                    "ML HTTP: nenhum card encontrado em %s (possível mudança de página ou bloqueio; %d bytes)",
                    url,
                    len(html),
                )
                break

            for card in cards:
                if promocao := _extrair_promocao(card, categoria_nome=categoria_nome):
                    # Evita o mesmo produto repetido entre páginas (ignora parâmetros de rastreio)
                    chave = promocao["url_produto"].split("?")[0].split("#")[0]
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    promocoes.append(promocao)

            time.sleep(getattr(config, "SCRAPER_REQUEST_DELAY_SECONDS", 2) + random.random())

        except Exception as err:
            logger.error("Erro ao raspar Mercado Livre via HTTP: %s", err)
            break

    if promocoes and time.monotonic() >= _proxima_busca_http and _alerta_verificacao_entregue:
        _alerta_verificacao_entregue = False
        whatsapp.enviar_alerta_privado("Robô de Ofertas: a busca HTTP do Mercado Livre voltou a encontrar ofertas.")
    logger.info("ML HTTP: %d promoções extraídas com sucesso em [%s]", len(promocoes), categoria_nome)
    return promocoes
