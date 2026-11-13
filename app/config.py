"""
Configuração central do bot.

Carrega as variáveis de ambiente definidas no arquivo `.env` (baseado em
`.env.example`) e expõe valores já convertidos para os tipos corretos.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _get_str(nome: str, padrao: str = "") -> str:
    return (os.getenv(nome) or padrao).strip()


def _get_bool(nome: str, padrao: bool = False) -> bool:
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in ("1", "true", "yes", "sim")


def _get_int(nome: str, padrao: int) -> int:
    valor = os.getenv(nome)
    if valor is None or valor.strip() == "":
        return padrao
    try:
        return int(valor)
    except ValueError:
        return padrao


def _get_float(nome: str, padrao: float) -> float:
    valor = os.getenv(nome)
    if valor is None or valor.strip() == "":
        return padrao
    try:
        return float(valor.replace(",", "."))
    except ValueError:
        return padrao


# ---------------------------------------------------------------- Telegram
TELEGRAM_BOT_TOKEN = _get_str("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = _get_str("TELEGRAM_CHANNEL_ID")
TELEGRAM_SEND_DELAY_SECONDS = _get_int("TELEGRAM_SEND_DELAY_SECONDS", 8)

# ---------------------------------------------------------------- WhatsApp
# Evolution API. Deixe WHATSAPP_API_URL ou WHATSAPP_GROUP_JID vazios para desativar o canal.
WHATSAPP_API_URL = _get_str("WHATSAPP_API_URL")
WHATSAPP_API_KEY = _get_str("WHATSAPP_API_KEY")
WHATSAPP_INSTANCE = _get_str("WHATSAPP_INSTANCE", "robo_ofertas")
WHATSAPP_GROUP_JID = _get_str("WHATSAPP_GROUP_JID")

# ---------------------------------------------------------- Mercado Livre
MERCADO_LIVRE_CLIENT_ID = _get_str("MERCADO_LIVRE_CLIENT_ID")
MERCADO_LIVRE_CLIENT_SECRET = _get_str("MERCADO_LIVRE_CLIENT_SECRET")
MERCADO_LIVRE_OFERTAS_URL = _get_str(
    "MERCADO_LIVRE_OFERTAS_URL", "https://www.mercadolivre.com.br/ofertas"
)

# Afiliado ML (sessão do navegador: o CSRF e o cookie EXPIRAM de tempos em tempos)
MELI_AFFILIATE_TAG = _get_str("MELI_AFFILIATE_TAG")
MELI_CSRF_TOKEN = _get_str("MELI_CSRF_TOKEN")
MELI_COOKIE_HEADER = _get_str("MELI_COOKIE_HEADER")

# ------------------------------------------------------------------ Shopee
# Sem valores padrão no código: IDs de afiliado ficam só no .env.
SHOPEE_AFFILIATE_ID = _get_str("SHOPEE_AFFILIATE_ID")
SHOPEE_USER_ID = _get_str("SHOPEE_USER_ID")
SHOPEE_OFERTAS_URL = _get_str("SHOPEE_OFERTAS_URL", "https://shopee.com.br/ofertas")
SHOPEE_MIN_DESCONTO = _get_float("SHOPEE_MIN_DESCONTO", 70.0)
SHOPEE_PRECO_MINIMO = _get_float("SHOPEE_PRECO_MINIMO", _get_float("PRECO_MINIMO", 10.0))
SHOPEE_PRECO_MAXIMO = _get_float("SHOPEE_PRECO_MAXIMO", 900.0)
SHOPEE_MAX_ENVIOS = _get_int("SHOPEE_MAX_ENVIOS", 5)
SHOPEE_JSON_PATH = _get_str("SHOPEE_JSON_PATH", "data/shopee_oferta.json")
# Se o arquivo do painel estiver mais velho que isso (horas), a Shopee é pulada. 0 = nunca pula.
SHOPEE_MAX_IDADE_HORAS = _get_int("SHOPEE_MAX_IDADE_HORAS", 72)
# Cupom válido SÓ para Shopee (não reaproveita o do Mercado Livre)
SHOPEE_CUPOM = _get_str("SHOPEE_CUPOM") or None

# ----------------------------------------------------- Afiliado / cupom ML
AFILIADO_ID = _get_str("AFILIADO_ID")
# Cupom aplicado às ofertas do MERCADO LIVRE. Deixe vazio se não valer para todos os produtos.
CUPOM_DESCONTO = _get_str("CUPOM_DESCONTO") or None

# ------------------------------------------------------------ Scraper geral
SCRAPER_USER_AGENT = _get_str(
    "SCRAPER_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
)
SCRAPER_REQUEST_DELAY_SECONDS = _get_int("SCRAPER_REQUEST_DELAY_SECONDS", 3)
SCRAPER_MAX_PAGINAS = _get_int("SCRAPER_MAX_PAGINAS", 2)
# Salva o HTML bruto de cada nicho em disco (só para diagnosticar mudanças no site)
DEBUG_SALVAR_HTML = _get_bool("DEBUG_SALVAR_HTML", False)

# --------------------------------------------- Automação e cotas por plataforma
MAX_PROMOTIONS_PER_RUN = _get_int("MAX_PROMOTIONS_PER_RUN", 3)
ML_COUNT_PER_RUN = _get_int("ML_COUNT_PER_RUN", 1)
SHOPEE_COUNT_PER_RUN = _get_int("SHOPEE_COUNT_PER_RUN", 2)
CHECK_INTERVAL_MINUTES = _get_int("CHECK_INTERVAL_MINUTES", 4)

# Modo noturno: não publica entre INICIO (inclusive) e FIM (exclusive), no fuso TIMEZONE.
# Para desligar, deixe os dois iguais (ex.: 0 e 0).
HORARIO_SILENCIO_INICIO = _get_int("HORARIO_SILENCIO_INICIO", 23)
HORARIO_SILENCIO_FIM = _get_int("HORARIO_SILENCIO_FIM", 7)
TIMEZONE = _get_str("TIMEZONE", "America/Sao_Paulo")

# ---------------------------------------------------------- Filtro de ofertas
DESCONTO_MINIMO = _get_float("DESCONTO_MINIMO", 25.0)
# Descontos acima disso costumam ser preço "de" inflado (ou erro de leitura): são descartados.
DESCONTO_MAXIMO_SUSPEITO = _get_float("DESCONTO_MAXIMO_SUSPEITO", 90.0)
PRECO_MINIMO = _get_float("PRECO_MINIMO", 10.0)
PRECO_MAXIMO = _get_float("PRECO_MAXIMO", 5000.0)
# Teto de preço aplicado já na leitura das páginas do Mercado Livre
ML_PRECO_MAXIMO = _get_float("ML_PRECO_MAXIMO", 900.0)
# Mínimo de desconto só para ML (por padrão, igual ao DESCONTO_MINIMO)
MELI_MIN_DESCONTO = _get_float("MELI_MIN_DESCONTO", DESCONTO_MINIMO)
# Opcional: restringe a categorias internas, separadas por vírgula
# (tecnologia, moda, cozinha, casa, moveis, games, esportes, ferramentas, beleza, pet, brinquedos, bebe)
CATEGORIAS_ALVO = _get_str("CATEGORIAS_ALVO")

# ------------------------------------------------------------ Banco de dados
DATABASE_PATH = _get_str("DATABASE_PATH", "data/promocoes.db")

# --------------------------------------------------------------- Modo de teste
TEST_MODE = _get_bool("TEST_MODE", False)


def validar_configuracao_telegram() -> None:
    """Garante que as credenciais mínimas do Telegram foram configuradas."""
    faltando = []
    if not TELEGRAM_BOT_TOKEN:
        faltando.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHANNEL_ID:
        faltando.append("TELEGRAM_CHANNEL_ID")

    if faltando:
        raise RuntimeError(
            "Variáveis de ambiente obrigatórias não configuradas: "
            + ", ".join(faltando)
            + ". Copie .env.example para .env e preencha os valores."
        )
