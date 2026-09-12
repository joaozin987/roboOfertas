"""
Regras de negócio das promoções — Fase 4.

Responsável por:
- filtrar ofertas por categoria sem bloquear os nichos oficiais;
- filtrar por desconto mínimo;
- filtrar por faixa de preço;
- remover duplicados encontrados na mesma execução;
- calcular pontuação balanceada para cada oferta;
- selecionar as melhores promoções;
- montar a mensagem final formatada para o Telegram.
"""

import logging
import re
import unicodedata

from app import config

logger = logging.getLogger(__name__)

# ============================================================
# CATEGORIAS E PALAVRAS-CHAVE (FALLBACK)
# ============================================================

CATEGORIAS = {
    "tecnologia": [
        "celular", "smartphone", "iphone", "samsung", "xiaomi", "motorola",
        "notebook", "laptop", "computador", "pc gamer", "monitor", "teclado",
        "mouse", "headset", "fone", "fone bluetooth", "airpods", "ssd",
        "hd externo", "memoria ram", "placa de video", "placa mae", "processador",
        "carregador", "power bank", "smartwatch", "relogio inteligente", "tablet"
    ],
    "moda": [
        "camisa", "camiseta", "blusa", "calca", "jaqueta", "casaco", "moletom",
        "vestido", "saia", "short", "bermuda", "cueca", "calcinha", "sutia",
        "meia", "tenis", "sapato", "sandalia", "chinelo", "bota", "mochila",
        "bolsa", "mala", "cinto", "bone", "relogio"
    ],
    "cozinha": [
        "air fryer", "airfryer", "fritadeira", "liquidificador", "mixer",
        "batedeira", "cafeteira", "panela", "frigideira", "panela de pressao",
        "jogo de panelas", "forno", "microondas", "sanduicheira", "churrasqueira",
        "processador de alimentos", "potes", "faqueiro", "garrafa termica"
    ],
    "casa": [
        "organizador", "caixa organizadora", "tapete", "cortina", "luminaria",
        "abajur", "lampada", "ventilador", "aspirador", "aspirador robo", "mop",
        "limpeza", "ferro de passar", "espelho", "travesseiro", "edredom", "cobertor"
    ],
    "moveis": [
        "mesa", "escrivaninha", "cadeira", "cadeira gamer", "cadeira de escritorio",
        "sofa", "poltrona", "cama", "colchao", "guarda roupa", "armario", "comoda",
        "gaveteiro", "estante", "rack", "painel para tv"
    ],
    "games": [
        "playstation", "ps5", "ps4", "xbox", "xbox series", "nintendo",
        "nintendo switch", "console", "controle ps5", "controle xbox", "joystick", "game"
    ],
    "esportes": [
        "suplemento", "whey", "creatina", "halter", "anilhas", "colchonete",
        "elastico", "garrafa", "bicicleta", "corda de pular", "luva de treino"
    ],
    "ferramentas": [
        "furadeira", "parafusadeira", "esmerilhadeira", "serra", "lixadeira",
        "compressor", "chave de fenda", "kit ferramentas", "alicate", "martelo", "trena"
    ],
}


# ============================================================
# NORMALIZAÇÃO DE TEXTO
# ============================================================

def _normalizar_texto(texto: str) -> str:
    """Remove acentos, converte para minúsculo e normaliza espaços."""
    if not texto:
        return ""
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", texto)


# ============================================================
# CATEGORIAS ATIVAS
# ============================================================

def obter_categorias_alvo() -> list[str]:
    """Lê CATEGORIAS_ALVO do config. Se vazio, aceita todas."""
    configuracao = getattr(config, "CATEGORIAS_ALVO", "")
    if not configuracao:
        return list(CATEGORIAS.keys())

    categorias = []
    for cat in configuracao.split(","):
        cat_norm = _normalizar_texto(cat).strip()
        if cat_norm:
            categorias.append(cat_norm)
    return categorias


# ============================================================
# IDENTIFICAÇÃO DA CATEGORIA
# ============================================================

def identificar_categoria(promocao: dict) -> str:
    """
    Retorna a categoria atribuída na coleta ou deduz pelo título via palavras-chave.
    """
    # 1. Se a coleta do nicho já determinou uma categoria válida, preserva ela
    cat_existente = promocao.get("categoria")
    if cat_existente and cat_existente.lower() not in ["sem categoria", "ofertas", "destaques"]:
        return cat_existente

    # 2. Fallback por palavras-chave no título
    titulo = _normalizar_texto(promocao.get("titulo", ""))
    if not titulo:
        return "Destaques"

    melhor_categoria = "Destaques"
    maior_pontuacao = 0

    for categoria, palavras in CATEGORIAS.items():
        pontuacao = 0
        for palavra in palavras:
            palavra_norm = _normalizar_texto(palavra)
            if palavra_norm in titulo:
                pontuacao += len(palavra_norm.split())

        if pontuacao > maior_pontuacao:
            maior_pontuacao = pontuacao
            melhor_categoria = categoria.capitalize()

    return melhor_categoria


# ============================================================
# FILTRO POR CATEGORIA
# ============================================================

def filtrar_por_categoria(promocoes: list[dict]) -> list[dict]:
    """
    Atribui a categoria correta e só filtra se CATEGORIAS_ALVO for restritivo.
    """
    aprovadas = []
    config_alvo = getattr(config, "CATEGORIAS_ALVO", "").strip()
    categorias_alvo = [c.strip().lower() for c in config_alvo.split(",") if c.strip()] if config_alvo else []

    for promocao in promocoes:
        categoria = identificar_categoria(promocao)
        promocao["categoria"] = categoria

        # Se CATEGORIAS_ALVO foi explicitamente preenchido no .env, filtra por ele
        if categorias_alvo:
            cat_norm = _normalizar_texto(categoria)
            # Permite se a categoria coincidir ou se for originária do nicho
            if any(alvo in cat_norm for alvo in categorias_alvo):
                aprovadas.append(promocao)
        else:
            # Sem restrição rígida: aproveita 100% dos produtos do nicho
            aprovadas.append(promocao)

    logger.info(
        "%s de %s ofertas pertencem às categorias válidas.",
        len(aprovadas),
        len(promocoes),
    )
    return aprovadas


# ============================================================
# FILTRO DE DESCONTO E PREÇO
# ============================================================

def filtrar_ofertas(promocoes: list[dict]) -> list[dict]:
    """Aplica os limites de DESCONTO_MINIMO, PRECO_MINIMO e PRECO_MAXIMO."""
    aprovadas = []

    desconto_min = getattr(config, "DESCONTO_MINIMO", 15.0)
    preco_min = getattr(config, "PRECO_MINIMO", 20.0)
    preco_max = getattr(config, "PRECO_MAXIMO", 50000.0)

    for promocao in promocoes:
        desconto = promocao.get("desconto")
        preco_atual = promocao.get("preco_atual")

        if desconto is None or preco_atual is None:
            continue

        if desconto < desconto_min:
            continue

        if preco_atual < preco_min or preco_atual > preco_max:
            continue

        aprovadas.append(promocao)

    logger.info(
        "%s de %s ofertas aprovadas (desconto >= %s%%, preço entre R$ %s e R$ %s)",
        len(aprovadas),
        len(promocoes),
        desconto_min,
        preco_min,
        preco_max,
    )
    return aprovadas


# ============================================================
# REMOVER DUPLICADAS
# ============================================================

def remover_duplicadas(promocoes: list[dict]) -> list[dict]:
    """Remove ofertas repetidas na mesma rodada pela URL."""
    vistos = set()
    unicas = []

    for promocao in promocoes:
        url = promocao.get("url_produto")
        if not url or url in vistos:
            continue
        vistos.add(url)
        unicas.append(promocao)

    return unicas


# ============================================================
# PONTUAÇÃO DAS OFERTAS
# ============================================================

def calcular_pontuacao(promocao: dict) -> float:
    """Calcula score de relevância da oferta."""
    pontuacao = 0.0
    desconto = promocao.get("desconto") or 0
    preco_atual = promocao.get("preco_atual") or 0
    preco_anterior = promocao.get("preco_anterior")

    # Pontos pelo percentual de desconto
    pontuacao += desconto / 4

    if desconto >= 30:
        pontuacao += 5
    if desconto >= 50:
        pontuacao += 8

    # Presença de preço original comprovado
    if preco_anterior:
        pontuacao += 4

    # Faixas de preço com alta conversão
    if 40 <= preco_atual <= 300:
        pontuacao += 6
    elif 300 < preco_atual <= 1500:
        pontuacao += 4

    return round(pontuacao, 2)


def pontuar_ofertas(promocoes: list[dict]) -> list[dict]:
    for promocao in promocoes:
        promocao["pontuacao"] = calcular_pontuacao(promocao)
    return promocoes


# ============================================================
# SELECIONAR MELHORES
# ============================================================

def selecionar_melhores(promocoes: list[dict], limite: int | None = None) -> list[dict]:
    limite = limite if limite is not None else getattr(config, "MAX_PROMOTIONS_PER_RUN", 3)
    pontuar_ofertas(promocoes)

    ordenadas = sorted(
        promocoes,
        key=lambda p: (p.get("pontuacao") or 0, p.get("desconto") or 0),
        reverse=True
    )

    selecionadas = ordenadas[:limite]
    logger.info("%s promoções selecionadas para publicação", len(selecionadas))

    for promocao in selecionadas:
        logger.info(
            "🏆 %s | %s | %.1f%% desconto | R$ %.2f | pontuação %.2f",
            promocao.get("categoria", "Destaque"),
            promocao.get("titulo", "Produto"),
            promocao.get("desconto") or 0,
            promocao.get("preco_atual") or 0,
            promocao.get("pontuacao") or 0,
        )

    return selecionadas


# ============================================================
# FORMATAÇÃO DE PREÇO
# ============================================================

def _formatar_preco(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ============================================================
# MONTAR MENSAGEM
# ============================================================

def montar_mensagem(promocao: dict) -> str:
    """Monta a mensagem formatada para o Telegram."""
    titulo = promocao.get("titulo", "Produto")
    preco_atual = promocao.get("preco_atual")
    preco_anterior = promocao.get("preco_anterior")
    desconto = promocao.get("desconto")
    cupom = promocao.get("cupom") or getattr(config, "CUPOM_DESCONTO", None)
    link = promocao.get("url_afiliado") or promocao.get("url_produto")
    categoria = promocao.get("categoria", "Destaque")

    # Mapeamento de emojis por nicho
    emojis = {
        "tecnologia": "💻",
        "smartphones & celulares": "📱",
        "celulares": "📱",
        "moda & calcados": "👕",
        "moda": "👕",
        "calcados": "👟",
        "cozinha": "🍳",
        "casa": "🏠",
        "casa & eletrodomesticos": "🏠",
        "moveis": "🪑",
        "games": "🎮",
        "esportes & suplementos": "💪",
        "esportes": "💪",
        "beleza & cuidados": "✨",
        "ferramentas & construcao": "🔧",
        "ferramentas": "🔧",
    }

    cat_slug = _normalizar_texto(categoria)
    emoji_header = "🛍️"
    for key, icone in emojis.items():
        if key in cat_slug:
            emoji_header = icone
            break

    linhas = [
        "🔥 OFERTA DO DIA",
        "",
        f"{emoji_header} {categoria.upper()}",
        "",
        f"🛍️ {titulo}",
        "",
    ]

    if preco_anterior:
        linhas.append(f"💰 De: {_formatar_preco(preco_anterior)}")

    if preco_atual is not None:
        linhas.append(f"🔥 Por: {_formatar_preco(preco_atual)}")

    if desconto:
        linhas.append(f"📉 Desconto: {desconto:.0f}%")

    if cupom:
        linhas.extend(["", f"🏷️ CUPOM: {cupom}"])

    linhas.extend([
        "",
        "🛒 COMPRAR AGORA:",
        link,
        "",
        "⚠️ Preço e disponibilidade podem mudar sem aviso.",
    ])

    return "\n".join(linhas)


# ============================================================
# PIPELINE COMPLETO
# ============================================================

def preparar_promocoes_para_publicar(promocoes_brutas: list[dict]) -> list[dict]:
    logger.info("Iniciando processamento de %s ofertas...", len(promocoes_brutas))

    sem_duplicadas = remover_duplicadas(promocoes_brutas)
    logger.info("Após remoção de duplicados: %s ofertas.", len(sem_duplicadas))

    por_categoria = filtrar_por_categoria(sem_duplicadas)
    aprovadas = filtrar_ofertas(por_categoria)
    selecionadas = selecionar_melhores(aprovadas)

    return selecionadas