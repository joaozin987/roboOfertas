"""
Orquestrador principal do bot de promoções (Modo 24/7 sem pausa noturna).
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app import afiliados, config, database, mercado_livre, promocoes, telegram, whatsapp
from app import mercado_livre_ofertas_api
from app.ml_upload import caminho_lote

try:
    from app import shopee
except ImportError:
    shopee = None

logger = logging.getLogger(__name__)

_shopee_idx = 0
_proxima_tentativa_afiliado = 0.0
_aviso_fuso_emitido = False
INTERVALO_RETENTATIVA_AFILIADO_S = 30 * 60
CANDIDATOS_POR_VAGA = 3
ML_JSON_MAX_IDADE_HORAS = 12


def _agora() -> datetime:
    global _aviso_fuso_emitido
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(getattr(config, "TIMEZONE", "America/Sao_Paulo")))
    except Exception:
        if not _aviso_fuso_emitido:
            logger.warning("Fuso horário indisponível. Usando hora local.")
            _aviso_fuso_emitido = True
        return datetime.now()


def em_horario_de_silencio(agora: Optional[datetime] = None) -> bool:
    # Modo noturno desativado permanentemente para rodar 24h
    return False


def _proximo_nicho_shopee():
    global _shopee_idx
    nichos = getattr(shopee, "NICHOS_ESTRATEGICOS", []) if shopee else []
    if not nichos:
        return None
    url = nichos[_shopee_idx % len(nichos)]["url"]
    _shopee_idx += 1
    return url


def enviar_mensagem_teste() -> bool:
    logger.info("Enviando mensagem de teste para os canais...")
    mensagem = "🤖 Bot de Promoções conectado e rodando 24h!"
    sucesso_tg = telegram.enviar_mensagem(mensagem) if hasattr(telegram, "enviar_mensagem") else False
    sucesso_wpp = whatsapp.enviar_mensagem(mensagem) if hasattr(whatsapp, "enviar_mensagem") else False
    return sucesso_tg or sucesso_wpp


def _publicar_no_telegram(texto_mensagem: str, imagem_url: Optional[str] = None) -> bool:
    if hasattr(telegram, "publicar_promocao"):
        return telegram.publicar_promocao(texto_mensagem, imagem_url)
    if hasattr(telegram, "enviar_mensagem"):
        return telegram.enviar_mensagem(texto_mensagem)
    return False


def _publicar_no_whatsapp(texto_mensagem: str, imagem_url: Optional[str] = None) -> bool:
    if imagem_url and hasattr(whatsapp, "enviar_foto"):
        try:
            if whatsapp.enviar_foto(imagem_url, texto_mensagem):
                return True
        except Exception:
            pass
    if hasattr(whatsapp, "enviar_mensagem"):
        return whatsapp.enviar_mensagem(texto_mensagem)
    return False


def _enviar_para_telegram(promo: dict, texto_mensagem: str, imagem_url: Optional[str] = None) -> bool:
    origem = (promo.get("origem") or "").lower()
    if origem == "shopee" and hasattr(telegram, "publicar_com_link_oculto"):
        try:
            return telegram.publicar_com_link_oculto(texto_mensagem, promo.get("url_afiliado", ""), imagem_url)
        except Exception:
            pass
    return _publicar_no_telegram(texto_mensagem, imagem_url)


def _processar_e_publicar_oferta(promo: dict, delay_segundos: int) -> bool:
    url_produto = (promo.get("url_produto") or "").strip()
    produto_id = promo.get("produto_id") or database.extrair_produto_id(url_produto)

    if not produto_id:
        return False

    promo["produto_id"] = str(produto_id)

    if database.produto_ja_publicado(promo["produto_id"]):
        return False

    origem = (promo.get("origem") or "").lower()
    if not promo.get("url_afiliado"):
        if origem == "shopee":
            return False
        link_afiliado = mercado_livre.montar_link_afiliado(url_produto)
        if not link_afiliado:
            return False
        promo["url_afiliado"] = link_afiliado

    texto_mensagem = promocoes.montar_mensagem(promo)
    imagem_url = promo.get("imagem")

    if getattr(config, "TEST_MODE", False):
        return True

    sucesso_tg = _enviar_para_telegram(promo, texto_mensagem, imagem_url)
    time.sleep(2)
    sucesso_wpp = _publicar_no_whatsapp(texto_mensagem, imagem_url)

    if sucesso_tg or sucesso_wpp:
        database.salvar_promocao(promo)
        time.sleep(delay_segundos)
        return True

    return False


def _filtrar_apenas_ineditas(lista_ofertas: List[Dict]) -> List[Dict]:
    com_id: List[Dict] = []
    for promo in lista_ofertas:
        url = (promo.get("url_produto") or "").strip()
        pid = promo.get("produto_id") or database.extrair_produto_id(url)
        if pid:
            promo["produto_id"] = str(pid)
            com_id.append(promo)

    ja_publicados = database.ids_ja_publicados(p["produto_id"] for p in com_id)
    return [p for p in com_id if p["produto_id"] not in ja_publicados]


def _obter_cotas_envio() -> tuple:
    return int(getattr(config, "ML_COUNT_PER_RUN", 1)), int(getattr(config, "SHOPEE_COUNT_PER_RUN", 2))


def _ler_ofertas_ml_json() -> List[Dict]:
    """Prioriza o volume e recorre ao lote do deploy se ele estiver atual."""
    campanha = Path(__file__).resolve().parents[1] / "data" / "ml_campanha.json"
    if campanha.is_file():
        agendadas = _ler_lote_ml_atual(campanha, aceitar_campanha=True)
        if agendadas:
            return agendadas

    caminho = caminho_lote()
    ofertas = _ler_lote_ml_atual(caminho)
    if ofertas:
        return ofertas

    alternativa = Path(__file__).resolve().parents[1] / "data" / "ml_ofertas.json"
    if alternativa == caminho or not alternativa.is_file():
        return []
    ofertas = _ler_lote_ml_atual(alternativa)
    if ofertas:
        logger.info("ML JSON: usando lote atual do deploy (%d ofertas).", len(ofertas))
    return ofertas


def _ler_lote_ml_atual(caminho: Path, *, aceitar_campanha: bool = False) -> List[Dict]:
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
    except Exception as erro:
        logger.warning("ML JSON: erro lendo %s: %s", caminho, erro)
        return []

    if not isinstance(dados, dict) or not isinstance(dados.get("ofertas"), list):
        logger.warning("ML JSON: formato inválido em %s.", caminho)
        return []

    try:
        gerado = datetime.fromisoformat(dados.get("gerado_em", ""))
        agora = datetime.now(gerado.tzinfo) if gerado.tzinfo else datetime.now()
        idade_h = (agora - gerado).total_seconds() / 3600
    except (TypeError, ValueError):
        logger.warning("ML JSON: data de geração ausente ou inválida; ignorando arquivo.")
        return []

    campanha = dados.get("campanha")
    if aceitar_campanha and isinstance(campanha, dict):
        try:
            inicio = datetime.fromisoformat(campanha["inicio"])
            fim = datetime.fromisoformat(campanha["fim"])
            ativa = gerado <= inicio <= agora < fim and (fim - gerado).total_seconds() <= 96 * 3600
        except (KeyError, TypeError, ValueError):
            return []
        if ativa:
            return [
                dict(oferta, _fila_ml=True, preco_consultado_em=gerado)
                for oferta in dados["ofertas"]
                if isinstance(oferta, dict) and _oferta_na_janela(oferta, agora)
            ]
        return []

    if idade_h < 0 or idade_h > ML_JSON_MAX_IDADE_HORAS:
        logger.warning(
            "ML JSON: arquivo vencido (%.1f h; limite %d h); tentando busca atual.",
            idade_h,
            ML_JSON_MAX_IDADE_HORAS,
        )
        return []

    return dados.get("ofertas", [])


def _oferta_na_janela(oferta: dict, agora: datetime) -> bool:
    try:
        horario = datetime.fromisoformat(oferta["publicar_em"])
        return 0 <= (agora - horario).total_seconds() < 10 * 60
    except (KeyError, TypeError, ValueError):
        return False


def _candidatos_ml(url_categoria: Optional[str], limite: int) -> List[Dict]:
    if os.getenv("ML_USAR_JSON", "true").strip().lower() == "true":
        todas = _ler_ofertas_ml_json()
        nome = next((n["nome"] for n in mercado_livre.NICHOS_ESTRATEGICOS if n["url"] == url_categoria), None)
        brutas = [o for o in todas if o.get("_fila_ml") or not nome or o.get("categoria") == nome]
        if brutas:
            ineditas = _filtrar_apenas_ineditas(brutas)
            aprovadas = promocoes.preparar_promocoes_para_publicar(
                ineditas, limite=limite, desconto_min=getattr(config, "MELI_MIN_DESCONTO", None)
            )
            logger.info(
                "ML JSON [%s]: %d lidas, %d inéditas com ID, %d selecionadas.",
                nome or "todas", len(brutas), len(ineditas), len(aprovadas),
            )
            if aprovadas:
                return aprovadas
        logger.info(
            "ML JSON [%s]: sem candidatas publicáveis; tentando busca direta.",
            nome or "todas",
        )

    brutas = mercado_livre_ofertas_api.buscar_ofertas(url_categoria)
    if not brutas:
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
        ineditas = _filtrar_apenas_ineditas(brutas)
        logger.info("Shopee: %d de %d ofertas inéditas com ID.", len(ineditas), len(brutas))
        return promocoes.preparar_promocoes_para_publicar(
            ineditas, limite=limite, desconto_min=config.SHOPEE_MIN_DESCONTO,
            preco_min=config.SHOPEE_PRECO_MINIMO,
        )
    except Exception:
        logger.exception("Shopee: falha ao preparar ofertas.")
        return []


def _publicar_lote(candidatos: List[Dict], cota: int, limite_global: int, delay_segundos: int, interromper_se_sessao_expirada: bool = False) -> int:
    enviadas = 0
    for promo in candidatos:
        if enviadas >= cota or enviadas >= limite_global:
            break
        if _processar_e_publicar_oferta(promo, delay_segundos):
            enviadas += 1
        elif interromper_se_sessao_expirada and afiliados.sessao_expirada():
            break
    return enviadas


def _aguardar_proxima_rodada(intervalo_min: int) -> None:
    intervalo_min = max(0, int(intervalo_min))
    logger.info("Aguardando %d minutos para a próxima busca.", intervalo_min)
    time.sleep(intervalo_min * 60)


def executar_ciclo(nicho: Optional[dict] = None) -> int:
    global _proxima_tentativa_afiliado
    database.inicializar_banco()

    nome_nicho = nicho.get("nome", "Geral") if nicho else "Geral"
    url_categoria = nicho.get("url") if nicho else None
    delay_segundos = getattr(config, "TELEGRAM_SEND_DELAY_SECONDS", 10)

    ml_cota, shopee_cota = _obter_cotas_envio()
    max_global = int(getattr(config, "MAX_PROMOTIONS_PER_RUN", 3))

    logger.info("=== Iniciando ciclo de busca: Nicho [%s] ===", nome_nicho)

    ml_candidatos: List[Dict] = []
    if ml_cota > 0:
        if afiliados.sessao_expirada() and time.time() < _proxima_tentativa_afiliado:
            pass
        else:
            ml_candidatos = _candidatos_ml(url_categoria, ml_cota * CANDIDATOS_POR_VAGA)

    shopee_candidatos = _candidatos_shopee(shopee_cota * CANDIDATOS_POR_VAGA) if shopee_cota > 0 else []

    enviadas_ml = _publicar_lote(ml_candidatos, ml_cota, max_global, delay_segundos, interromper_se_sessao_expirada=True)
    enviadas_shopee = _publicar_lote(shopee_candidatos, shopee_cota, max_global - enviadas_ml, delay_segundos)

    if afiliados.sessao_expirada():
        _proxima_tentativa_afiliado = time.time() + INTERVALO_RETENTATIVA_AFILIADO_S

    enviadas = enviadas_ml + enviadas_shopee
    logger.info("Ciclo [%s] finalizado. Promoções processadas: %d", nome_nicho, enviadas)
    return enviadas


def rodar_loop():
    logger.info("Iniciando loop do bot com rotação de nichos...")
    nichos = getattr(mercado_livre, "NICHOS_ESTRATEGICOS", [])
    total_nichos = len(nichos)
    indice_atual = 0

    try:
        while True:
            nicho_atual = nichos[indice_atual] if nichos else None

            try:
                executar_ciclo(nicho=nicho_atual)
            except Exception as erro:
                logger.error("Erro durante o ciclo: %s", erro, exc_info=True)

            if nichos:
                indice_atual = (indice_atual + 1) % total_nichos
            intervalo_min = getattr(config, "CHECK_INTERVAL_MINUTES", 4)
            _aguardar_proxima_rodada(intervalo_min)
    except KeyboardInterrupt:
        logger.info("Bot interrompido pelo usuário.")
