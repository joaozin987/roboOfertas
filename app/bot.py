"""
Orquestrador principal do bot de promoções.
Coordena a busca de ofertas por nicho cíclico (Mercado Livre e Shopee),
filtragem com deduplicação antecipada no banco, modo noturno e envio ao Telegram e WhatsApp.
"""

import logging
import time
from datetime import datetime
from typing import List, Dict

from app import config, database, mercado_livre, promocoes, telegram, whatsapp

# Import seguro do módulo da Shopee
try:
    from app import shopee
except ImportError:
    shopee = None

logger = logging.getLogger(__name__)

_shopee_idx = 0


def _proximo_nicho_shopee():
    """Rotaciona pelos nichos da Shopee a cada ciclo."""
    global _shopee_idx
    nichos = getattr(shopee, "NICHOS_ESTRATEGICOS", []) if shopee else []
    if not nichos:
        return None
    url = nichos[_shopee_idx % len(nichos)]["url"]
    _shopee_idx += 1
    return url


def enviar_mensagem_teste() -> bool:
    """Envia uma mensagem de teste para validar a conexão com Telegram e WhatsApp."""
    logger.info("Enviando mensagem de teste para os canais...")

    mensagem = (
        "🤖 *Bot de Promoções conectado com sucesso!*\n\n"
        "Configurações ativas:\n"
        f"• ML Cota por ciclo: {getattr(config, 'ML_COUNT_PER_RUN', 1)}\n"
        f"• Shopee Cota por ciclo: {getattr(config, 'SHOPEE_COUNT_PER_RUN', 2)}\n"
        f"• Teto Global (Max Total): {getattr(config, 'MAX_PROMOTIONS_PER_RUN', 3)}\n"
        f"• Intervalo de ciclo: {getattr(config, 'CHECK_INTERVAL_MINUTES', 4)} min"
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


def _enviar_para_telegram(promo: dict, texto_mensagem: str, imagem_url: str = None) -> bool:
    """
    Escolhe o caminho de envio ao Telegram conforme a origem da promoção:
    - Shopee: usa link oculto (HTML), já que a URL de afiliado é muito longa.
    - Mercado Livre (e qualquer outra origem): mantém o caminho original,
      sem parse_mode, exatamente como já validado em produção.
    """
    origem = (promo.get("origem") or "").lower()

    if origem == "shopee" and hasattr(telegram, "publicar_com_link_oculto"):
        try:
            return telegram.publicar_com_link_oculto(
                texto_mensagem, promo.get("url_afiliado", ""), imagem_url
            )
        except Exception as err:
            logger.warning(
                "Falha ao publicar com link oculto no Telegram: %s. Tentando caminho padrão...",
                err,
            )

    return _publicar_no_telegram(texto_mensagem, imagem_url)


def _processar_e_publicar_oferta(promo: dict, delay_segundos: int) -> bool:
    """Valida ID, gera link de afiliado se necessário e dispara nos canais ativos."""
    url_produto = promo.get("url_produto", "").strip()
    produto_id = promo.get("produto_id") or database.extrair_produto_id(url_produto)

    if not produto_id:
        logger.warning("⚠️ Produto ignorado por falta de ID válido: %s", url_produto)
        return False

    promo["produto_id"] = str(produto_id)

    if database.produto_ja_publicado(promo["produto_id"]):
        logger.info("⏩ Produto %s já publicado anteriormente. Ignorando...", promo["produto_id"])
        return False

    origem = promo.get("origem", "").lower()
    if origem != "shopee" and not promo.get("url_afiliado"):
        logger.info("🔗 Gerando link de afiliado Mercado Livre para %s...", promo["produto_id"])
        link_afiliado = mercado_livre.montar_link_afiliado(url_produto)
        promo["url_afiliado"] = link_afiliado

    texto_mensagem = promocoes.montar_mensagem(promo)
    imagem_url = promo.get("imagem")

    if getattr(config, "TEST_MODE", False):
        logger.info("[TEST_MODE] Promoção aprovada [%s] (ID %s):\n%s\n", promo.get("origem", "ML"), promo["produto_id"], texto_mensagem)
        return True

    logger.info(
        "📢 Publicando [%s] nos canais: %s (ID: %s)",
        promo.get("origem", "Mercado Livre"),
        promo.get("titulo"),
        promo["produto_id"],
    )

    sucesso_tg = _enviar_para_telegram(promo, texto_mensagem, imagem_url)
    time.sleep(2)
    sucesso_wpp = _publicar_no_whatsapp(texto_mensagem, imagem_url)

    if sucesso_tg or sucesso_wpp:
        database.salvar_promocao(promo)
        logger.info("💾 Produto %s salvo no banco de dados.", promo["produto_id"])
        time.sleep(delay_segundos)
        return True
    else:
        logger.warning("❌ Falha ao publicar %s em todos os canais. Não salvo no banco.", promo["produto_id"])
        return False


def _filtrar_apenas_ineditas(lista_ofertas: List[Dict]) -> List[Dict]:
    """Descarta ofertas que já existem no banco antes da montagem final da fila."""
    ineditas = []
    for promo in lista_ofertas:
        url = promo.get("url_produto", "").strip()
        pid = promo.get("produto_id") or database.extrair_produto_id(url)
        if pid:
            promo["produto_id"] = str(pid)
            if not database.produto_ja_publicado(promo["produto_id"]):
                ineditas.append(promo)
    return ineditas


def _obter_cotas_envio() -> tuple[int, int]:
    """Retorna as cotas fixas de (ML, Shopee)."""
    ml_cota = int(getattr(config, "ML_COUNT_PER_RUN", 1))
    shopee_cota = int(getattr(config, "SHOPEE_COUNT_PER_RUN", 2))
    return ml_cota, shopee_cota


def executar_ciclo(nicho: dict = None) -> int:
    database.inicializar_banco()

    nome_nicho = nicho.get("nome", "Geral") if nicho else "Geral"
    url_categoria = nicho.get("url") if nicho else None
    delay_segundos = getattr(config, "TELEGRAM_SEND_DELAY_SECONDS", 10)

    ml_cota, shopee_cota = _obter_cotas_envio()
    max_global = int(getattr(config, "MAX_PROMOTIONS_PER_RUN", 3))

    logger.info("=== Iniciando ciclo de busca: Nicho [%s] ===", nome_nicho)

    # 1. Mercado Livre
    ofertas_meli_brutas = mercado_livre.buscar_ofertas(url_categoria=url_categoria) or []
    ofertas_meli_brutas_ineditas = _filtrar_apenas_ineditas(ofertas_meli_brutas)
    ofertas_meli_aprovadas = promocoes.preparar_promocoes_para_publicar(ofertas_meli_brutas_ineditas)
    min_desc_meli = getattr(config, "MELI_MIN_DESCONTO", getattr(config, "DESCONTO_MINIMO", 70.0))
    ofertas_meli_filtradas = [
        p for p in ofertas_meli_aprovadas if (p.get("desconto") or 0) >= min_desc_meli
    ]
    ofertas_meli_ineditas = _filtrar_apenas_ineditas(ofertas_meli_filtradas)

    # 2. Shopee (rotaciona o nicho da própria Shopee)
    ofertas_shopee_ineditas = []
    if shopee_cota > 0 and shopee:
        fn_buscar = getattr(shopee, "buscar_ofertas_shopee", getattr(shopee, "buscar_ofertas", None))
        if fn_buscar:
            try:
                url_shopee = _proximo_nicho_shopee()
                brutas = (fn_buscar(url_categoria=url_shopee) if url_shopee else fn_buscar()) or []
                logger.info("Shopee: %d ofertas brutas recebidas", len(brutas))
                ofertas_shopee_ineditas = _filtrar_apenas_ineditas(brutas)
                logger.info("Shopee: %d ofertas inéditas", len(ofertas_shopee_ineditas))
            except Exception as err_shopee:
                logger.error("Falha ao buscar ofertas Shopee: %s", err_shopee, exc_info=True)

    # 3. Monta lote por cota, respeitando teto global
    ml_selecionadas = ofertas_meli_ineditas[:ml_cota]
    shopee_selecionadas = ofertas_shopee_ineditas[:shopee_cota]

    fila_publicacao: List[Dict] = []
    idx_ml, idx_shopee = 0, 0

    while (idx_ml < len(ml_selecionadas) or idx_shopee < len(shopee_selecionadas)) and len(fila_publicacao) < max_global:
        for _ in range(ml_cota):
            if idx_ml < len(ml_selecionadas) and len(fila_publicacao) < max_global:
                fila_publicacao.append(ml_selecionadas[idx_ml])
                idx_ml += 1
        for _ in range(shopee_cota):
            if idx_shopee < len(shopee_selecionadas) and len(fila_publicacao) < max_global:
                fila_publicacao.append(shopee_selecionadas[idx_shopee])
                idx_shopee += 1

    logger.info(
        "Fila para [%s]: %d ofertas prontas (Cota alvo: %d ML + %d Shopee, Teto global: %d).",
        nome_nicho,
        len(fila_publicacao),
        ml_cota,
        shopee_cota,
        max_global,
    )

    enviadas = 0
    for promo in fila_publicacao:
        if _processar_e_publicar_oferta(promo, delay_segundos):
            enviadas += 1

    logger.info("Ciclo [%s] finalizado. Promoções processadas: %d", nome_nicho, enviadas)
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

        intervalo_min = getattr(config, "CHECK_INTERVAL_MINUTES", 4)

        logger.info(
            "Aguardando %d minutos. Próximo nicho na fila: [%s]",
            intervalo_min,
            proximo_nicho,
        )

        time.sleep(intervalo_min * 60)