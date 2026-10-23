"""
Camada de comunicação com o Mercado Livre.

buscar_ofertas() tenta primeiro a API OFICIAL (busca por categoria, depois mais vendidos
em lote) e só cai no scraping de HTML como último recurso, pois o site bloqueia o robô
com a tela de verificação (account-verification).

Versão com logs de diagnóstico: todo ponto que antes desistia em silêncio
(sem HTML, sem cards, status inesperado, erro de rede) agora registra o motivo.
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

from app import config
from app.afiliados import gerar_link_afiliado

logger = logging.getLogger(__name__)
BASE_URL = "https://www.mercadolivre.com.br"


def _preco_maximo() -> float:
    """Preço máximo aceito no ML: variável ML_PRECO_MAXIMO do .env > config > 900."""
    try:
        return float(os.getenv("ML_PRECO_MAXIMO") or getattr(config, "ML_PRECO_MAXIMO", 900.0))
    except (TypeError, ValueError):
        return 900.0

# ==============================================================
# NICHOS ESTRATEGICOS (Com Perfumes Árabes e Nacionais Inclusos)
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
    "Perfumaria Nacional Top": ["boticario", "boticário", "natura", "malbec", "egeo", "kaiak", "essencial", "humor", "perfume", "colônia", "ekos", "quasar", "floratta"],
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
    cookie = (getattr(config, "MELI_COOKIE_HEADER", "") or "").strip()
    if cookie:
        headers["Cookie"] = cookie
    else:
        logger.warning("ML: MELI_COOKIE_HEADER vazio ou ausente no config; requisição sairá sem cookie.")

    for tentativa in range(1, tentativas + 1):
        try:
            resposta = _SESSAO.get(url, headers=headers, timeout=20, allow_redirects=True)
            logger.info(
                "ML GET %s -> %s (final: %s, %d bytes) [tentativa %d/%d]",
                url, resposta.status_code, resposta.url, len(resposta.text), tentativa, tentativas,
            )
            if resposta.status_code == 200:
                return resposta.text
            if resposta.status_code not in (403, 429, 500, 502, 503, 504):
                logger.warning("ML: status %s inesperado em %s; desistindo desta URL.", resposta.status_code, url)
                return None
            logger.warning("ML: status %s (provável bloqueio/instabilidade) em %s; tentando de novo.", resposta.status_code, url)
        except requests.RequestException as erro:
            logger.warning("ML: erro de rede em %s: %s [tentativa %d/%d]", url, erro, tentativa, tentativas)
        time.sleep(2 * tentativa + random.random())

    logger.error("ML: todas as %d tentativas falharam para %s", tentativas, url)
    return None


# ==============================================================
# NAVEGADOR REAL (Playwright) - contorna a tela de "tráfego suspeito"
# ==============================================================
_PW = None
_CTX = None
_PERFIL_DIR = Path(__file__).resolve().parent.parent / "data" / "ml_profile"


def _env_bool(nome: str, padrao: bool) -> bool:
    valor = os.getenv(nome)
    if valor is None or valor.strip() == "":
        return padrao
    return valor.strip().lower() in ("1", "true", "sim", "yes", "on")


def _contexto_navegador():
    """Abre (uma vez) um navegador com perfil salvo em data/ml_profile."""
    global _PW, _CTX
    if _CTX is not None:
        return _CTX
    from playwright.sync_api import sync_playwright

    _PW = sync_playwright().start()
    _PERFIL_DIR.mkdir(parents=True, exist_ok=True)
    headless = _env_bool("ML_HEADLESS", False)
    opcoes = dict(
        user_data_dir=str(_PERFIL_DIR),
        headless=headless,
        locale="pt-BR",
        viewport={"width": 1280, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
    )
    try:
        _CTX = _PW.chromium.launch_persistent_context(channel="chrome", **opcoes)  # Chrome instalado
        logger.info("ML: navegador Chrome aberto (headless=%s, perfil=%s)", headless, _PERFIL_DIR)
    except Exception as erro:
        logger.warning("ML: Chrome não disponível (%s); usando o Chromium do Playwright.", str(erro)[:120])
        _CTX = _PW.chromium.launch_persistent_context(**opcoes)
    return _CTX


def _buscar_pagina_html_navegador(url: str) -> Optional[str]:
    espera_verificacao = int(os.getenv("ML_VERIFICACAO_ESPERA_S", "180"))
    headless = _env_bool("ML_HEADLESS", False)
    try:
        ctx = _contexto_navegador()
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)

            if "account-verification" in page.url:
                if headless:
                    logger.error("ML: caiu na verificação de conta e o navegador está em modo headless. "
                                 "Rode com ML_HEADLESS=false e conclua a verificação na janela.")
                    return None
                logger.warning("ML: verificação de conta detectada. Conclua na janela do navegador "
                               "(aguardando até %ds)...", espera_verificacao)
                limite = time.time() + espera_verificacao
                while time.time() < limite and "account-verification" in page.url:
                    page.wait_for_timeout(2000)
                if "account-verification" in page.url:
                    logger.error("ML: verificação não concluída no prazo.")
                    return None
                logger.info("ML: verificação concluída; seguindo.")

            try:
                page.wait_for_selector(", ".join(_SELETORES["card"]), timeout=15000)
            except Exception:
                logger.warning("ML: nenhum card apareceu em 15s em %s (url final: %s)", url, page.url)

            html = page.content()
            logger.info("ML NAV %s -> %d bytes (final: %s)", url, len(html), page.url)
            return html
        finally:
            page.close()
    except ImportError:
        logger.error("ML: Playwright não instalado. Rode: pip install playwright")
    except Exception as erro:
        logger.error("ML: falha no navegador em %s: %s", url, erro)
    return None


def _obter_html(url: str) -> Optional[str]:
    """Navegador real por padrão; ML_USAR_NAVEGADOR=false volta ao requests."""
    if _env_bool("ML_USAR_NAVEGADOR", True):
        html = _buscar_pagina_html_navegador(url)
        if html:
            return html
        logger.warning("ML: navegador não trouxe HTML; tentando requests como último recurso.")
    return _buscar_pagina_html(url)


def _extrair_promocao(card, categoria_nome: str = "Destaques") -> Optional[dict]:
    titulo = _primeiro_texto(card, _SELETORES["titulo"])
    url_produto = _primeiro_atributo(card, _SELETORES["link"], "href")
    preco_atual = _primeiro_preco(card, _SELETORES["preco_atual"])
    preco_anterior = _primeiro_preco(card, _SELETORES["preco_anterior"])

    if not titulo or not url_produto or preco_atual is None:
        logger.debug("ML: card sem título/link/preço (titulo=%r, link=%r, preco=%r)", titulo, url_produto, preco_atual)
        return None

    # Aplicação da Trava Anti-Lixo
    if not _validar_relevancia_titulo(titulo, categoria_nome):
        logger.warning(f"Descartado por irrelevância em '{categoria_nome}': {titulo}")
        return None

    preco_maximo = _preco_maximo()
    if preco_atual > preco_maximo:
        logger.debug("ML: descartado por preço R$ %.2f > ML_PRECO_MAXIMO R$ %.2f: %s", preco_atual, preco_maximo, titulo)
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


def _buscar_ofertas_scraper(url_categoria: Optional[str] = None, max_paginas: Optional[int] = None) -> List[Dict]:
    paginas_para_buscar = max_paginas or getattr(config, "SCRAPER_MAX_PAGINAS", 3)
    promocoes = []
    base_url = url_categoria or getattr(config, "MERCADO_LIVRE_OFERTAS_URL", f"{BASE_URL}/ofertas")

    categoria_nome = next((n["nome"] for n in NICHOS_ESTRATEGICOS if n["url"] == url_categoria), "Ofertas")
    pagina_inicial = 1 if "lista.mercadolivre.com.br" in base_url else random.choice([1, 2])

    logger.info(
        "ML: iniciando busca [%s] | páginas=%d | preço máx R$ %s",
        categoria_nome, paginas_para_buscar, _preco_maximo(),
    )

    for pagina in range(pagina_inicial, pagina_inicial + paginas_para_buscar):
        url = _montar_url_paginada(base_url, pagina)
        html = _obter_html(url)
        if not html:
            logger.warning("ML: sem HTML para %s; encerrando busca de [%s].", url, categoria_nome)
            break

        soup = BeautifulSoup(html, "html.parser")
        cards = []
        for seletor in _SELETORES["card"]:
            if encontrados := soup.select(seletor):
                cards = encontrados
                logger.info("ML: %d cards encontrados com o seletor %r", len(cards), seletor)
                break

        if not cards:
            titulo_pagina = soup.title.get_text(strip=True) if soup.title else "(sem <title>)"
            logger.warning(
                "ML: nenhum card em %s | <title>: %r | início do HTML: %r",
                url, titulo_pagina, html[:200],
            )
            break

        aceitos = 0
        for card in cards:
            if promocao := _extrair_promocao(card, categoria_nome=categoria_nome):
                promocoes.append(promocao)
                aceitos += 1
        logger.info("ML: página %d de [%s]: %d cards, %d aceitos", pagina, categoria_nome, len(cards), aceitos)

        time.sleep(getattr(config, "SCRAPER_REQUEST_DELAY_SECONDS", 2) + random.random())

    cookie_ok = bool((getattr(config, "MELI_COOKIE_HEADER", "") or "").strip())
    logger.info("ML: %d promoções extraídas em [%s] | cookie %s", len(promocoes), categoria_nome, "ok" if cookie_ok else "VAZIO")
    return promocoes


# ==============================================================
# BUSCA PELA API OFICIAL (caminho principal)
# ==============================================================
API_BASE = "https://api.mercadolibre.com"
_API_CLIENTE = None


# ==============================================================
# TOKEN (reaproveita a sua classe MercadoLivreAPI)
# ==============================================================
def _obter_token() -> Optional[str]:
    """Pega um access_token válido usando a classe OAuth que já existe no projeto."""
    global _API_CLIENTE
    try:
        if _API_CLIENTE is None:
            # AJUSTE O CAMINHO se o arquivo da classe tiver outro nome
            from app.mercado_livre_api import MercadoLivreAPI

            client_id = getattr(config, "ML_CLIENT_ID", None) or os.getenv("ML_CLIENT_ID", "")
            client_secret = getattr(config, "ML_CLIENT_SECRET", None) or os.getenv("ML_CLIENT_SECRET", "")
            redirect_uri = getattr(config, "ML_REDIRECT_URI", None) or os.getenv("ML_REDIRECT_URI", "")
            if not client_id or not client_secret:
                logger.error("ML API: ML_CLIENT_ID / ML_CLIENT_SECRET não encontrados (config ou variáveis de ambiente).")
                return None
            _API_CLIENTE = MercadoLivreAPI(client_id, client_secret, redirect_uri)
        token = _API_CLIENTE.get_token_valido()
        logger.info("ML API: token obtido com sucesso.")
        return token
    except ImportError as erro:
        logger.error("ML API: não consegui importar MercadoLivreAPI (%s). Ajuste o import em _obter_token().", erro)
    except Exception as erro:
        logger.error("ML API: falha ao obter token: %s", erro)
    return None


# ==============================================================
# HTTP COM LOG
# ==============================================================
def _get(caminho: str, params: dict, token: Optional[str], tentativas: int = 2) -> Tuple[Optional[int], Optional[object]]:
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
                logger.warning("ML API: acesso negado em %s: %s", caminho, resp.text[:200])
                return resp.status_code, None
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 * tentativa)
                continue
            logger.warning("ML API: status %s em %s: %s", resp.status_code, caminho, resp.text[:200])
            return resp.status_code, None
        except (requests.RequestException, ValueError) as erro:
            logger.warning("ML API: erro em %s: %s [tentativa %d/%d]", caminho, erro, tentativa, tentativas)
            time.sleep(2 * tentativa)
    return None, None


# ==============================================================
# CONVERSÃO item da API -> formato do bot
# ==============================================================
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
        logger.debug("ML API: descartado por irrelevância em '%s': %s", categoria_nome, titulo)
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
# CAMINHO 1: busca por categoria
# ==============================================================
def _via_busca(cat_id: str, categoria_nome: str, token: str, paginas: int) -> List[Dict]:
    resultado = []
    limite = 50
    for pagina in range(paginas):
        status, dados = _get(
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
        time.sleep(1)
    logger.info("ML API [busca]: %d promoções em [%s]", len(resultado), categoria_nome)
    return resultado


# ==============================================================
# CAMINHO 2: mais vendidos da categoria + detalhes em lote
# ==============================================================
def _via_highlights(cat_id: str, categoria_nome: str, token: str) -> List[Dict]:
    status, dados = _get(f"/highlights/MLB/category/{cat_id}", {}, token)
    if status != 200 or not dados:
        return []
    ids = [c.get("id") for c in dados.get("content", []) if c.get("type") == "ITEM" and c.get("id")]
    logger.info("ML API [highlights]: %d itens listados em [%s]", len(ids), categoria_nome)

    resultado = []
    for i in range(0, len(ids), 20):  # o multiget aceita até 20 ids por chamada
        lote = ids[i:i + 20]
        status, itens = _get("/items", {"ids": ",".join(lote)}, token)
        if status != 200 or not isinstance(itens, list):
            continue
        for entrada in itens:
            if entrada.get("code") == 200 and (corpo := entrada.get("body")):
                if promo := _para_promocao(corpo, categoria_nome):
                    resultado.append(promo)
    logger.info("ML API [highlights]: %d promoções em [%s]", len(resultado), categoria_nome)
    return resultado


# ==============================================================
# PONTO DE ENTRADA (mesma assinatura do scraper)
# ==============================================================
def buscar_ofertas(url_categoria: Optional[str] = None, max_paginas: Optional[int] = None) -> List[Dict]:
    categoria_nome = next((n["nome"] for n in NICHOS_ESTRATEGICOS if n["url"] == url_categoria), "Ofertas")
    cat_id = _id_categoria(url_categoria)
    paginas = max_paginas or getattr(config, "SCRAPER_MAX_PAGINAS", 3)

    if not _env_bool("ML_USAR_API", False):
        # A busca da API está bloqueada (403 PolicyAgent) para este app; vai direto pro navegador.
        return _buscar_ofertas_scraper(url_categoria, max_paginas)

    logger.info("ML API: iniciando busca [%s] (categoria %s)", categoria_nome, cat_id)

    token = _obter_token()
    if token and cat_id:
        promocoes = _via_busca(cat_id, categoria_nome, token, paginas)
        if promocoes:
            return promocoes

        promocoes = _via_highlights(cat_id, categoria_nome, token)
        if promocoes:
            return promocoes
    elif not cat_id:
        logger.warning("ML API: não achei category=MLB... na URL %r; indo pro scraper.", url_categoria)

    logger.warning("ML API: nenhum caminho da API trouxe produtos em [%s]; tentando o scraper antigo.", categoria_nome)
    try:
        return _buscar_ofertas_scraper(url_categoria, max_paginas)
    except Exception as erro:
        logger.error("ML: scraper de fallback também falhou: %s", erro)
        return []