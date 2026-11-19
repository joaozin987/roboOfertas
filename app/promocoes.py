"""
Regras de negócio das promoções.

Responsável por:
- classificar cada oferta numa categoria coerente com o TÍTULO do produto
  (o nome do nicho de onde ela veio só é mantido quando o título não o contradiz);
- filtrar por categoria (opcional), desconto e faixa de preço;
- remover duplicados encontrados na mesma execução;
- pontuar e selecionar as melhores ofertas, com variedade de categorias;
- montar a mensagem final formatada para o Telegram.
"""

import hashlib
import logging
import re
import unicodedata
from functools import lru_cache
from typing import Dict, List, Optional, Set

from app import config

logger = logging.getLogger(__name__)

LIMITE_TITULO = 110  # legenda de foto no Telegram aceita no máximo 1024 caracteres

# ============================================================
# CATEGORIAS E PALAVRAS-CHAVE
# ============================================================

CATEGORIAS: Dict[str, List[str]] = {
    "tecnologia": [
        "celular", "smartphone", "iphone", "samsung", "xiaomi", "motorola",
        "notebook", "laptop", "computador", "pc gamer", "monitor", "teclado",
        "mouse", "headset", "fone", "fone bluetooth", "fone de ouvido", "airpods",
        "ssd", "hd externo", "memoria ram", "placa de video", "placa mae",
        "processador", "carregador", "power bank", "smartwatch",
        "relogio inteligente", "tablet", "capinha", "pelicula", "cabo usb",
        "cabo hdmi", "caixa de som", "webcam", "roteador", "pendrive", "smart tv",
    ],
    "moda": [
        "camisa", "camiseta", "blusa", "calca", "jaqueta", "casaco", "moletom",
        "vestido", "saia", "short", "bermuda", "cueca", "calcinha", "sutia",
        "meia", "tenis", "sapato", "sandalia", "chinelo", "bota", "mochila",
        "bolsa", "mala", "cinto", "bone", "relogio", "regata", "legging",
        "pijama", "sueter", "oculos", "carteira",
    ],
    "cozinha": [
        "air fryer", "airfryer", "fritadeira", "liquidificador", "mixer",
        "batedeira", "cafeteira", "panela", "frigideira", "panela de pressao",
        "jogo de panelas", "forno", "microondas", "sanduicheira", "churrasqueira",
        "processador de alimentos", "potes", "faqueiro", "garrafa termica",
        "chaleira", "caneca", "copo", "xicara", "jarra", "prato", "talher",
        "marmita", "tabua de corte", "espremedor", "ralador",
    ],
    "casa": [
        "organizador", "caixa organizadora", "tapete", "cortina", "luminaria",
        "abajur", "lampada", "ventilador", "aspirador", "aspirador robo", "mop",
        "limpeza", "ferro de passar", "espelho", "travesseiro", "edredom",
        "cobertor", "toalha", "lencol", "jogo de cama", "fronha",
        "cesto", "varal", "vassoura", "rodo", "balde", "capacho", "cabide",
        "vaso", "decoracao",
    ],
    "moveis": [
        "mesa", "escrivaninha", "cadeira", "cadeira gamer", "cadeira de escritorio",
        "sofa", "poltrona", "cama", "colchao", "guarda roupa", "armario", "comoda",
        "gaveteiro", "estante", "rack", "painel para tv",
    ],
    "games": [
        "playstation", "ps5", "ps4", "xbox", "xbox series", "nintendo",
        "nintendo switch", "console", "controle ps5", "controle xbox", "joystick",
        "game",
    ],
    "esportes": [
        "suplemento", "whey", "creatina", "halter", "anilhas", "colchonete",
        "elastico", "garrafa", "bicicleta", "corda de pular", "luva de treino",
    ],
    "ferramentas": [
        "furadeira", "parafusadeira", "esmerilhadeira", "serra", "lixadeira",
        "compressor", "chave de fenda", "kit ferramentas", "alicate", "martelo",
        "trena",
    ],
    "beleza": [
        "perfume", "colonia", "shampoo", "condicionador", "hidratante",
        "creme facial", "creme hidratante", "batom", "maquiagem", "rimel",
        "esmalte", "serum", "skincare", "protetor solar", "sabonete",
        "desodorante", "secador de cabelo", "chapinha", "prancha de cabelo",
        "barbeador", "aparador de barba", "depilador", "mascara capilar",
        "body splash", "locao", "creme corporal", "mascara facial", "gloss",
        "base liquida", "corretivo", "pincel de maquiagem",
    ],
    "pet": [
        "racao", "coleira", "caminha pet", "arranhador", "brinquedo para cachorro",
        "brinquedo para gato", "comedouro", "bebedouro pet",
    ],
    "brinquedos": [
        "brinquedo", "boneca", "lego", "carrinho de controle", "quebra cabeca",
        "pelucia",
    ],
    "bebe": [
        "fralda", "mamadeira", "carrinho de bebe", "chupeta", "bebe conforto",
    ],
}

NOMES_EXIBICAO = {
    "tecnologia": "Tecnologia", "moda": "Moda", "cozinha": "Cozinha",
    "casa": "Casa", "moveis": "Móveis", "games": "Games",
    "esportes": "Esportes", "ferramentas": "Ferramentas", "beleza": "Beleza",
    "pet": "Pet", "brinquedos": "Brinquedos", "bebe": "Bebê",
}

# Quais categorias internas "pertencem" a cada nicho do scraper do Mercado Livre
# (chaves já normalizadas: sem acento e em minúsculo).
NICHO_CATEGORIAS: Dict[str, Set[str]] = {
    "smartphones & celulares": {"tecnologia"},
    "moda & calcados": {"moda"},
    "corrida & esportes": {"esportes", "moda"},
    "informatica & games": {"tecnologia", "games"},
    "casa & eletrodomesticos": {"casa", "cozinha", "moveis", "ferramentas"},
    "beleza & cuidados": {"beleza"},
}

# Rótulos "genéricos": a categoria é decidida só pelo título.
NICHOS_GENERICOS = {
    "", "sem categoria", "ofertas", "destaques",
    "super queimas & liquidacao", "ofertas shopee",
}

_ID_ML_RE = re.compile(r"MLBU?-?(\d{7,})")


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


def _nome_exibicao(chave: str) -> str:
    return NOMES_EXIBICAO.get(chave, chave.capitalize())


# ============================================================
# IDENTIFICAÇÃO DA CATEGORIA
# ============================================================

@lru_cache(maxsize=1)
def _padroes() -> Dict[str, list]:
    """Compila uma vez: palavra inteira (não casa 'game' em 'gamer'), aceitando plural simples."""
    resultado = {}
    for categoria, palavras in CATEGORIAS.items():
        compilados = []
        for palavra in palavras:
            norm = _normalizar_texto(palavra)
            peso = len(norm.split())
            regex = re.compile(rf"(?<!\w){re.escape(norm)}(?:s|es)?(?!\w)")
            compilados.append((peso, regex))
        resultado[categoria] = compilados
    return resultado


def _pontuar_categorias(titulo: str) -> Dict[str, int]:
    texto = _normalizar_texto(titulo)
    if not texto:
        return {}
    pontos = {}
    for categoria, padroes in _padroes().items():
        total = sum(peso for peso, regex in padroes if regex.search(texto))
        if total > 0:
            pontos[categoria] = total
    return pontos


def identificar_categoria(promocao: dict) -> str:
    """
    O TÍTULO manda. O rótulo do nicho de origem só é mantido quando o título
    não o contradiz; caso contrário a oferta é reclassificada (ex.: um tênis
    que apareceu na página de Beleza sai como "Moda").
    """
    rotulo = promocao.get("categoria") or ""
    rotulo_norm = _normalizar_texto(rotulo)
    pontos = _pontuar_categorias(promocao.get("titulo", ""))

    # Nicho conhecido do Mercado Livre
    if rotulo_norm in NICHO_CATEGORIAS:
        if not pontos:
            return rotulo  # título sem pistas: mantém o nicho
        melhor = max(pontos.values())
        # Em caso de empate com uma categoria do nicho, o nicho vence.
        if any(pontos.get(c, 0) == melhor for c in NICHO_CATEGORIAS[rotulo_norm]):
            return rotulo
        nova = _nome_exibicao(max(pontos, key=pontos.get))
        logger.info(
            "Recategorizado '%s': %s -> %s", promocao.get("titulo"), rotulo, nova
        )
        return nova

    # Rótulo genérico: usa só o título
    if rotulo_norm in NICHOS_GENERICOS:
        if pontos:
            return _nome_exibicao(max(pontos, key=pontos.get))
        return "Destaques"

    # Já é uma categoria final (ou origem desconhecida): preserva
    return rotulo or "Destaques"


def _categorias_internas(rotulo: str) -> Set[str]:
    norm = _normalizar_texto(rotulo)
    if norm in NICHO_CATEGORIAS:
        return set(NICHO_CATEGORIAS[norm])
    if norm in CATEGORIAS:
        return {norm}
    return set()


# ============================================================
# FILTRO POR CATEGORIA
# ============================================================

def obter_categorias_alvo() -> List[str]:
    """Lê CATEGORIAS_ALVO do config. Lista vazia = sem restrição."""
    bruto = getattr(config, "CATEGORIAS_ALVO", "") or ""
    alvos = [_normalizar_texto(c) for c in bruto.split(",")]
    return [a for a in alvos if a]


def filtrar_por_categoria(promocoes: List[dict]) -> List[dict]:
    """Atribui a categoria correta e só descarta se CATEGORIAS_ALVO estiver preenchido."""
    alvos = set(obter_categorias_alvo())
    aprovadas = []

    for promocao in promocoes:
        promocao["categoria"] = identificar_categoria(promocao)
        if alvos and not (_categorias_internas(promocao["categoria"]) & alvos):
            continue
        aprovadas.append(promocao)

    logger.info(
        "%s de %s ofertas pertencem às categorias válidas.", len(aprovadas), len(promocoes)
    )
    return aprovadas


# ============================================================
# FILTRO DE DESCONTO E PREÇO
# ============================================================

def filtrar_ofertas(
    promocoes: List[dict], desconto_min: Optional[float] = None, *, preco_min: Optional[float] = None
) -> List[dict]:
    """Aplica DESCONTO_MINIMO, teto de desconto suspeito e faixa de preço."""
    aprovadas = []

    if desconto_min is None:
        desconto_min = getattr(config, "DESCONTO_MINIMO", 15.0)
    desconto_max = getattr(config, "DESCONTO_MAXIMO_SUSPEITO", 90.0)
    if preco_min is None:
        preco_min = getattr(config, "PRECO_MINIMO", 20.0)
    preco_max = getattr(config, "PRECO_MAXIMO", 50000.0)
    descartes = dict(dados_ausentes=0, desconto_baixo=0, desconto_alto=0, preco_baixo=0, preco_alto=0)

    for promocao in promocoes:
        desconto = promocao.get("desconto")
        preco_atual = promocao.get("preco_atual")

        if desconto is None or preco_atual is None:
            descartes["dados_ausentes"] += 1
            continue
        if desconto < desconto_min:
            descartes["desconto_baixo"] += 1
            continue
        if desconto_max and desconto > desconto_max:
            descartes["desconto_alto"] += 1
            logger.info("Desconto suspeito (%.0f%%) ignorado: %s", desconto, promocao.get("titulo"))
            continue
        if preco_atual < preco_min:
            descartes["preco_baixo"] += 1
            continue
        if preco_atual > preco_max:
            descartes["preco_alto"] += 1
            continue

        aprovadas.append(promocao)

    logger.info(
        "%s de %s ofertas aprovadas (desconto entre %s%% e %s%%, preço entre R$ %s e R$ %s)",
        len(aprovadas), len(promocoes), desconto_min, desconto_max, preco_min, preco_max,
    )
    if len(aprovadas) < len(promocoes):
        logger.info("Descartes por regra (%s): %s", promocoes[0].get("origem", "Mercado Livre"), descartes)
    return aprovadas


# ============================================================
# REMOVER DUPLICADAS
# ============================================================

def _chave_produto(promocao: dict) -> str:
    """Chave estável do produto: ID do anúncio, não a URL com parâmetros de rastreio."""
    pid = promocao.get("produto_id")
    if pid:
        return str(pid)
    url = (promocao.get("url_produto") or "").split("#")[0].split("?")[0]
    m = _ID_ML_RE.search(url)
    if m:
        return "MLB" + m.group(1)
    return url


def remover_duplicadas(promocoes: List[dict]) -> List[dict]:
    vistos = set()
    unicas = []
    for promocao in promocoes:
        chave = _chave_produto(promocao)
        if not chave or chave in vistos:
            continue
        vistos.add(chave)
        unicas.append(promocao)
    return unicas


# ============================================================
# PONTUAÇÃO E SELEÇÃO
# ============================================================

def calcular_pontuacao(promocao: dict) -> float:
    pontuacao = 0.0
    desconto = promocao.get("desconto") or 0
    preco_atual = promocao.get("preco_atual") or 0
    preco_anterior = promocao.get("preco_anterior")

    pontuacao += desconto / 4
    if desconto >= 30:
        pontuacao += 5
    if desconto >= 50:
        pontuacao += 8
    if preco_anterior:
        pontuacao += 4
    if 40 <= preco_atual <= 300:
        pontuacao += 6
    elif 300 < preco_atual <= 1500:
        pontuacao += 4

    return round(pontuacao, 2)


def pontuar_ofertas(promocoes: List[dict]) -> List[dict]:
    for promocao in promocoes:
        promocao["pontuacao"] = calcular_pontuacao(promocao)
    return promocoes


def selecionar_melhores(promocoes: List[dict], limite: Optional[int] = None) -> List[dict]:
    """Pega as melhores por pontuação, priorizando uma oferta por categoria (variedade)."""
    if limite is None:
        limite = getattr(config, "MAX_PROMOTIONS_PER_RUN", 3)
    pontuar_ofertas(promocoes)

    ordenadas = sorted(
        promocoes,
        key=lambda p: (p.get("pontuacao") or 0, p.get("desconto") or 0),
        reverse=True,
    )

    selecionadas: List[dict] = []
    categorias_usadas = set()
    for promocao in ordenadas:
        if len(selecionadas) >= limite:
            break
        categoria = promocao.get("categoria")
        if categoria in categorias_usadas:
            continue
        selecionadas.append(promocao)
        categorias_usadas.add(categoria)

    if len(selecionadas) < limite:  # completa com as próximas melhores, mesmo repetindo categoria
        ja = {id(p) for p in selecionadas}
        for promocao in ordenadas:
            if len(selecionadas) >= limite:
                break
            if id(promocao) not in ja:
                selecionadas.append(promocao)

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
# MENSAGEM
# ============================================================

def _formatar_preco(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


_EMOJIS = {
    "smartphones & celulares": "📱",
    "celulares": "📱",
    "tecnologia": "💻",
    "informatica": "💻",
    "moda & calcados": "👕",
    "calcados": "👟",
    "moda": "👕",
    "cozinha": "🍳",
    "casa": "🏠",
    "moveis": "🪑",
    "games": "🎮",
    "esportes": "💪",
    "beleza": "✨",
    "ferramentas": "🔧",
    "pet": "🐶",
    "brinquedos": "🧸",
    "bebe": "🍼",
}


def _emoji_da_categoria(categoria: str) -> str:
    slug = _normalizar_texto(categoria)
    for chave, icone in _EMOJIS.items():
        if chave in slug:
            return icone
    return "⭐"


# Humor zoeiro do Jpz: piadas relacionadas ao titulo, sem inventar fatos.
# Ganchos especificos vem antes dos genericos; nao depende de IA externa.
_GANCHOS_PRODUTO = [
    (("air fryer", "airfryer", "fritadeira"), [
        "🍟 A panela de óleo já tá procurando outro emprego! 😂",
        "🍟 A batata tá feliz. O óleo nem tanto!",
        "🍟 Até a cozinha pediu pra aposentar a fritura!",
    ]),
    (("aspirador robo", "robo aspirador"), [
        "🤖 Finalmente alguém nessa casa disposto a limpar o chão! 😂",
        "🤖 A vassoura viu isso e pediu férias!",
        "🤖 Esse robô trabalha enquanto você finge que não viu a sujeira!",
    ]),
    (("headset", "fone gamer"), [
        "🎧 Seu squad pode até não te escutar, mas olha esse achado! 😂",
        "🎧 O microfone não resolve o rage, mas ajuda no setup!",
        "🎧 Até o vizinho ficou curioso com esse headset!",
    ]),
    (("mouse",), [
        "🖱️ Se a mira tá ruim, pelo menos o mouse não precisa sofrer! 😂",
        "🖱️ O clique é seu. A desculpa pro lag também!",
        "🖱️ Até o cursor parou pra olhar essa oferta!",
    ]),
    (("teclado",), [
        "⌨️ O teclado antigo já tá digitando o pedido de demissão!",
        "⌨️ CTRL + ALT + QUERO ESSE ACHADO! 😂",
        "⌨️ Seu teclado cansou de levar a culpa pelas derrotas!",
    ]),
    (("tenis", "sneaker"), [
        "👟 O tênis é novo. A desculpa pra não treinar continua! 😂",
        "👟 Seu tênis antigo já tá pedindo aposentadoria!",
        "👟 Comprar tênis é fácil. Difícil é começar a correr!",
    ]),
    (("cafeteira", "maquina de cafe"), [
        "☕ Pra quem só começa a funcionar depois do primeiro café!",
        "☕ Até o despertador pediu uma xícara!",
        "☕ Seu eu de segunda-feira aprovou a ideia!",
    ]),
    (("controle", "joystick"), [
        "🎮 O controle não joga sozinho, infelizmente! 😂",
        "🎮 Se perder a partida, não põe a culpa no controle!",
        "🎮 Seu próximo rage já tem companhia!",
    ]),
    (("panela", "frigideira"), [
        "🍳 Até o miojo ficou se achando gourmet!",
        "🍳 A receita é simples. Lavar a louça continua difícil!",
        "🍳 A cozinha tá pedindo reforços!",
    ]),
    (("perfume", "colonia"), [
        "✨ Chegar chegando, mas sem assustar o bolso!",
        "✨ O crush pode não notar, mas o Jpz notou essa oferta!",
        "✨ Perfume novo, mesma dificuldade pra escolher roupa! 😂",
    ]),
    (("cadeira", "poltrona"), [
        "🪑 A cadeira antiga ouviu falar em upgrade e ficou nervosa!",
        "🪑 Sua cadeira já tá fazendo barulho de protesto?",
        "🪑 Até a cadeira pediu pra sentar e conversar!",
    ]),
    (("smartphone", "celular", "iphone"), [
        "📱 Seu celular antigo já tá fingindo que não ouviu!",
        "📱 A bateria do seu celular caiu só de ver esse achado! 😂",
        "📱 O grupo da família vai querer saber desse achado!",
    ]),
    (("notebook", "laptop"), [
        "💻 Seu notebook antigo abriu 37 abas só pra reclamar!",
        "💻 O computador travou, mas o Jpz não!",
        "💻 Até a ventoinha parou pra prestar atenção!",
    ]),
    (("smart tv", "televisao", "tv "), [
        "📺 A novela é a mesma, mas a tela pode mudar!",
        "📺 Até o controle remoto ficou animado!",
        "📺 O sofá já tá preparando a pipoca!",
    ]),
    (("mochila",), [
        "🎒 Sua mochila antiga já pediu transferência!",
        "🎒 Cabe muita coisa. A preguiça de segunda não!",
        "🎒 Até o zíper ficou curioso!",
    ]),
    (("relogio", "smartwatch"), [
        "⌚ Tá na hora de olhar esse achado. Literalmente! 😂",
        "⌚ O tempo voa, mas essa oferta chamou atenção!",
        "⌚ Até o despertador ficou com ciúme!",
    ]),
    (("ventilador",), [
        "🌬️ O calor chegou sem convite. O Jpz trouxe uma ideia!",
        "🌬️ Até o calor ficou sem graça!",
        "🌬️ Seu verão já pediu reforço!",
    ]),
    (("liquidificador",), [
        "🥤 Até a vitamina ficou animada com esse achado!",
        "🥤 O liquidificador antigo tá fazendo um barulho de protesto!",
        "🥤 Mistura tudo, menos o preço com a desculpa! 😂",
    ]),
]
_GANCHOS_CATEGORIA = {
    "tecnologia": ["💻 O setup pediu upgrade e mandou o boleto pra você! 😂", "💻 Seu gadget antigo já tá desconfiado!"],
    "games": ["🎮 Habilidade não vem na caixa, mas olha esse achado!", "🎮 Até o lobby parou pra conferir!"],
    "moda": ["👕 O guarda-roupa pediu socorro de novo!", "👟 O estilo chamou e a carteira fingiu que não ouviu!"],
    "casa": ["🏠 A casa quer novidade. O boleto que lute! 😂", "🏠 Até a lista de compras ficou curiosa!"],
    "cozinha": ["🍳 Até o miojo pediu um upgrade!", "🍳 A cozinha chamou reforços!"],
    "beleza": ["✨ O nécessaire pediu mais espaço. De novo!", "✨ Até o espelho ficou curioso!"],
    "esportes": ["💪 O treino não se faz sozinho, infelizmente!", "💪 A academia chamou. O Jpz atendeu!"],
}
_GANCHOS_GERAIS = ["👀 O Jpz achou e a carteira já ficou desconfiada! 😂", "🔎 Mais um achado pra testar o autocontrole!"]


def _gancho_jpz(promocao: dict) -> str:
    titulo = _normalizar_texto(promocao.get("titulo") or "")
    categoria = _normalizar_texto(promocao.get("categoria") or "")
    opcoes = None
    for palavras, frases in _GANCHOS_PRODUTO:
        if any(re.search(r"(?<!\\w)" + re.escape(palavra) + r"(?!\\w)", titulo) for palavra in palavras):
            opcoes = frases
            break
    if opcoes is None:
        chave = next((nome for nome in _GANCHOS_CATEGORIA if nome in categoria), None)
        opcoes = _GANCHOS_CATEGORIA[chave] if chave else _GANCHOS_GERAIS
    identidade = str(promocao.get("produto_id") or promocao.get("url_produto") or promocao.get("titulo") or "")
    indice = int(hashlib.sha256(identidade.encode("utf-8")).hexdigest()[:8], 16) % len(opcoes)
    return opcoes[indice]


def montar_mensagem(promocao: dict) -> str:
    """Mensagem limpa e espaçada, com informações verificáveis da oferta."""
    titulo = (promocao.get("titulo") or "Produto").strip()
    if len(titulo) > LIMITE_TITULO:
        titulo = titulo[: LIMITE_TITULO - 3].rstrip() + "..."

    preco_atual = promocao.get("preco_atual")
    preco_anterior = promocao.get("preco_anterior")
    desconto = promocao.get("desconto")
    cupom = promocao.get("cupom")
    link = promocao.get("url_afiliado") or promocao.get("url_produto")

    blocos = [_gancho_jpz(promocao), f"🛍️ {titulo}"]

    consultado = promocao.get("preco_consultado_em")
    if consultado and preco_atual is not None:
        blocos.append(
            f"Preço visto em {consultado:%d/%m}: {_formatar_preco(preco_atual)}. "
            "Confira o valor e a disponibilidade no link."
        )
    elif preco_anterior is not None and preco_atual is not None and preco_anterior > preco_atual:
        blocos.append(f"De {_formatar_preco(preco_anterior)} → por {_formatar_preco(preco_atual)}")
    elif preco_atual is not None:
        blocos.append(f"Por {_formatar_preco(preco_atual)}")

    if not consultado and desconto is not None and desconto > 0:
        blocos.append(f"📉 {desconto:.0f}% de desconto")
    if cupom and not consultado:
        blocos.append(f"🏷️ Cupom: {cupom}")
    if link:
        blocos.append(f"🔗 Confira a oferta:\n{link}")

    blocos.append("Jpz Ofertas • Link de afiliado")
    return "\n\n".join(blocos)


# ============================================================
# PIPELINE COMPLETO
# ============================================================

def preparar_promocoes_para_publicar(
    promocoes_brutas: List[dict],
    limite: Optional[int] = None,
    desconto_min: Optional[float] = None,
    *,
    preco_min: Optional[float] = None,
) -> List[dict]:
    """duplicadas -> categoria -> desconto/preço -> melhores. Serve para ML e Shopee."""
    logger.info("Iniciando processamento de %s ofertas...", len(promocoes_brutas))

    sem_duplicadas = remover_duplicadas(promocoes_brutas)
    logger.info("Após remoção de duplicados: %s ofertas.", len(sem_duplicadas))

    por_categoria = filtrar_por_categoria(sem_duplicadas)
    aprovadas = filtrar_ofertas(por_categoria, desconto_min=desconto_min, preco_min=preco_min)
    return selecionar_melhores(aprovadas, limite=limite)
