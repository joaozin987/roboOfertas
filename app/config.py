"""
Configuração central do bot.

Carrega as variáveis de ambiente definidas no arquivo `.env` (baseado em
`.env.example`) e expõe valores já convertidos para os tipos corretos.
"""

import os

from dotenv import load_dotenv

load_dotenv()


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


# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")
TELEGRAM_SEND_DELAY_SECONDS = _get_int("TELEGRAM_SEND_DELAY_SECONDS", 8)

# Mercado Livre (usado a partir da Fase 3)
MERCADO_LIVRE_CLIENT_ID = os.getenv("MERCADO_LIVRE_CLIENT_ID", "")
MERCADO_LIVRE_CLIENT_SECRET = os.getenv("MERCADO_LIVRE_CLIENT_SECRET", "")

# Afiliado / cupom padrão
AFILIADO_ID = os.getenv("AFILIADO_ID", "")
CUPOM_DESCONTO = os.getenv("CUPOM_DESCONTO", "")

# Scraper do Mercado Livre (Fase 3)
MERCADO_LIVRE_OFERTAS_URL = os.getenv(
    "MERCADO_LIVRE_OFERTAS_URL", "https://www.mercadolivre.com.br/ofertas"
)
SCRAPER_USER_AGENT = os.getenv(
    "SCRAPER_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
)
# Intervalo mínimo (em segundos) entre requisições ao Mercado Livre,
# para não sobrecarregar o site nem levar bloqueio de IP.
SCRAPER_REQUEST_DELAY_SECONDS = _get_int("SCRAPER_REQUEST_DELAY_SECONDS", 3)
SCRAPER_MAX_PAGINAS = _get_int("SCRAPER_MAX_PAGINAS", 2)

# Automação
CHECK_INTERVAL_MINUTES = _get_int("CHECK_INTERVAL_MINUTES", 30)
MAX_PROMOTIONS_PER_RUN = _get_int("MAX_PROMOTIONS_PER_RUN", 3)

# Filtro de ofertas (Fase 4)
DESCONTO_MINIMO = _get_float("DESCONTO_MINIMO", 25.0)
PRECO_MINIMO = _get_float("PRECO_MINIMO", 10.0)
PRECO_MAXIMO = _get_float("PRECO_MAXIMO", 5000.0)

# Banco de dados (Fase 2)
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/promocoes.db")

# Modo de teste: quando True, o bot nunca publica de fato no canal.
TEST_MODE = _get_bool("TEST_MODE", True)


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