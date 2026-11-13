"""
Envio de ofertas para o grupo do WhatsApp via Evolution API (v2).
"""

import logging
import os
import re

import requests

from app import config

logger = logging.getLogger(__name__)


def _obter_config() -> dict:
    """Recupera as variáveis em tempo de execução (ambiente primeiro, depois config.py)."""

    def _valor(chave: str, padrao: str = "") -> str:
        return (os.getenv(chave) or getattr(config, chave, "") or padrao).strip()

    return {
        "url": _valor("WHATSAPP_API_URL").rstrip("/"),
        "key": _valor("WHATSAPP_API_KEY"),
        "instance": _valor("WHATSAPP_INSTANCE", "robo_ofertas"),
        "group_jid": _valor("WHATSAPP_GROUP_JID"),
    }


def _configurado(cfg: dict) -> bool:
    if not (cfg["url"] and cfg["group_jid"] and cfg["key"]):
        logger.warning("[WhatsApp] Configurações ausentes (URL, API KEY ou Group JID). Canal ignorado.")
        return False
    return True


def _get_headers(api_key: str) -> dict:
    return {"apikey": api_key, "Content-Type": "application/json"}


def _post(endpoint: str, payload: dict, api_key: str, timeout: int, rotulo: str, *, privado: bool = False) -> bool:
    try:
        resposta = requests.post(
            endpoint, json=payload, headers=_get_headers(api_key), timeout=timeout
        )
    except requests.exceptions.ReadTimeout:
        if privado:
            logger.warning("[WhatsApp] Entrega do alerta privado não confirmada (timeout).")
            return False
        # A Evolution recebeu o pedido mas demorou a responder (comum ao baixar a imagem):
        # provavelmente entregou. Retornar False dispararia o texto e o grupo veria a oferta duas vezes.
        logger.warning(
            "[WhatsApp] Timeout de leitura ao enviar %s. Assumindo entregue para evitar duplicata.",
            rotulo,
        )
        return True
    except requests.RequestException as erro:
        logger.error("[WhatsApp] Falha de rede ao enviar %s: %s", rotulo, type(erro).__name__)
        return False

    if resposta.status_code in (200, 201):
        logger.info("[WhatsApp] %s enviado com sucesso.", rotulo.capitalize())
        return True

    logger.error(
        "[WhatsApp] Erro ao enviar %s. Status: %s - %s",
        rotulo, resposta.status_code, "" if privado else resposta.text[:300],
    )
    return False


def enviar_alerta_privado(texto: str) -> bool:
    """Envia um alerta usando exclusivamente o número administrativo."""
    if getattr(config, "TEST_MODE", False):
        logger.info("[WhatsApp] Alerta privado simulado (TEST_MODE=true).")
        return True

    numero = os.getenv("WHATSAPP_ADMIN_NUMBER", "").strip().removeprefix("+")
    cfg = _obter_config()
    if not re.fullmatch(r"[1-9][0-9]{7,14}", numero) or not (cfg["url"] and cfg["key"]):
        logger.warning("[WhatsApp] Alerta privado indisponível. Confira o número e a configuração da Evolution.")
        return False

    endpoint = f"{cfg['url']}/message/sendText/{cfg['instance']}"
    payload = {"number": numero, "text": texto, "linkPreview": False}
    return _post(endpoint, payload, cfg["key"], timeout=5, rotulo="alerta privado", privado=True)


def enviar_mensagem(texto: str) -> bool:
    """Envia mensagem de texto puro para o grupo do WhatsApp."""
    if getattr(config, "TEST_MODE", False):
        print("[TESTE] Mensagem que seria enviada ao WhatsApp:\n")
        print(texto)
        print("\nNão publicado no WhatsApp (TEST_MODE=true).")
        return True

    cfg = _obter_config()
    if not _configurado(cfg):
        return False

    endpoint = f"{cfg['url']}/message/sendText/{cfg['instance']}"
    payload = {"number": cfg["group_jid"], "text": texto, "linkPreview": True}
    return _post(endpoint, payload, cfg["key"], timeout=15, rotulo="texto")


def enviar_foto(url_imagem: str, legenda: str) -> bool:
    """Envia imagem com legenda para o grupo do WhatsApp (Evolution API v2)."""
    if getattr(config, "TEST_MODE", False):
        print("[TESTE] Foto + mensagem que seriam enviadas ao WhatsApp:\n")
        print(f"[imagem: {url_imagem}]\n")
        print(legenda)
        print("\nNão publicado no WhatsApp (TEST_MODE=true).")
        return True

    cfg = _obter_config()
    if not _configurado(cfg):
        return False

    endpoint = f"{cfg['url']}/message/sendMedia/{cfg['instance']}"
    payload = {
        "number": cfg["group_jid"],
        "media": url_imagem,
        "mediatype": "image",
        "caption": legenda,
    }
    return _post(endpoint, payload, cfg["key"], timeout=25, rotulo="imagem")
