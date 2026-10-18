"""
app/confianca.py
Enriquece ofertas do Mercado Livre com dados de confiança (API pública) e
descarta as de vendedores fracos ou anúncios inativos.

Roda só nos FINALISTAS de cada ciclo (poucas requisições), não em todas as ofertas.

Campos que ele adiciona na promo (quando a API devolve):
    item_id, dados_confianca (bool), vendas, estoque, loja_oficial,
    mercadolider ("silver"|"gold"|"platinum"), nota, avaliacoes,
    frete_gratis, full

Configuração (opcional, via config.py/.env; sem isso usa os padrões abaixo):
    CONFIANCA_ATIVA, CONFIANCA_EXIGIR_SELO, CONFIANCA_LIDER_MINIMO,
    CONFIANCA_MIN_VENDAS, CONFIANCA_MIN_NOTA, CONFIANCA_MIN_AVALIACOES

Teste isolado (antes de ligar no bot):
    python -m app.confianca MLB1234567890
"""

import logging
import re
import time
from collections import Counter
from typing import Dict, List, Optional, Tuple

import requests

from app import config

logger = logging.getLogger(__name__)

API = "https://api.mercadolibre.com"
_SESSAO = requests.Session()
_CACHE: Dict[str, Tuple[float, dict]] = {}
_CACHE_TTL_S = 30 * 60
_ORDEM_LIDER = {"silver": 1, "gold": 2, "platinum": 3}

_RE_ITEM_FILTRO = re.compile(r"item_id[:=](MLB\d+)")
_RE_WID = re.compile(r"[?&]wid=(MLB\d+)")
_RE_MLB = re.compile(r"(?<![A-Za-z])MLB-?(\d{8,})")  # não casa MLBU (catálogo)


def _cfg(nome: str, padrao):
    return getattr(config, nome, padrao)


# ------------------------------------------------------------------ API
def _get_json(caminho: str) -> Optional[dict]:
    agora = time.time()
    em_cache = _CACHE.get(caminho)
    if em_cache and agora - em_cache[0] < _CACHE_TTL_S:
        return em_cache[1]

    headers = {
        "User-Agent": _cfg("SCRAPER_USER_AGENT", "Mozilla/5.0"),
        "Accept": "application/json",
    }
    # Sem cookie: estas consultas são públicas e não devem usar a sua sessão logada.
    for tentativa in (1, 2):
        try:
            r = _SESSAO.get(f"{API}{caminho}", headers=headers, timeout=10)
            if r.status_code == 200:
                dados = r.json()
                _CACHE[caminho] = (agora, dados)
                time.sleep(0.3)
                return dados
            if r.status_code in (401, 403):
                logger.warning("API do ML negou acesso (%s) em %s", r.status_code, caminho)
                return None
            if r.status_code == 404:
                return None
        except (requests.RequestException, ValueError) as erro:
            logger.debug("Falha em %s: %s", caminho, erro)
        time.sleep(1.0 * tentativa)
    return None


def extrair_item_id(url: str, produto_id: Optional[str] = None) -> Optional[str]:
    """ID do anúncio (MLB123...). IDs de catálogo (MLBU...) não servem na API de itens."""
    url = url or ""
    for regex in (_RE_ITEM_FILTRO, _RE_WID):
        if m := regex.search(url):
            return m.group(1)
    for texto in (url.split("?")[0], produto_id or ""):
        if m := _RE_MLB.search(texto):
            return "MLB" + m.group(1)
    return None


# ------------------------------------------------------- enriquecimento
def enriquecer(promo: dict) -> dict:
    if "dados_confianca" in promo:
        return promo

    promo["dados_confianca"] = False
    item_id = extrair_item_id(promo.get("url_produto", ""), promo.get("produto_id"))
    promo["item_id"] = item_id
    if not item_id:
        return promo

    item = _get_json(f"/items/{item_id}")
    if not item:
        return promo

    promo["dados_confianca"] = True
    promo["status_anuncio"] = item.get("status")
    promo["estoque"] = item.get("available_quantity")
    promo["vendas"] = item.get("sold_quantity")
    promo["loja_oficial"] = bool(item.get("official_store_id"))
    envio = item.get("shipping") or {}
    promo["frete_gratis"] = bool(envio.get("free_shipping"))
    promo["full"] = envio.get("logistic_type") == "fulfillment"

    if seller_id := item.get("seller_id"):
        vendedor = _get_json(f"/users/{seller_id}") or {}
        rep = vendedor.get("seller_reputation") or {}
        nivel = (rep.get("power_seller_status") or "").lower()
        promo["mercadolider"] = nivel if nivel in _ORDEM_LIDER else None

    reviews = _get_json(f"/reviews/item/{item_id}")
    if reviews:
        promo["nota"] = reviews.get("rating_average")
        promo["avaliacoes"] = (reviews.get("paging") or {}).get("total")

    return promo


# -------------------------------------------------------------- decisão
def selo_vendedor(promo: dict) -> Optional[str]:
    if promo.get("loja_oficial"):
        return "Loja Oficial"
    return {
        "platinum": "MercadoLíder Platinum",
        "gold": "MercadoLíder Gold",
        "silver": "MercadoLíder",
    }.get(promo.get("mercadolider") or "")


def formatar_vendas(n) -> Optional[str]:
    """520 -> '+500 vendidos' (a API pública devolve valores aproximados)."""
    if not n:
        return None
    if n < 50:
        return f"{n} vendidos"
    if n < 1000:
        faixa = 50 if n < 100 else (100 if n < 500 else 500)
        return f"+{(n // faixa) * faixa} vendidos"
    return f"+{n // 1000} mil vendidos"


def aprovar(promo: dict) -> Tuple[bool, str]:
    if not promo.get("dados_confianca"):
        return False, "sem dados da API"
    if promo.get("status_anuncio") not in (None, "active"):
        return False, "anúncio inativo"
    estoque = promo.get("estoque")
    if estoque is not None and estoque <= 0:
        return False, "sem estoque"

    if _cfg("CONFIANCA_EXIGIR_SELO", True):
        nivel_min = _ORDEM_LIDER.get(str(_cfg("CONFIANCA_LIDER_MINIMO", "gold")).lower(), 2)
        nivel = _ORDEM_LIDER.get(promo.get("mercadolider") or "", 0)
        if not (promo.get("loja_oficial") or nivel >= nivel_min):
            return False, "vendedor sem selo"

    vendas = promo.get("vendas")
    if vendas is not None and vendas < _cfg("CONFIANCA_MIN_VENDAS", 50):
        return False, "poucas vendas"
    avaliacoes = promo.get("avaliacoes")
    if avaliacoes is not None and avaliacoes < _cfg("CONFIANCA_MIN_AVALIACOES", 20):
        return False, "poucas avaliações"
    nota = promo.get("nota")
    if nota is not None and avaliacoes and nota < _cfg("CONFIANCA_MIN_NOTA", 4.5):
        return False, "nota baixa"
    return True, "ok"


def filtrar_confiaveis(promos: List[dict], maximo: Optional[int] = None) -> List[dict]:
    """Consulta a API na ordem recebida e para quando juntar `maximo` aprovadas."""
    if not _cfg("CONFIANCA_ATIVA", True):
        return promos[:maximo] if maximo else promos

    aprovadas: List[dict] = []
    motivos: Counter = Counter()
    analisadas = 0
    for promo in promos:
        if maximo and len(aprovadas) >= maximo:
            break
        analisadas += 1
        enriquecer(promo)
        ok, motivo = aprovar(promo)
        if ok:
            aprovadas.append(promo)
        else:
            motivos[motivo] += 1
            logger.info("Descartada (%s): %s", motivo, promo.get("titulo"))

    logger.info(
        "Confiança: %d aprovadas de %d analisadas. Descartes: %s",
        len(aprovadas), analisadas, dict(motivos) or "nenhum",
    )
    if analisadas and motivos.get("sem dados da API", 0) == analisadas:
        logger.error(
            "A API do ML não devolveu dados para NENHUMA oferta. Rode "
            "`python -m app.confianca MLB...` pra ver o que ela responde."
        )
    return aprovadas


# ---------------------------------------------------------- teste manual
if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    alvo = sys.argv[1] if len(sys.argv) > 1 else ""
    promo = {"url_produto": alvo, "produto_id": alvo}
    enriquecer(promo)
    print(json.dumps(promo, indent=2, ensure_ascii=False, default=str))
    print("Decisão:", aprovar(promo), "| selo:", selo_vendedor(promo),
          "|", formatar_vendas(promo.get("vendas")))