import logging
import os
import requests
from app import config

logger = logging.getLogger(__name__)


def _obter_config():
    """Recupera as variáveis dinamicamente em tempo de execução."""
    return {
        "url": (
            os.getenv("WHATSAPP_API_URL")
            or getattr(config, "WHATSAPP_API_URL", "")
        ).rstrip("/"),
        "key": (
            os.getenv("WHATSAPP_API_KEY")
            or getattr(config, "WHATSAPP_API_KEY", "")
        ),
        "instance": (
            os.getenv("WHATSAPP_INSTANCE")
            or getattr(config, "WHATSAPP_INSTANCE", "robo_ofertas")
        ),
        "group_jid": (
            os.getenv("WHATSAPP_GROUP_JID")
            or getattr(config, "WHATSAPP_GROUP_JID", "")
        ),
    }


def _get_headers(api_key: str) -> dict:
    return {
        "apikey": api_key,
        "Content-Type": "application/json",
    }


def enviar_mensagem(texto: str) -> bool:
    """Envia mensagem de texto puro para o grupo do WhatsApp."""
    cfg = _obter_config()
    if not cfg["url"] or not cfg["group_jid"]:
        logger.warning("[WhatsApp] Configurações ausentes (URL ou Group JID).")
        return False

    endpoint = f"{cfg['url']}/message/sendText/{cfg['instance']}"
    payload = {
        "number": cfg["group_jid"],
        "text": texto,
        "linkPreview": True,
    }

    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers=_get_headers(cfg["key"]),
            timeout=15,
        )
        if response.status_code in [200, 201]:
            logger.info("[WhatsApp] Mensagem de texto enviada com sucesso.")
            return True
        logger.error(
            "[WhatsApp] Erro ao enviar texto. Status: %s - %s",
            response.status_code,
            response.text,
        )
        return False
    except Exception as e:
        logger.error("[WhatsApp] Erro na requisição de texto: %s", e)
        return False


def enviar_foto(url_imagem: str, legenda: str) -> bool:
    """Envia imagem com legenda para o grupo do WhatsApp (Evolution API v2)."""
    cfg = _obter_config()
    if not cfg["url"] or not cfg["group_jid"]:
        logger.warning("[WhatsApp] Configurações ausentes (URL ou Group JID).")
        return False

    endpoint = f"{cfg['url']}/message/sendMedia/{cfg['instance']}"
    payload = {
        "number": cfg["group_jid"],
        "media": url_imagem,
        "mediatype": "image",
        "caption": legenda,
    }

    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers=_get_headers(cfg["key"]),
            timeout=25,
        )
        if response.status_code in [200, 201]:
            logger.info("[WhatsApp] Imagem enviada com sucesso.")
            return True
        logger.error(
            "[WhatsApp] Erro ao enviar imagem. Status: %s - %s",
            response.status_code,
            response.text,
        )
        return False
    except Exception as e:
        logger.error("[WhatsApp] Erro na requisição de mídia: %s", e)
        return False