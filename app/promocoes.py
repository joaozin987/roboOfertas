"""
Regras de negócio das promoções — Fase 4.

Responsável por:
- filtrar ofertas ruins (desconto mínimo, faixa de preço);
- remover duplicados encontrados na mesma execução;
- selecionar as melhores promoções (respeitando MAX_PROMOTIONS_PER_RUN);
- montar a mensagem final que será publicada no Telegram.

A verificação de "já publicado antes" (banco de dados) fica pra Fase 2/5
— este módulo só cuida do que dá pra decidir com os dados da própria
execução atual.
"""

import logging

from app import config

logger = logging.getLogger(__name__)


def filtrar_ofertas(promocoes: list[dict]) -> list[dict]:
    """
    Aplica os filtros configurados (DESCONTO_MINIMO, PRECO_MINIMO,
    PRECO_MAXIMO) e descarta qualquer oferta sem desconto calculável.
    """
    aprovadas = []

    for promocao in promocoes:
        desconto = promocao.get("desconto")
        preco_atual = promocao.get("preco_atual")

        if desconto is None or preco_atual is None:
            continue

        if desconto < config.DESCONTO_MINIMO:
            continue

        if preco_atual < config.PRECO_MINIMO or preco_atual > config.PRECO_MAXIMO:
            continue

        aprovadas.append(promocao)

    logger.info(
        "%s de %s ofertas aprovadas (desconto >= %s%%, preço entre R$ %s e R$ %s)",
        len(aprovadas),
        len(promocoes),
        config.DESCONTO_MINIMO,
        config.PRECO_MINIMO,
        config.PRECO_MAXIMO,
    )
    return aprovadas


def remover_duplicadas(promocoes: list[dict]) -> list[dict]:
    """
    Remove ofertas repetidas dentro da mesma lista (o scraper às vezes
    traz o mesmo produto em páginas diferentes). Usa `url_produto` como
    identificador único.
    """
    vistos = set()
    unicas = []

    for promocao in promocoes:
        identificador = promocao.get("url_produto")
        if not identificador or identificador in vistos:
            continue
        vistos.add(identificador)
        unicas.append(promocao)

    return unicas


def selecionar_melhores(promocoes: list[dict], limite: int | None = None) -> list[dict]:
    """
    Ordena as ofertas pelo maior desconto e devolve no máximo `limite`
    (por padrão, MAX_PROMOTIONS_PER_RUN).
    """
    limite = limite or config.MAX_PROMOTIONS_PER_RUN
    ordenadas = sorted(promocoes, key=lambda p: p.get("desconto") or 0, reverse=True)
    selecionadas = ordenadas[:limite]

    logger.info("%s promoções selecionadas para publicação", len(selecionadas))
    return selecionadas


def _formatar_preco(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def montar_mensagem(promocao: dict) -> str:
    """
    Monta a mensagem final no formato definido no README, usando o link
    de afiliado (ou o link normal, se não houver tag configurada) e
    incluindo o cupom apenas quando disponível.
    """
    titulo = promocao.get("titulo", "Produto")
    preco_atual = promocao.get("preco_atual")
    preco_anterior = promocao.get("preco_anterior")
    desconto = promocao.get("desconto")
    cupom = promocao.get("cupom") or config.CUPOM_DESCONTO
    link = promocao.get("url_afiliado") or promocao.get("url_produto")

    linhas = ["🔥 OFERTA DO DIA", "", f"🎧 {titulo}", ""]

    if preco_anterior:
        linhas.append(f"💰 De: {_formatar_preco(preco_anterior)}")
    linhas.append(f"🔥 Por: {_formatar_preco(preco_atual)}")
    if desconto:
        linhas.append(f"📉 Desconto: {desconto:.0f}%")

    if cupom:
        linhas.append("")
        linhas.append(f"🏷️ CUPOM: {cupom}")

    linhas.append("")
    linhas.append("🛒 COMPRAR AGORA:")
    linhas.append(link)
    linhas.append("")
    linhas.append("⚠️ Preço e disponibilidade podem mudar sem aviso.")

    return "\n".join(linhas)


def preparar_promocoes_para_publicar(promocoes_brutas: list[dict]) -> list[dict]:
    """
    Pipeline completo desta fase: remove duplicados, filtra e seleciona
    as melhores ofertas encontradas na execução atual.
    """
    sem_duplicadas = remover_duplicadas(promocoes_brutas)
    aprovadas = filtrar_ofertas(sem_duplicadas)
    return selecionar_melhores(aprovadas)
