"""
Ponto central do bot — Fase 5.

Orquestra o fluxo completo:

    Mercado Livre -> buscar -> filtrar -> verificar banco -> selecionar
        -> montar mensagem -> Telegram -> salvar no banco
"""

import logging

from app import config, database, mercado_livre, promocoes, telegram

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)


def enviar_mensagem_teste() -> None:
    """Comando da Fase 1: valida a configuração e envia uma mensagem de teste."""
    logger.info("Bot iniciado")

    if not config.TEST_MODE:
        config.validar_configuracao_telegram()

    logger.info("Enviando mensagem de teste para o Telegram")
    sucesso = telegram.testar_conexao()

    if sucesso:
        logger.info("Mensagem de teste enviada com sucesso")
    else:
        logger.error("Falha ao enviar mensagem de teste")

    logger.info("Execução finalizada")


def executar_ciclo() -> None:
    """
    Executa um ciclo completo do bot: busca ofertas, filtra, remove as
    que já foram publicadas antes, seleciona as melhores, publica no
    Telegram e registra no banco.
    """
    logger.info("Bot iniciado")

    if not config.TEST_MODE:
        config.validar_configuracao_telegram()

    database.inicializar_banco()

    logger.info("Buscando promoções")
    ofertas_brutas = mercado_livre.buscar_ofertas()
    logger.info("%s produtos encontrados", len(ofertas_brutas))

    sem_duplicadas = promocoes.remover_duplicadas(ofertas_brutas)
    aprovadas = promocoes.filtrar_ofertas(sem_duplicadas)

    novas = []
    for oferta in aprovadas:
        produto_id = database.extrair_produto_id(oferta.get("url_produto", ""))
        if database.produto_ja_publicado(produto_id):
            continue
        novas.append(oferta)

    logger.info(
        "%s ofertas aprovadas, %s ainda não publicadas antes",
        len(aprovadas),
        len(novas),
    )

    selecionadas = promocoes.selecionar_melhores(novas)

    if not selecionadas:
        logger.info("Nenhuma promoção nova para publicar nesta execução")
        logger.info("Execução finalizada")
        return

    for oferta in selecionadas:
        mensagem = promocoes.montar_mensagem(oferta)
        sucesso = telegram.publicar_promocao(mensagem, oferta.get("imagem"))

        if sucesso:
            database.salvar_promocao(oferta)
            logger.info("Promoção enviada: %s", oferta.get("titulo"))
        else:
            logger.error("Falha ao enviar mensagem para Telegram: %s", oferta.get("titulo"))

    logger.info("Execução finalizada")