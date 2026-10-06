"""
Camada de comunicação com o Telegram.

Responsável apenas por enviar mensagens para o canal configurado através
da API oficial do Telegram Bot. Não deve conter regras de negócio sobre
promoções — isso fica em `promocoes.py`.
"""

import html
import logging
import time
from typing import Optional

import requests

from app import config

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


def _url(metodo: str) -> str:
    return f"{TELEGRAM_API_BASE.format(token=config.TELEGRAM_BOT_TOKEN)}/{metodo}"


def _post(metodo: str, payload: dict) -> bool:
    """
    POST único para a API. Nunca loga a exceção completa do `requests`, porque a
    URL (que contém o token do bot) aparece nela. Trata o rate limit (429).
    """
    try:
        resposta = requests.post(_url(metodo), data=payload, timeout=15)

        if resposta.status_code == 429:
            try:
                espera = int(resposta.json().get("parameters", {}).get("retry_after", 5))
            except (ValueError, TypeError, AttributeError):
                espera = 5
            logger.warning("Rate limit do Telegram: aguardando %ss", espera)
            time.sleep(min(espera, 60))
            resposta = requests.post(_url(metodo), data=payload, timeout=15)

        try:
            dados = resposta.json()
        except ValueError:
            dados = {}

        if not dados.get("ok"):
            logger.error(
                "Telegram recusou %s (HTTP %s): %s",
                metodo, resposta.status_code, dados.get("description", "sem descrição"),
            )
            return False
        return True

    except requests.exceptions.ReadTimeout:
        # O pedido chegou ao Telegram mas a resposta não voltou: provavelmente foi entregue.
        # Retornar False dispararia o fallback e a oferta sairia duplicada no canal.
        logger.warning(
            "Telegram: timeout de leitura em %s. Assumindo entregue para evitar duplicata.", metodo
        )
        return True
    except requests.RequestException as erro:
        logger.error("Falha de rede em %s: %s", metodo, type(erro).__name__)
        return False


def enviar_mensagem(texto: str, parse_mode: Optional[str] = None) -> bool:
    """
    Envia uma mensagem de texto para o canal do Telegram configurado.

    Em modo de teste (TEST_MODE=true), a mensagem não é enviada de verdade —
    apenas exibida no terminal.

    `parse_mode` fica None por padrão (texto puro): títulos raspados do
    Mercado Livre podem conter '&' ou '<' que quebrariam o parser HTML/Markdown.
    """
    if config.TEST_MODE:
        print("[TESTE] Mensagem que seria enviada ao Telegram:\n")
        print(texto)
        print("\nNão publicado no Telegram (TEST_MODE=true).")
        logger.info("TEST_MODE ativo: mensagem não enviada de verdade.")
        return True

    config.validar_configuracao_telegram()

    payload = {
        "chat_id": config.TELEGRAM_CHANNEL_ID,
        "text": texto,
        "disable_web_page_preview": False,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    sucesso = _post("sendMessage", payload)
    if sucesso:
        logger.info("Mensagem enviada ao Telegram com sucesso.")
    return sucesso


def enviar_foto(url_imagem: str, legenda: str, parse_mode: Optional[str] = None) -> bool:
    """
    Envia uma foto com legenda (máx. 1024 caracteres no Telegram).
    Em modo de teste, apenas exibe no terminal.
    """
    if config.TEST_MODE:
        print("[TESTE] Foto + mensagem que seriam enviadas ao Telegram:\n")
        print(f"[imagem: {url_imagem}]\n")
        print(legenda)
        print("\nNão publicado no Telegram (TEST_MODE=true).")
        logger.info("TEST_MODE ativo: foto não enviada de verdade.")
        return True

    config.validar_configuracao_telegram()

    payload = {
        "chat_id": config.TELEGRAM_CHANNEL_ID,
        "photo": url_imagem,
        "caption": legenda,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    sucesso = _post("sendPhoto", payload)
    if sucesso:
        logger.info("Foto enviada ao Telegram com sucesso.")
    return sucesso


def _montar_texto_com_link_oculto(texto: str, url: str, rotulo: str = "🛒 Ver oferta") -> str:
    """
    Recebe o texto pronto (contendo a URL crua) e devolve uma versão em HTML onde
    essa URL vira um link clicável com o texto `rotulo`, escapando o resto do
    conteúdo para não quebrar o parser do Telegram.
    """
    if url and url in texto:
        antes, depois = texto.split(url, 1)
        return (
            f"{html.escape(antes, quote=False)}"
            f"<a href=\"{html.escape(url, quote=True)}\">{rotulo}</a>"
            f"{html.escape(depois, quote=False)}"
        )

    escapado = html.escape(texto, quote=False)
    if url:
        escapado += f"\n\n<a href=\"{html.escape(url, quote=True)}\">{rotulo}</a>"
    return escapado


def publicar_com_link_oculto(
    texto: str, url_afiliado: str, url_imagem: Optional[str] = None, rotulo: str = "🛒 Ver oferta"
) -> bool:
    """
    Publica a promoção com a URL de afiliado escondida atrás de um texto
    clicável (parse_mode HTML). Se o envio em HTML falhar, cai para texto
    simples com o link visível, para não perder a publicação.
    """
    texto_html = _montar_texto_com_link_oculto(texto, url_afiliado, rotulo)

    if url_imagem:
        if enviar_foto(url_imagem, texto_html, parse_mode="HTML"):
            return True
        logger.warning("Falha ao enviar foto com link oculto — tentando texto simples.")

    if enviar_mensagem(texto_html, parse_mode="HTML"):
        return True

    logger.warning("Falha ao enviar em HTML — tentando texto simples sem link oculto.")
    if url_imagem and enviar_foto(url_imagem, texto):
        return True
    return enviar_mensagem(texto)


def publicar_promocao(mensagem: str, url_imagem: Optional[str] = None) -> bool:
    """Publica com foto (se houver) ou como texto simples. Ponto de entrada do fluxo do bot."""
    if url_imagem:
        if enviar_foto(url_imagem, mensagem):
            return True
        logger.warning("Falha ao enviar com foto — tentando como texto simples.")

    return enviar_mensagem(mensagem)


def testar_conexao() -> bool:
    """Envia uma mensagem de teste para validar token e permissão no canal."""
    mensagem = (
        "✅ Bot de Promoções conectado com sucesso!\n\n"
        "Esta é uma mensagem de teste da Fase 1."
    )
    return enviar_mensagem(mensagem)