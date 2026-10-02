"""
Camada de comunicação com o Telegram.

Responsável apenas por enviar mensagens para o canal configurado através
da API oficial do Telegram Bot. Não deve conter regras de negócio sobre
promoções — isso fica em `promocoes.py`.
"""

import html
import logging

import requests

from app import config

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


def _url(metodo: str) -> str:
    return f"{TELEGRAM_API_BASE.format(token=config.TELEGRAM_BOT_TOKEN)}/{metodo}"


def enviar_mensagem(texto: str, parse_mode: str | None = None) -> bool:
    """
    Envia uma mensagem de texto para o canal do Telegram configurado.

    Retorna True em caso de sucesso e False em caso de falha. Em modo de
    teste (TEST_MODE=true), a mensagem não é enviada de verdade — apenas
    exibida no terminal.

    `parse_mode` fica None por padrão (texto puro): títulos de produtos
    raspados do Mercado Livre podem conter caracteres como '&' ou '<'
    que quebrariam o parser HTML/Markdown do Telegram.
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

    try:
        resposta = requests.post(_url("sendMessage"), data=payload, timeout=15)
        resposta.raise_for_status()
        dados = resposta.json()
        if not dados.get("ok"):
            logger.error("Falha ao enviar mensagem para Telegram: %s", dados)
            return False
        logger.info("Mensagem enviada ao Telegram com sucesso.")
        return True
    except requests.RequestException as erro:
        logger.error("Falha ao enviar mensagem para Telegram: %s", erro)
        return False


def enviar_foto(url_imagem: str, legenda: str, parse_mode: str | None = None) -> bool:
    """
    Envia uma foto com legenda para o canal do Telegram configurado.
    Usado quando a promoção tem uma imagem do produto.

    Em modo de teste, apenas exibe no terminal (igual `enviar_mensagem`).
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

    try:
        resposta = requests.post(_url("sendPhoto"), data=payload, timeout=15)
        resposta.raise_for_status()
        dados = resposta.json()
        if not dados.get("ok"):
            logger.error("Falha ao enviar foto para Telegram: %s", dados)
            return False
        logger.info("Foto enviada ao Telegram com sucesso.")
        return True
    except requests.RequestException as erro:
        logger.error("Falha ao enviar foto para Telegram: %s", erro)
        return False


def _montar_texto_com_link_oculto(texto: str, url: str, rotulo: str = "🛒 Ver oferta") -> str:
    """
    Recebe o texto da mensagem já pronto (contendo a URL crua em algum
    ponto) e devolve uma versão em HTML onde essa URL vira um link
    clicável com o texto `rotulo`, escapando o restante do conteúdo
    para não quebrar o parser do Telegram.

    Se a URL não for encontrada no texto (ex.: já foi removida antes),
    o link é apenas acrescentado ao final.
    """
    if url and url in texto:
        antes, depois = texto.split(url, 1)
        return f"{html.escape(antes)}<a href=\"{html.escape(url, quote=True)}\">{rotulo}</a>{html.escape(depois)}"

    escapado = html.escape(texto)
    if url:
        escapado += f"\n\n<a href=\"{html.escape(url, quote=True)}\">{rotulo}</a>"
    return escapado


def publicar_com_link_oculto(
    texto: str, url_afiliado: str, url_imagem: str | None = None, rotulo: str = "🛒 Ver oferta"
) -> bool:
    """
    Publica a promoção no canal com a URL de afiliado escondida atrás
    de um texto clicável (ex.: "🛒 Ver oferta"), usando parse_mode HTML.

    `texto` deve ser a mensagem já montada por `promocoes.montar_mensagem`,
    contendo a URL crua em algum ponto (normalmente no fim). `url_afiliado`
    é essa mesma URL, passada separadamente para localizá-la no texto.

    Se o envio em HTML falhar por qualquer motivo (ex.: caractere que
    o parser não aceitou), cai automaticamente para o texto simples,
    com o link visível por extenso, para não perder a publicação.
    """
    texto_html = _montar_texto_com_link_oculto(texto, url_afiliado, rotulo)

    if url_imagem:
        sucesso = enviar_foto(url_imagem, texto_html, parse_mode="HTML")
        if sucesso:
            return True
        logger.warning("Falha ao enviar foto com link oculto — tentando texto simples.")

    sucesso = enviar_mensagem(texto_html, parse_mode="HTML")
    if sucesso:
        return True

    logger.warning("Falha ao enviar em HTML — tentando texto simples sem link oculto.")
    if url_imagem:
        if enviar_foto(url_imagem, texto):
            return True
    return enviar_mensagem(texto)


def publicar_promocao(mensagem: str, url_imagem: str | None = None) -> bool:
    """
    Publica uma promoção no canal: com foto (se houver imagem) ou como
    texto simples (fallback). Ponto de entrada único usado pelo fluxo
    principal do bot (Fase 5).
    """
    if url_imagem:
        sucesso = enviar_foto(url_imagem, mensagem)
        if sucesso:
            return True
        logger.warning("Falha ao enviar com foto — tentando como texto simples.")

    return enviar_mensagem(mensagem)


def testar_conexao() -> bool:
    """
    Envia uma mensagem simples de teste para validar a conexão com o
    Telegram (token válido e bot com permissão no canal).
    """
    mensagem = (
        "✅ Bot de Promoções conectado com sucesso!\n\n"
        "Esta é uma mensagem de teste da Fase 1."
    )
    return enviar_mensagem(mensagem)