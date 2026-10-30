"""
Geração de links de afiliado do Mercado Livre via API interna do linkbuilder.

IMPORTANTE: usa a sessão do seu navegador (CSRF + cookie). Ela EXPIRA. Quando
isso acontece, `gerar_link_afiliado` devolve None e `sessao_expirada()` fica True.
O cookie é credencial da sua conta: nunca imprima nem versione.
"""

import logging
import os
import time
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse, urlunparse

import requests

from app import config

logger = logging.getLogger(__name__)

API_URL = "https://www.mercadolivre.com.br/affiliate-program/api/v2/affiliates/createLink"

_sessao_expirada = False


def sessao_expirada() -> bool:
    """True se a última chamada indicou cookie/CSRF vencido."""
    return _sessao_expirada


def _cfg(chave: str, padrao: str = "") -> str:
    return getattr(config, chave, None) or os.getenv(chave, padrao)


def _url_real_ml(url: str) -> Optional[str]:
    """
    Troca links de rastreio de anúncios (click1.mercadolivre.com.br/mclics/...)
    pela URL real do produto, que fica dentro do parâmetro `url=`.
    Devolve None se o link de rastreio não trouxer o destino ou se não for do Mercado Livre.
    """
    if not url:
        return None
    partes = urlparse(url.strip())
    if "/mclics/" in partes.path or partes.netloc.lower().startswith("click"):
        destino = (parse_qs(partes.query).get("url") or [None])[0]
        if not destino:
            return None
        if destino.lower().startswith(("http%", "https%")):  # codificado duas vezes
            destino = unquote(destino)
        partes = urlparse(destino)
        if "/mclics/" in partes.path or partes.netloc.lower().startswith("click"):
            return None
    if not partes.netloc.lower().endswith("mercadolivre.com.br"):
        return None
    return partes._replace(fragment="").geturl()


def limpar_url(url: str) -> str:
    """Remove parâmetros e âncoras (#reviews, etc.) para evitar rejeição da API."""
    if not url:
        return url
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))


def gerar_link_afiliado(url_produto: str, usar_link_curto: bool = True) -> Optional[str]:
    """
    Retorna o link de afiliado ou None em qualquer falha.
    NUNCA devolve a URL original: quem chama decide o que fazer sem o link.
    """
    global _sessao_expirada

    tag = _cfg("MELI_AFFILIATE_TAG")
    csrf = _cfg("MELI_CSRF_TOKEN")
    cookie = _cfg("MELI_COOKIE_HEADER")

    if not (tag and csrf and cookie):
        logger.error(
            "Afiliado ML não configurado (MELI_AFFILIATE_TAG, MELI_CSRF_TOKEN, MELI_COOKIE_HEADER)."
        )
        return None

    # Resolve links de rastreio de anúncios ANTES de limpar a URL
    # (a limpeza apaga o parâmetro url= onde está o produto de verdade)
    url_real = _url_real_ml(url_produto)
    if not url_real:
        logger.warning("Afiliado ML: link de rastreio sem destino, produto descartado.")
        return None
    url_limpa = limpar_url(url_real)

    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "content-type": "application/json",
        "origin": "https://www.mercadolivre.com.br",
        "referer": "https://www.mercadolivre.com.br/afiliados/linkbuilder",
        "user-agent": getattr(config, "SCRAPER_USER_AGENT", "Mozilla/5.0"),
        "x-csrf-token": csrf,
        "cookie": cookie,
    }
    payload = {"urls": [url_limpa], "tag": tag}

    for tentativa in range(1, 3):
        try:
            resp = requests.post(API_URL, json=payload, headers=headers, timeout=10)
        except requests.RequestException as erro:
            logger.warning(
                "Afiliado ML: erro de rede (%s), tentativa %d/2", type(erro).__name__, tentativa
            )
            time.sleep(2)
            continue

        if resp.status_code in (401, 403):
            if not _sessao_expirada:
                logger.critical(
                    "Afiliado ML: sessão expirada (HTTP %d). "
                    "Renove MELI_CSRF_TOKEN e MELI_COOKIE_HEADER no .env.",
                    resp.status_code,
                )
            _sessao_expirada = True
            return None

        if resp.status_code == 429 or resp.status_code >= 500:
            logger.warning("Afiliado ML: HTTP %d, tentativa %d/2", resp.status_code, tentativa)
            time.sleep(3)
            continue

        if resp.status_code in (200, 201):
            try:
                urls = resp.json().get("urls") or []
            except ValueError:
                urls = []
            if urls:
                item = urls[0]
                curto, longo = item.get("short_url"), item.get("long_url")
                link = (curto or longo) if usar_link_curto else (longo or curto)
                if link and link != url_limpa:
                    _sessao_expirada = False
                    return link

        logger.error(
            "Afiliado ML: resposta inesperada (HTTP %d): %s", resp.status_code, resp.text[:200]
        )
        return None

    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    url_teste = (
        "https://www.mercadolivre.com.br/mesa-de-computador-escrivaninha-preta-"
        "pe-metalon-industrial-120x60-jm3-moveis/p/MLB29873777#reviews"
    )
    print("--- TESTE DE GERAÇÃO DE LINK ---")
    link = gerar_link_afiliado(url_teste)
    if link:
        print("OK, LINK GERADO:", link)
    else:
        print("FALHOU: veja a mensagem de erro acima (sessão expirada, variável ausente ou resposta inesperada).")