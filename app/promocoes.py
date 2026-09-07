"""
Regras de negócio das promoções — Fase 4.

Responsável por:
- filtrar ofertas por categoria;
- filtrar por desconto mínimo;
- filtrar por faixa de preço;
- remover duplicados encontrados na mesma execução;
- identificar a categoria do produto;
- calcular uma pontuação para cada oferta;
- selecionar as melhores promoções;
- montar a mensagem final para o Telegram.

A verificação de "já publicado antes" fica no database.py/bot.py.
"""

import logging
import re
import unicodedata

from app import config

logger = logging.getLogger(__name__)


# ============================================================
# CATEGORIAS E PALAVRAS-CHAVE
# ============================================================

CATEGORIAS = {

    "tecnologia": [
        "celular",
        "smartphone",
        "iphone",
        "samsung",
        "xiaomi",
        "motorola",
        "notebook",
        "laptop",
        "computador",
        "pc gamer",
        "monitor",
        "monitor gamer",
        "teclado",
        "mouse",
        "mouse gamer",
        "headset",
        "fone",
        "fone bluetooth",
        "airpods",
        "ssd",
        "hd externo",
        "memoria ram",
        "memoria",
        "placa de video",
        "placa mae",
        "processador",
        "cpu",
        "gpu",
        "fonte de computador",
        "gabinete",
        "webcam",
        "microfone",
        "tablet",
        "smart tv",
        "televisao",
        "tv",
        "tv box",
        "chromecast",
        "projetor",
        "carregador",
        "carregador sem fio",
        "cabo usb",
        "cabo hdmi",
        "roteador",
        "wifi",
        "impressora",
        "camera",
        "camera de seguranca",
        "smartwatch",
        "relogio inteligente",
    ],

    "cozinha": [
        "air fryer",
        "airfryer",
        "fritadeira",
        "liquidificador",
        "mixer",
        "batedeira",
        "cafeteira",
        "cafeira",
        "panela",
        "frigideira",
        "panela de pressao",
        "jogo de panelas",
        "jogo de frigideiras",
        "forma",
        "assadeira",
        "forno",
        "microondas",
        "micro-ondas",
        "sandwichera",
        "sanduicheira",
        "churrasqueira",
        "grill",
        "processador de alimentos",
        "espremedor",
        "torneira gourmet",
        "purificador",
        "filtro de agua",
        "garrafa termica",
        "garrafa",
        "pote",
        "potes",
        "potes hermeticos",
        "organizador de cozinha",
        "utensilios de cozinha",
        "utensilio de cozinha",
        "faqueiro",
        "talheres",
        "pratos",
        "copos",
        "xicara",
        "caneca",
    ],

    "casa": [
        "organizador",
        "organizador de gaveta",
        "organizador de armario",
        "caixa organizadora",
        "tapete",
        "tapete sala",
        "tapete quarto",
        "cortina",
        "persiana",
        "luminaria",
        "abajur",
        "lampada",
        "lampada led",
        "ventilador",
        "circulador de ar",
        "aspirador",
        "aspirador robo",
        "vassoura",
        "rodo",
        "mop",
        "produtos de limpeza",
        "limpeza",
        "varal",
        "tábua de passar",
        "tabua de passar",
        "ferro de passar",
        "cabide",
        "espelho",
        "almofada",
        "travesseiro",
        "roupa de cama",
        "edredom",
        "cobertor",
        "decoracao",
        "decoracao de casa",
        "vaso",
        "plantas",
        "relogio de parede",
    ],

    "moveis": [
        "mesa",
        "mesa de computador",
        "mesa gamer",
        "escrivaninha",
        "cadeira",
        "cadeira gamer",
        "cadeira de escritorio",
        "sofa",
        "sofa cama",
        "poltrona",
        "cama",
        "cama box",
        "beliche",
        "colchao",
        "guarda roupa",
        "guarda-roupa",
        "armario",
        "armario de cozinha",
        "comoda",
        "gaveteiro",
        "criado mudo",
        "criado-mudo",
        "estante",
        "rack",
        "painel para tv",
        "aparador",
        "buffet",
        "puff",
        "sapateira",
        "banco",
        "banqueta",
        "mesa de jantar",
        "mesa lateral",
        "mesa de cabeceira",
    ],

    "games": [
        "playstation",
        "playstation 5",
        "ps5",
        "ps4",
        "xbox",
        "xbox series",
        "xbox one",
        "nintendo",
        "nintendo switch",
        "switch",
        "steam deck",
        "console",
        "controle",
        "controle ps5",
        "controle ps4",
        "controle xbox",
        "joystick",
        "gamepad",
        "video game",
        "videogame",
        "game",
        "gamer",
        "cadeira gamer",
        "headset gamer",
        "teclado gamer",
        "mouse gamer",
        "volante gamer",
        "pedal gamer",
        "acessorios gamer",
    ],

    "ferramentas": [
        "furadeira",
        "parafusadeira",
        "furadeira parafusadeira",
        "martelete",
        "esmerilhadeira",
        "serra",
        "serra circular",
        "serra tico tico",
        "lixadeira",
        "plaina",
        "compressor",
        "chave de impacto",
        "chave de fenda",
        "chave philips",
        "chave inglesa",
        "kit ferramentas",
        "kit de ferramentas",
        "ferramenta",
        "ferramentas",
        "alicate",
        "martelo",
        "trena",
        "nivel",
        "nivel a laser",
        "broca",
        "jogo de chaves",
        "caixa de ferramentas",
        "torquimetro",
        "solda",
        "ferro de solda",
    ],
}


# ============================================================
# NORMALIZAÇÃO DE TEXTO
# ============================================================

def _normalizar_texto(texto: str) -> str:
    """
    Remove acentos, converte para minúsculo e normaliza espaços.
    """

    if not texto:
        return ""

    texto = str(texto).lower().strip()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto


# ============================================================
# CATEGORIAS ATIVAS
# ============================================================

def obter_categorias_alvo() -> list[str]:
    """
    Lê CATEGORIAS_ALVO do config/.env.

    Exemplo:

    CATEGORIAS_ALVO=tecnologia,cozinha,casa,moveis

    Se não estiver configurado, utiliza todas as categorias.
    """

    configuracao = getattr(
        config,
        "CATEGORIAS_ALVO",
        ""
    )

    if not configuracao:
        return list(CATEGORIAS.keys())

    categorias = []

    for categoria in configuracao.split(","):

        categoria = _normalizar_texto(
            categoria
        ).strip()

        if categoria in CATEGORIAS:
            categorias.append(categoria)

        else:
            logger.warning(
                "Categoria '%s' configurada, mas não existe.",
                categoria
            )

    return categorias


# ============================================================
# IDENTIFICAÇÃO DA CATEGORIA
# ============================================================

def identificar_categoria(promocao: dict) -> str | None:
    """
    Identifica a categoria da promoção usando o título.

    Retorna:
        "tecnologia"
        "cozinha"
        "casa"
        "moveis"
        "games"
        "ferramentas"

    ou None caso nenhuma categoria seja encontrada.
    """

    titulo = _normalizar_texto(
        promocao.get("titulo", "")
    )

    if not titulo:
        return None

    categorias_alvo = obter_categorias_alvo()

    melhor_categoria = None
    maior_pontuacao = 0

    for categoria in categorias_alvo:

        pontuacao = 0

        for palavra in CATEGORIAS.get(categoria, []):

            palavra_normalizada = _normalizar_texto(
                palavra
            )

            if palavra_normalizada in titulo:

                # Palavras maiores são mais específicas.
                # Ex.: "monitor gamer" vale mais que "monitor".
                pontuacao += len(
                    palavra_normalizada.split()
                )

        if pontuacao > maior_pontuacao:

            maior_pontuacao = pontuacao
            melhor_categoria = categoria

    return melhor_categoria


# ============================================================
# FILTRO POR CATEGORIA
# ============================================================

def filtrar_por_categoria(
    promocoes: list[dict]
) -> list[dict]:
    """
    Mantém somente produtos pertencentes às categorias configuradas.
    """

    aprovadas = []

    categorias_alvo = obter_categorias_alvo()

    if not categorias_alvo:
        logger.warning(
            "Nenhuma categoria válida configurada."
        )
        return []

    for promocao in promocoes:

        categoria = identificar_categoria(
            promocao
        )

        if not categoria:
            continue

        promocao["categoria"] = categoria

        aprovadas.append(
            promocao
        )

    logger.info(
        "%s de %s ofertas pertencem às categorias alvo: %s",
        len(aprovadas),
        len(promocoes),
        ", ".join(categorias_alvo),
    )

    return aprovadas


# ============================================================
# FILTRO DE DESCONTO E PREÇO
# ============================================================

def filtrar_ofertas(
    promocoes: list[dict]
) -> list[dict]:
    """
    Aplica os filtros configurados:

    - DESCONTO_MINIMO
    - PRECO_MINIMO
    - PRECO_MAXIMO

    Também descarta ofertas sem desconto calculável.
    """

    aprovadas = []

    for promocao in promocoes:

        desconto = promocao.get(
            "desconto"
        )

        preco_atual = promocao.get(
            "preco_atual"
        )

        if desconto is None or preco_atual is None:
            continue

        if desconto < config.DESCONTO_MINIMO:
            continue

        if (
            preco_atual < config.PRECO_MINIMO
            or preco_atual > config.PRECO_MAXIMO
        ):
            continue

        aprovadas.append(
            promocao
        )

    logger.info(
        "%s de %s ofertas aprovadas "
        "(desconto >= %s%%, preço entre R$ %s e R$ %s)",
        len(aprovadas),
        len(promocoes),
        config.DESCONTO_MINIMO,
        config.PRECO_MINIMO,
        config.PRECO_MAXIMO,
    )

    return aprovadas


# ============================================================
# REMOVER DUPLICADAS
# ============================================================

def remover_duplicadas(
    promocoes: list[dict]
) -> list[dict]:
    """
    Remove ofertas repetidas dentro da mesma execução.

    Usa a URL do produto como identificador.
    """

    vistos = set()
    unicas = []

    for promocao in promocoes:

        identificador = promocao.get(
            "url_produto"
        )

        if not identificador:
            continue

        if identificador in vistos:
            continue

        vistos.add(
            identificador
        )

        unicas.append(
            promocao
        )

    return unicas


# ============================================================
# PONTUAÇÃO DAS OFERTAS
# ============================================================

def calcular_pontuacao(
    promocao: dict
) -> float:
    """
    Calcula uma pontuação para determinar a qualidade da oferta.

    A pontuação considera:

    - categoria encontrada;
    - percentual de desconto;
    - presença de preço anterior;
    - faixa de preço.

    Quanto maior a pontuação, maior a prioridade.
    """

    pontuacao = 0.0

    desconto = promocao.get(
        "desconto"
    ) or 0

    preco_atual = promocao.get(
        "preco_atual"
    ) or 0

    preco_anterior = promocao.get(
        "preco_anterior"
    )

    categoria = promocao.get(
        "categoria"
    )

    # --------------------------------------------------------
    # Categoria
    # --------------------------------------------------------

    if categoria:
        pontuacao += 10

    # --------------------------------------------------------
    # Desconto
    # --------------------------------------------------------

    # Cada 5% de desconto adiciona pontos.
    pontuacao += desconto / 5

    # Bônus para descontos realmente interessantes.
    if desconto >= 30:
        pontuacao += 5

    if desconto >= 40:
        pontuacao += 5

    if desconto >= 50:
        pontuacao += 5

    # --------------------------------------------------------
    # Preço anterior
    # --------------------------------------------------------

    if preco_anterior:
        pontuacao += 3

    # --------------------------------------------------------
    # Faixa de preço
    # --------------------------------------------------------

    # Pequeno bônus para produtos dentro de uma faixa
    # normalmente interessante para compras por impulso.

    if 50 <= preco_atual <= 500:
        pontuacao += 5

    elif 500 < preco_atual <= 1500:
        pontuacao += 3

    return round(
        pontuacao,
        2
    )


# ============================================================
# ATRIBUIR PONTUAÇÃO
# ============================================================

def pontuar_ofertas(
    promocoes: list[dict]
) -> list[dict]:
    """
    Calcula e adiciona a pontuação em cada promoção.
    """

    for promocao in promocoes:

        promocao["pontuacao"] = calcular_pontuacao(
            promocao
        )

    return promocoes


# ============================================================
# SELECIONAR MELHORES
# ============================================================

def selecionar_melhores(
    promocoes: list[dict],
    limite: int | None = None
) -> list[dict]:
    """
    Ordena as ofertas pela pontuação e devolve no máximo
    `limite` produtos.
    """

    limite = (
        limite
        if limite is not None
        else config.MAX_PROMOTIONS_PER_RUN
    )

    pontuar_ofertas(
        promocoes
    )

    ordenadas = sorted(
        promocoes,
        key=lambda p: (
            p.get("pontuacao") or 0,
            p.get("desconto") or 0,
        ),
        reverse=True
    )

    selecionadas = ordenadas[
        :limite
    ]

    logger.info(
        "%s promoções selecionadas para publicação",
        len(selecionadas)
    )

    for promocao in selecionadas:

        logger.info(
            "🏆 %s | %s | %.1f%% desconto | "
            "R$ %.2f | pontuação %.2f",
            promocao.get("categoria", "sem categoria"),
            promocao.get("titulo", "Produto"),
            promocao.get("desconto") or 0,
            promocao.get("preco_atual") or 0,
            promocao.get("pontuacao") or 0,
        )

    return selecionadas


# ============================================================
# FORMATAÇÃO DE PREÇO
# ============================================================

def _formatar_preco(
    valor: float
) -> str:

    return (
        f"R$ {valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


# ============================================================
# MONTAR MENSAGEM
# ============================================================

def montar_mensagem(
    promocao: dict
) -> str:
    """
    Monta a mensagem final para o Telegram.
    """

    titulo = promocao.get(
        "titulo",
        "Produto"
    )

    preco_atual = promocao.get(
        "preco_atual"
    )

    preco_anterior = promocao.get(
        "preco_anterior"
    )

    desconto = promocao.get(
        "desconto"
    )

    cupom = (
        promocao.get("cupom")
        or config.CUPOM_DESCONTO
    )

    link = (
        promocao.get("url_afiliado")
        or promocao.get("url_produto")
    )

    categoria = promocao.get(
        "categoria"
    )

    linhas = [
        "🔥 OFERTA DO DIA",
        "",
    ]

    if categoria:
        emojis_categoria = {
            "tecnologia": "💻",
            "cozinha": "🍳",
            "casa": "🏠",
            "moveis": "🪑",
            "games": "🎮",
            "ferramentas": "🔧",
        }

        emoji = emojis_categoria.get(
            categoria,
            "🛍️"
        )

        linhas.append(
            f"{emoji} {categoria.upper()}"
        )

        linhas.append("")

    linhas.extend([
        f"🛍️ {titulo}",
        "",
    ])

    if preco_anterior:

        linhas.append(
            f"💰 De: {_formatar_preco(preco_anterior)}"
        )

    if preco_atual is not None:

        linhas.append(
            f"🔥 Por: {_formatar_preco(preco_atual)}"
        )

    if desconto:

        linhas.append(
            f"📉 Desconto: {desconto:.0f}%"
        )

    if cupom:

        linhas.append("")

        linhas.append(
            f"🏷️ CUPOM: {cupom}"
        )

    linhas.extend([
        "",
        "🛒 COMPRAR AGORA:",
        link,
        "",
        "⚠️ Preço e disponibilidade podem mudar sem aviso.",
    ])

    return "\n".join(
        linhas
    )


# ============================================================
# PIPELINE COMPLETO
# ============================================================

def preparar_promocoes_para_publicar(
    promocoes_brutas: list[dict]
) -> list[dict]:
    """
    Pipeline completo:

    1. Remove duplicados;
    2. identifica categorias;
    3. filtra por categoria;
    4. filtra por desconto e preço;
    5. calcula pontuação;
    6. seleciona as melhores ofertas.

    A verificação do banco fica no bot.py.
    """

    logger.info(
        "Iniciando processamento de %s ofertas...",
        len(promocoes_brutas)
    )

    # --------------------------------------------------------
    # 1. Remove duplicados
    # --------------------------------------------------------

    sem_duplicadas = remover_duplicadas(
        promocoes_brutas
    )

    logger.info(
        "Após remoção de duplicados: %s ofertas.",
        len(sem_duplicadas)
    )

    # --------------------------------------------------------
    # 2. Filtra por categoria
    # --------------------------------------------------------

    por_categoria = filtrar_por_categoria(
        sem_duplicadas
    )

    # --------------------------------------------------------
    # 3. Filtra desconto e preço
    # --------------------------------------------------------

    aprovadas = filtrar_ofertas(
        por_categoria
    )

    # --------------------------------------------------------
    # 4. Seleciona melhores por pontuação
    # --------------------------------------------------------

    selecionadas = selecionar_melhores(
        aprovadas
    )

    return selecionadas