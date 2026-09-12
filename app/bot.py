"""
Orquestrador principal do bot de promoções.
Coordena a busca de ofertas por nicho cíclico, filtragem, validação no banco e envio ao Telegram.
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
        f"• Max por ciclo: {getattr(config, 'MAX_PROMOTIONS_PER_RUN', 1)}\n"
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


def executar_ciclo(nicho: dict = None) -> int:
    database.inicializar_banco()

    nome_nicho = nicho.get("nome", "Geral") if nicho else "Geral"
    url_categoria = nicho.get("url") if nicho else None

    logger.info("=== Iniciando ciclo de busca: Nicho [%s] ===", nome_nicho)

    ofertas_brutas = mercado_livre.buscar_ofertas(url_categoria=url_categoria)

    if not ofertas_brutas:
        logger.info("Nenhuma oferta encontrada para o nicho [%s].", nome_nicho)
        return 0

    ofertas_filtradas = promocoes.preparar_promocoes_para_publicar(
        ofertas_brutas
    )

    logger.info(
        "%d ofertas aprovadas após os filtros para [%s].",
        len(ofertas_filtradas),
        nome_nicho
    )

    enviadas = 0
    max_envios = getattr(config, "MAX_PROMOTIONS_PER_RUN", 1)
    delay_segundos = getattr(config, "TELEGRAM_SEND_DELAY_SECONDS", 8)

    for promo in ofertas_filtradas:
        if enviadas >= max_envios:
            logger.info(
                "Limite de %d envios atingido para este ciclo.",
                max_envios
            )
            break

        url_produto = promo.get("url_produto", "").strip()
        produto_id = database.extrair_produto_id(url_produto)

        if not produto_id:
            logger.warning(
                "⚠️ Produto ignorado por falta de ID válido: %s",
                url_produto
            )
            continue

        promo["produto_id"] = produto_id

        if database.produto_ja_publicado(produto_id):
            logger.info(
                "⏩ Produto %s já publicado anteriormente. Ignorando...",
                produto_id
            )
            continue

        if not promo.get("url_afiliado"):
            logger.info("🔗 Gerando link de afiliado para %s...", produto_id)
            promo["url_afiliado"] = mercado_livre.montar_link_afiliado(
                url_produto
            )

        texto_mensagem = promocoes.montar_mensagem(promo)
        imagem_url = promo.get("imagem")

        if getattr(config, "TEST_MODE", False):
            logger.info(
                "[TEST_MODE] Promoção aprovada (ID %s):\n%s\n",
                produto_id,
                texto_mensagem
            )
            enviadas += 1
            continue

        logger.info(
            "📢 Publicando no Telegram [%s]: %s (ID: %s)",
            nome_nicho,
            promo.get("titulo"),
            produto_id
        )

        sucesso = _publicar_no_telegram(texto_mensagem, imagem_url)

        if sucesso:
            database.salvar_promocao(promo)
            logger.info("💾 Produto %s salvo no banco.", produto_id)
            enviadas += 1

            if enviadas < max_envios:
                time.sleep(delay_segundos)
        else:
            logger.warning(
                "❌ Falha ao publicar %s. Não salvo no banco.",
                produto_id
            )

    logger.info(
        "Ciclo [%s] finalizado. Novas promoções publicadas: %d",
        nome_nicho,
        enviadas
    )

    return enviadas


def rodar_loop():
    """Executa a fila cíclica sequencial (Round Robin) pelos nichos cadastrados."""
    logger.info("Iniciando loop do bot com rotação de nichos...")

    nichos = getattr(mercado_livre, "NICHOS_ESTRATEGICOS", [])
    total_nichos = len(nichos)
    indice_atual = 0

    while True:
        nicho_atual = nichos[indice_atual] if nichos else None

        try:
            executar_ciclo(nicho=nicho_atual)
        except Exception as erro:
            logger.error(
                "Erro durante o ciclo: %s",
                erro,
                exc_info=True
            )

        # Avança para o próximo nicho na lista de forma circular
        if nichos:
            indice_atual = (indice_atual + 1) % total_nichos
            proximo_nicho = nichos[indice_atual]["nome"]
        else:
            proximo_nicho = "Geral"

        intervalo_min = getattr(
            config,
            "CHECK_INTERVAL_MINUTES",
            5
        )

        logger.info(
            "Aguardando %d minutos. Próximo nicho na fila: [%s]",
            intervalo_min,
            proximo_nicho
        )

        time.sleep(intervalo_min * 10)