"""
Orquestrador principal do bot de promoções.
Coordena a busca de ofertas por nicho cíclico (Mercado Livre),
filtragem com limites independentes, validação no banco e envio ao Telegram e WhatsApp.
"""

import logging
import time
from typing import List, Dict

from app import config, database, mercado_livre, promocoes, telegram, whatsapp

logger = logging.getLogger(__name__)


def enviar_mensagem_teste() -> bool:
    """Envia uma mensagem de teste para validar a conexão com Telegram e WhatsApp."""
    logger.info("Enviando mensagem de teste para os canais...")

    mensagem = (
        "🤖 *Jpz Ofertas Bot conectado com sucesso!*\n\n"
        "Configurações ativas:\n"
        f"• ML Desconto Mínimo: {getattr(config, 'MELI_MIN_DESCONTO', getattr(config, 'DESCONTO_MINIMO', 70))}%\n"
        f"• ML Max Envios por ciclo: {getattr(config, 'MELI_MAX_ENVIOS', 5)}\n"
        f"• Intervalo de ciclo: {getattr(config, 'CHECK_INTERVAL_MINUTES', 5)} min"
    )

    sucesso_tg = False
    if hasattr(telegram, "enviar_mensagem"):
        sucesso_tg = telegram.enviar_mensagem(mensagem)

    sucesso_wpp = False
    if hasattr(whatsapp, "enviar_mensagem"):
        sucesso_wpp = whatsapp.enviar_mensagem(mensagem)

    return sucesso_tg or sucesso_wpp


def _publicar_no_telegram(texto_mensagem: str, imagem_url: str = None) -> bool:
    """Tenta enviar foto com legenda para o Telegram; se não conseguir, envia texto puro."""
    if imagem_url and hasattr(telegram, "enviar_foto"):
        try:
            return telegram.enviar_foto(imagem_url, texto_mensagem)
        except TypeError:
            try:
                return telegram.enviar_foto(url_imagem=imagem_url, legenda=texto_mensagem)
            except Exception as err:
                logger.warning("Falha ao enviar com foto no Telegram: %s. Tentando texto...", err)
        except Exception as err:
            logger.warning("Falha ao enviar com foto no Telegram: %s. Tentando texto...", err)

    if hasattr(telegram, "enviar_mensagem"):
        return telegram.enviar_mensagem(texto_mensagem)

    return False


def _publicar_no_whatsapp(texto_mensagem: str, imagem_url: str = None) -> bool:
    """Tenta enviar foto com legenda para o WhatsApp; se não conseguir, envia texto puro."""
    if imagem_url and hasattr(whatsapp, "enviar_foto"):
        try:
            return whatsapp.enviar_foto(imagem_url, texto_mensagem)
        except TypeError:
            try:
                return whatsapp.enviar_foto(url_imagem=imagem_url, legenda=texto_mensagem)
            except Exception as err:
                logger.warning("Falha ao enviar com foto no WhatsApp: %s. Tentando texto...", err)
        except Exception as err:
            logger.warning("Falha ao enviar com foto no WhatsApp: %s. Tentando texto...", err)

    if hasattr(whatsapp, "enviar_mensagem"):
        return whatsapp.enviar_mensagem(texto_mensagem)

    return False


def _processar_e_publicar_oferta(promo: dict, delay_segundos: int) -> bool:
    """Valida duplicidade, assegura o link de afiliado comissionado e dispara nos canais ativos."""
    url_produto = promo.get("url_produto", "").strip()
    produto_id = promo.get("produto_id") or database.extrair_produto_id(url_produto)

    if not produto_id:
        logger.warning("⚠️ Produto ignorado por falta de ID válido: %s", url_produto)
        return False

    promo["produto_id"] = str(produto_id)

    if database.produto_ja_publicado(promo["produto_id"]):
        logger.info("⏩ Produto %s já publicado anteriormente. Ignorando...", promo["produto_id"])
        return False

    # Gera link de afiliado Mercado Livre obrigatório
    if not promo.get("url_afiliado"):
        logger.info("🔗 Gerando link de afiliado Mercado Livre para %s...", promo["produto_id"])
        link_afiliado = mercado_livre.montar_link_afiliado(url_produto)
        
        # Trava de segurança: Se o cookie expirou e não gerou comissão, NÃO posta!
        if not link_afiliado:
            logger.error(
                "❌ [BLOQUEIO DE SEGURANÇA] Item %s ignorado porque o link comissionado falhou (Cookie expirado?).",
                promo["produto_id"]
            )
            return False
            
        promo["url_afiliado"] = link_afiliado

    texto_mensagem = promocoes.montar_mensagem(promo)
    imagem_url = promo.get("imagem")

    if getattr(config, "TEST_MODE", False):
        logger.info("[TEST_MODE] Promoção validada (ID %s):\n%s\n", promo["produto_id"], texto_mensagem)
        return True

    logger.info(
        "📢 Publicando [%s] nos canais: %s (ID: %s)",
        promo.get("origem", "Mercado Livre"),
        promo.get("titulo"),
        promo["produto_id"]
    )

    # Disparo no Telegram
    sucesso_tg = _publicar_no_telegram(texto_mensagem, imagem_url)

    # Respiro de 2 segundos entre as duas APIs
    time.sleep(2)

    # Disparo no WhatsApp
    sucesso_wpp = _publicar_no_whatsapp(texto_mensagem, imagem_url)

    if sucesso_tg or sucesso_wpp:
        database.salvar_promocao(promo)
        logger.info("💾 Produto %s salvo no banco de dados.", promo["produto_id"])
        time.sleep(delay_segundos)
        return True
    else:
        logger.warning("❌ Falha ao publicar %s nos canais. Não salvo no banco.", promo["produto_id"])
        return False


def executar_ciclo(nicho: dict = None) -> int:
    database.inicializar_banco()

    nome_nicho = nicho.get("nome", "Geral") if nicho else "Geral"
    url_categoria = nicho.get("url") if nicho else None
    delay_segundos = getattr(config, "TELEGRAM_SEND_DELAY_SECONDS", 10)

    logger.info("=== Iniciando ciclo de busca: Nicho [%s] ===", nome_nicho)

    ofertas_meli_brutas = mercado_livre.buscar_ofertas(url_categoria=url_categoria) or []
    ofertas_meli_aprovadas = promocoes.preparar_promocoes_para_publicar(ofertas_meli_brutas)

    min_desc_meli = getattr(config, "MELI_MIN_DESCONTO", getattr(config, "DESCONTO_MINIMO", 70.0))
    ofertas_meli_filtradas = [
        p for p in ofertas_meli_aprovadas if (p.get("desconto") or 0) >= min_desc_meli
    ]
    max_envios_meli = getattr(config, "MELI_MAX_ENVIOS", 5)

    fila_publicacao: List[Dict] = ofertas_meli_filtradas[:max_envios_meli]

    logger.info(
        "Fila montada para [%s]: %d ofertas prontas para processamento.",
        nome_nicho,
        len(fila_publicacao)
    )

    enviadas = 0
    for promo in fila_publicacao:
        if _processar_e_publicar_oferta(promo, delay_segundos):
            enviadas += 1

    logger.info("Ciclo [%s] finalizado. Novas promoções publicadas: %d", nome_nicho, enviadas)
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
            logger.error("Erro durante o ciclo: %s", erro, exc_info=True)

        if nichos:
            indice_atual = (indice_atual + 1) % total_nichos
            proximo_nicho = nichos[indice_atual]["nome"]
        else:
            proximo_nicho = "Geral"

        intervalo_min = getattr(config, "CHECK_INTERVAL_MINUTES", 5)

        logger.info(
            "Aguardando %d minutos. Próximo nicho na fila: [%s]",
            intervalo_min,
            proximo_nicho
        )

        time.sleep(intervalo_min * 60)