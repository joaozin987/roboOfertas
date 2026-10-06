"""
Orquestrador principal do bot de promoções.
Coordena a busca de ofertas por nicho cíclico (Mercado Livre e Shopee),
filtragem com deduplicação antecipada no banco, modo noturno e envio ao
Telegram e WhatsApp.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

from app import afiliados, config, database, mercado_livre, promocoes, telegram, whatsapp

# Import seguro do módulo da Shopee
try:
    from app import shopee
except ImportError:
    shopee = None

logger = logging.getLogger(__name__)

_shopee_idx = 0
_proxima_tentativa_afiliado = 0.0   # quando o ML pode tentar de novo após sessão expirada
_aviso_fuso_emitido = False
INTERVALO_RETENTATIVA_AFILIADO_S = 30 * 60
CANDIDATOS_POR_VAGA = 3             # reservas por vaga, caso o primeiro candidato falhe


# ------------------------------------------------------------ modo noturno

def _agora() -> datetime:
    global _aviso_fuso_emitido
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(getattr(config, "TIMEZONE", "America/Sao_Paulo")))
    except Exception:
        if not _aviso_fuso_emitido:
            logger.warning(
                "Fuso horário indisponível (no Windows: pip install tzdata). Usando hora local."
            )
            _aviso_fuso_emitido = True
        return datetime.now()


def em_horario_de_silencio(agora: Optional[datetime] = None) -> bool:
    inicio = int(getattr(config, "HORARIO_SILENCIO_INICIO", 23))
    fim = int(getattr(config, "HORARIO_SILENCIO_FIM", 7))
    if inicio == fim:
        return False
    hora = (agora or _agora()).hour
    if inicio < fim:
        return inicio <= hora < fim
    return hora >= inicio or hora < fim  # janela que atravessa a meia-noite


# --------------------------------------------------------------- Shopee

def _proximo_nicho_shopee():
    """Rotaciona pelos nichos da Shopee a cada ciclo."""
    global _shopee_idx
    nichos = getattr(shopee, "NICHOS_ESTRATEGICOS", []) if shopee else []
    if not nichos:
        return None
    url = nichos[_shopee_idx % len(nichos)]["url"]
    _shopee_idx += 1
    return url


# ----------------------------------------------------------- publicação

def enviar_mensagem_teste() -> bool:
    """Envia uma mensagem de teste para validar a conexão com Telegram e WhatsApp."""
    logger.info("Enviando mensagem de teste para os canais...")

    mensagem = (
        "🤖 Bot de Promoções conectado com sucesso!\n\n"
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


def _publicar_no_telegram(texto_mensagem: str, imagem_url: Optional[str] = None) -> bool:
    """Foto com legenda; se a foto falhar, cai para texto (fallback já feito em telegram.py)."""
    if hasattr(telegram, "publicar_promocao"):
        return telegram.publicar_promocao(texto_mensagem, imagem_url)
    if hasattr(telegram, "enviar_mensagem"):
        return telegram.enviar_mensagem(texto_mensagem)
    return False


def _publicar_no_whatsapp(texto_mensagem: str, imagem_url: Optional[str] = None) -> bool:
    """Tenta foto com legenda; se retornar False ou der erro, envia texto puro."""
    if imagem_url and hasattr(whatsapp, "enviar_foto"):
        try:
            if whatsapp.enviar_foto(imagem_url, texto_mensagem):
                return True
        except Exception as err:
            logger.warning("Falha ao enviar foto no WhatsApp: %s. Tentando texto...", err)

    if hasattr(whatsapp, "enviar_mensagem"):
        return whatsapp.enviar_mensagem(texto_mensagem)
    return False


def _enviar_para_telegram(promo: dict, texto_mensagem: str, imagem_url: Optional[str] = None) -> bool:
    """
    - Shopee: link oculto (HTML), já que a URL de afiliado é muito longa.
    - Mercado Livre (e qualquer outra origem): caminho padrão, sem parse_mode.
    """
    origem = (promo.get("origem") or "").lower()

    if origem == "shopee" and hasattr(telegram, "publicar_com_link_oculto"):
        try:
            return telegram.publicar_com_link_oculto(
                texto_mensagem, promo.get("url_afiliado", ""), imagem_url
            )
        except Exception as err:
            logger.warning(
                "Falha ao publicar com link oculto no Telegram: %s. Tentando caminho padrão...", err
            )

    return _publicar_no_telegram(texto_mensagem, imagem_url)


def _processar_e_publicar_oferta(promo: dict, delay_segundos: int) -> bool:
    """Valida ID, garante link de afiliado e dispara nos canais ativos."""
    url_produto = (promo.get("url_produto") or "").strip()
    produto_id = promo.get("produto_id") or database.extrair_produto_id(url_produto)

    if not produto_id:
        logger.warning("⚠️ Produto ignorado por falta de ID válido: %s", url_produto)
        return False

    promo["produto_id"] = str(produto_id)

    if database.produto_ja_publicado(promo["produto_id"]):
        logger.info("⏩ Produto %s já publicado anteriormente. Ignorando...", promo["produto_id"])
        return False

    origem = (promo.get("origem") or "").lower()

    # Nunca publica sem link de afiliado: o link cru não gera comissão.
    if not promo.get("url_afiliado"):
        if origem == "shopee":
            logger.warning("Oferta Shopee %s sem link de afiliado: ignorada.", promo["produto_id"])
            return False
        logger.info("🔗 Gerando link de afiliado Mercado Livre para %s...", promo["produto_id"])
        link_afiliado = mercado_livre.montar_link_afiliado(url_produto)
        if not link_afiliado:
            logger.warning("Sem link de afiliado para %s: oferta ignorada.", promo["produto_id"])
            return False
        promo["url_afiliado"] = link_afiliado

    texto_mensagem = promocoes.montar_mensagem(promo)
    imagem_url = promo.get("imagem")

    if getattr(config, "TEST_MODE", False):
        logger.info(
            "[TEST_MODE] Promoção aprovada [%s] (ID %s):\n%s\n",
            promo.get("origem", "ML"), promo["produto_id"], texto_mensagem,
        )
        return True

    logger.info(
        "📢 Publicando [%s] nos canais: %s (ID: %s)",
        promo.get("origem", "Mercado Livre"), promo.get("titulo"), promo["produto_id"],
    )

    sucesso_tg = _enviar_para_telegram(promo, texto_mensagem, imagem_url)
    time.sleep(2)
    sucesso_wpp = _publicar_no_whatsapp(texto_mensagem, imagem_url)

    if sucesso_tg or sucesso_wpp:
        database.salvar_promocao(promo)
        logger.info("💾 Produto %s salvo no banco de dados.", promo["produto_id"])
        time.sleep(delay_segundos)
        return True

    logger.warning("❌ Falha ao publicar %s em todos os canais. Não salvo no banco.", promo["produto_id"])
    return False


# ---------------------------------------------------------- seleção/ciclo

def _filtrar_apenas_ineditas(lista_ofertas: List[Dict]) -> List[Dict]:
    """Descarta ofertas que já existem no banco (uma consulta em lote, não uma por oferta)."""
    com_id: List[Dict] = []
    sem_id = 0
    for promo in lista_ofertas:
        url = (promo.get("url_produto") or "").strip()
        pid = promo.get("produto_id") or database.extrair_produto_id(url)
        if pid:
            promo["produto_id"] = str(pid)
            com_id.append(promo)
        else:
            sem_id += 1

    if sem_id:
        logger.warning("%d ofertas descartadas por falta de ID de produto.", sem_id)

    ja_publicados = database.ids_ja_publicados(p["produto_id"] for p in com_id)
    return [p for p in com_id if p["produto_id"] not in ja_publicados]


def _obter_cotas_envio() -> tuple:
    ml_cota = int(getattr(config, "ML_COUNT_PER_RUN", 1))
    shopee_cota = int(getattr(config, "SHOPEE_COUNT_PER_RUN", 2))
    return ml_cota, shopee_cota


def _candidatos_ml(url_categoria: Optional[str], limite: int) -> List[Dict]:
    brutas = mercado_livre.buscar_ofertas(url_categoria=url_categoria) or []
    ineditas = _filtrar_apenas_ineditas(brutas)
    return promocoes.preparar_promocoes_para_publicar(
        ineditas, limite=limite, desconto_min=getattr(config, "MELI_MIN_DESCONTO", None)
    )


def _candidatos_shopee(limite: int) -> List[Dict]:
    if limite <= 0 or not shopee:
        return []
    fn_buscar = getattr(shopee, "buscar_ofertas_shopee", getattr(shopee, "buscar_ofertas", None))
    if not fn_buscar:
        return []
    try:
        url_shopee = _proximo_nicho_shopee()
        brutas = (fn_buscar(url_categoria=url_shopee) if url_shopee else fn_buscar()) or []
        logger.info("Shopee: %d ofertas brutas recebidas", len(brutas))
        ineditas = _filtrar_apenas_ineditas(brutas)
        logger.info("Shopee: %d ofertas inéditas", len(ineditas))
        # Mesmo pipeline do ML: categoria pelo título, faixa de preço, desconto suspeito, variedade.
        return promocoes.preparar_promocoes_para_publicar(
            ineditas, limite=limite, desconto_min=getattr(config, "SHOPEE_MIN_DESCONTO", None)
        )
    except Exception as err_shopee:
        logger.error("Falha ao buscar ofertas Shopee: %s", err_shopee, exc_info=True)
        return []


def _publicar_lote(
    candidatos: List[Dict],
    cota: int,
    limite_global: int,
    delay_segundos: int,
    interromper_se_sessao_expirada: bool = False,
) -> int:
    """Publica até `cota` ofertas, passando para o próximo candidato se um falhar."""
    enviadas = 0
    for promo in candidatos:
        if enviadas >= cota or enviadas >= limite_global:
            break
        if _processar_e_publicar_oferta(promo, delay_segundos):
            enviadas += 1
        elif interromper_se_sessao_expirada and afiliados.sessao_expirada():
            break
    return enviadas


def executar_ciclo(nicho: Optional[dict] = None) -> int:
    global _proxima_tentativa_afiliado
    database.inicializar_banco()

    nome_nicho = nicho.get("nome", "Geral") if nicho else "Geral"
    url_categoria = nicho.get("url") if nicho else None
    delay_segundos = getattr(config, "TELEGRAM_SEND_DELAY_SECONDS", 10)

    ml_cota, shopee_cota = _obter_cotas_envio()
    max_global = int(getattr(config, "MAX_PROMOTIONS_PER_RUN", 3))

    logger.info("=== Iniciando ciclo de busca: Nicho [%s] ===", nome_nicho)

    # 1. Mercado Livre (pausado enquanto a sessão de afiliado estiver expirada)
    ml_candidatos: List[Dict] = []
    if ml_cota > 0:
        if afiliados.sessao_expirada() and time.time() < _proxima_tentativa_afiliado:
            logger.error(
                "Sessão de afiliado do ML expirada: Mercado Livre pausado. "
                "Renove MELI_CSRF_TOKEN/MELI_COOKIE_HEADER no .env e reinicie o bot."
            )
        else:
            ml_candidatos = _candidatos_ml(url_categoria, ml_cota * CANDIDATOS_POR_VAGA)

    # 2. Shopee
    shopee_candidatos = _candidatos_shopee(shopee_cota * CANDIDATOS_POR_VAGA) if shopee_cota > 0 else []

    logger.info(
        "Candidatos para [%s]: %d ML + %d Shopee (cota %d + %d, teto global %d).",
        nome_nicho, len(ml_candidatos), len(shopee_candidatos), ml_cota, shopee_cota, max_global,
    )

    # 3. Publicação
    enviadas_ml = _publicar_lote(
        ml_candidatos, ml_cota, max_global, delay_segundos, interromper_se_sessao_expirada=True
    )
    enviadas_shopee = _publicar_lote(
        shopee_candidatos, shopee_cota, max_global - enviadas_ml, delay_segundos
    )

    if afiliados.sessao_expirada():
        _proxima_tentativa_afiliado = time.time() + INTERVALO_RETENTATIVA_AFILIADO_S

    enviadas = enviadas_ml + enviadas_shopee
    logger.info("Ciclo [%s] finalizado. Promoções processadas: %d", nome_nicho, enviadas)
    return enviadas


def rodar_loop():
    """Executa a fila cíclica sequencial (Round Robin) pelos nichos cadastrados."""
    logger.info("Iniciando loop do bot com rotação de nichos...")
    if getattr(config, "TEST_MODE", False):
        logger.warning("⚠️ TEST_MODE ATIVO: nada será enviado nem salvo no banco.")

    nichos = getattr(mercado_livre, "NICHOS_ESTRATEGICOS", [])
    total_nichos = len(nichos)
    indice_atual = 0

    try:
        while True:
            if em_horario_de_silencio():
                logger.info(
                    "Modo noturno ativo (%02dh–%02dh). Nova checagem em 10 min.",
                    getattr(config, "HORARIO_SILENCIO_INICIO", 23),
                    getattr(config, "HORARIO_SILENCIO_FIM", 7),
                )
                time.sleep(600)
                continue

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
                "Aguardando %d minutos. Próximo nicho na fila: [%s]", intervalo_min, proximo_nicho
            )
            time.sleep(intervalo_min * 60)
    except KeyboardInterrupt:
        logger.info("Bot interrompido pelo usuário (Ctrl+C).")