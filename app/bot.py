"""
Orquestrador principal do bot de promoções.
Coordena a busca de ofertas, filtragem, validação no banco e envio cadenciado ao Telegram.
"""

import logging
import time
from typing import List, Dict

from app import config, database, mercado_livre, promocoes, telegram

logger = logging.getLogger(__name__)


def enviar_mensagem_teste() -> bool:
    """Envia uma mensagem de teste para validar a conexão com o Telegram."""
    logger.info("Enviando mensagem de teste para o canal...")

    mensagem = (
        "🤖 *Bot de Promoções conectado com sucesso!*\n\n"
        "Configurações ativas:\n"
        f"• Desconto mínimo: {getattr(config, 'DESCONTO_MINIMO', 15)}%\n"
        f"• Max por ciclo: {getattr(config, 'MAX_PROMOTIONS_PER_RUN', 4)}\n"
        f"• Intervalo de ciclo: {getattr(config, 'CHECK_INTERVAL_MINUTES', 5)} min"
    )

    if hasattr(telegram, "enviar_mensagem"):
        return telegram.enviar_mensagem(mensagem)

    return False


def _publicar_no_telegram(
    texto_mensagem: str,
    imagem_url: str = None
) -> bool:
    """Tenta enviar foto com legenda; se não conseguir, envia apenas o texto."""

    if imagem_url and hasattr(telegram, "enviar_foto"):
        try:
            return telegram.enviar_foto(
                imagem_url,
                texto_mensagem
            )

        except TypeError:
            try:
                return telegram.enviar_foto(
                    url_imagem=imagem_url,
                    legenda=texto_mensagem
                )

            except Exception as err:
                logger.warning(
                    "Falha ao enviar com foto: %s. Tentando texto...",
                    err
                )

        except Exception as err:
            logger.warning(
                "Falha ao enviar com foto: %s. Tentando texto...",
                err
            )

    if hasattr(telegram, "enviar_mensagem"):
        return telegram.enviar_mensagem(texto_mensagem)

    return False


def executar_ciclo() -> int:
    """
    Executa uma rodada completa:

    1. Garante que a tabela SQLite existe
    2. Coleta ofertas no Mercado Livre
    3. Filtra por desconto e preço
    4. Verifica se o produto já foi publicado
    5. Gera o link de afiliado SOMENTE para produtos aprovados
    6. Envia para o Telegram
    7. Registra no SQLite somente se o envio for realizado
    """

    # ==========================================================
    # 1. Garante o banco pronto
    # ==========================================================

    database.inicializar_banco()

    logger.info("=== Iniciando ciclo de busca de ofertas ===")

    # ==========================================================
    # 2. Busca ofertas
    # ==========================================================

    ofertas_brutas = mercado_livre.buscar_ofertas()

    if not ofertas_brutas:
        logger.info("Nenhuma oferta encontrada nesta busca.")
        return 0

    # ==========================================================
    # 3. Aplica filtros
    # ==========================================================

    ofertas_filtradas = promocoes.preparar_promocoes_para_publicar(
        ofertas_brutas
    )

    logger.info(
        "%d ofertas aprovadas após os filtros.",
        len(ofertas_filtradas)
    )

    # ==========================================================
    # 4. Configurações do ciclo
    # ==========================================================

    enviadas = 0

    max_envios = getattr(
        config,
        "MAX_PROMOTIONS_PER_RUN",
        4
    )

    delay_segundos = getattr(
        config,
        "TELEGRAM_SEND_DELAY_SECONDS",
        8
    )

    # ==========================================================
    # 5. Processa somente as ofertas aprovadas
    # ==========================================================

    for promo in ofertas_filtradas:

        # Limite de envios por ciclo
        if enviadas >= max_envios:
            logger.info(
                "Limite de %d envios atingido para este ciclo.",
                max_envios
            )
            break

        url_produto = promo.get(
            "url_produto",
            ""
        )

        # ======================================================
        # Extrai ID correto do produto
        # ======================================================

        produto_id = database.extrair_produto_id(
            url_produto
        )

        logger.info(
            "🔎 URL PRODUTO: %s",
            url_produto
        )

        logger.info(
            "🔎 PRODUTO ID: %s",
            produto_id
        )

        # ======================================================
        # 6. Verifica duplicidade ANTES de gerar afiliado
        # ======================================================

        if produto_id and database.produto_ja_publicado(
            produto_id
        ):
            logger.info(
                "⏩ Produto %s já publicado anteriormente. Ignorando...",
                produto_id
            )
            continue

        # ======================================================
        # 7. GERA O LINK DE AFILIADO SOMENTE AGORA
        #
        # Antes isso acontecia para todos os produtos
        # encontrados pelo scraper.
        #
        # Agora só acontece para os produtos que:
        # - passaram pelos filtros
        # - não estão no banco
        # - ainda podem ser publicados
        # ======================================================

        if not promo.get("url_afiliado"):

            logger.info(
                "🔗 Gerando link de afiliado para %s...",
                produto_id or "produto sem ID"
            )

            promo["url_afiliado"] = (
                mercado_livre.montar_link_afiliado(
                    url_produto
                )
            )

        # ======================================================
        # 8. Monta mensagem
        # ======================================================

        texto_mensagem = promocoes.montar_mensagem(
            promo
        )

        imagem_url = promo.get(
            "imagem"
        )

        # ======================================================
        # 9. TEST MODE
        # ======================================================

        if getattr(config, "TEST_MODE", False):

            logger.info(
                "[TEST_MODE] Promoção aprovada:\n%s\n",
                texto_mensagem
            )

            # Em TEST_MODE não enviamos e não registramos
            # como publicado.

            enviadas += 1

        # ======================================================
        # 10. ENVIO REAL
        # ======================================================

        else:

            logger.info(
                "📢 Publicando no Telegram: %s (ID: %s)",
                promo.get("titulo"),
                produto_id
            )

            sucesso = _publicar_no_telegram(
                texto_mensagem,
                imagem_url
            )

            # ==================================================
            # Só salva no banco se o Telegram confirmou envio
            # ==================================================

            if sucesso:

                database.salvar_promocao(
                    promo
                )

                logger.info(
                    "💾 Produto %s salvo no banco.",
                    produto_id
                )

                enviadas += 1

            else:

                logger.warning(
                    "❌ Falha ao publicar %s. "
                    "Produto NÃO será salvo no banco.",
                    produto_id
                )

        # ======================================================
        # 11. Delay entre publicações
        # ======================================================

        if enviadas < max_envios:
            time.sleep(
                delay_segundos
            )

    # ==========================================================
    # 12. Final do ciclo
    # ==========================================================

    logger.info(
        "Ciclo finalizado. Novas promoções publicadas: %d",
        enviadas
    )

    return enviadas


def rodar_loop():
    """Executa continuamente respeitando CHECK_INTERVAL_MINUTES."""

    logger.info(
        "Iniciando loop do bot..."
    )

    while True:

        try:

            executar_ciclo()

        except Exception as erro:

            logger.error(
                "Erro durante o ciclo: %s",
                erro,
                exc_info=True
            )

        intervalo_min = getattr(
            config,
            "CHECK_INTERVAL_MINUTES",
            5
        )

        logger.info(
            "Aguardando %d minutos até o próximo ciclo...",
            intervalo_min
        )

        time.sleep(
            intervalo_min * 60
        )