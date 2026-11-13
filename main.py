"""
Ponto de entrada do bot de promoções.

Uso:
    python main.py             # Inicia o robô em loop contínuo (roda a cada X minutos)
    python main.py --uma-vez   # Executa apenas um ciclo e encerra
    python main.py --teste     # Apenas valida a conexão com o Telegram
    python main.py --auth-ml TG-XXXXX  # Autentica e gera os tokens do Mercado Livre pela 1ª vez
"""

import logging
import sys
import os

# Garante que o .env seja lido antes de qualquer os.getenv (se python-dotenv estiver instalado)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Configura logs detalhados para exibir o progresso no terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from app.bot import ML_JSON_MAX_IDADE_HORAS, enviar_mensagem_teste, executar_ciclo, rodar_loop
from app.mercado_livre_api import MercadoLivreAPI
from app.ml_upload import iniciar_receptor

# Credenciais da aplicação do Mercado Livre (vêm do .env, nada fixo no código)
ML_CLIENT_ID = os.getenv("ML_CLIENT_ID", "").strip()
ML_CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET", "").strip()
ML_REDIRECT_URI = os.getenv("ML_REDIRECT_URI", "https://www.google.com").strip()


def autenticar_ml(tg_code: str):
    if not ML_CLIENT_ID or not ML_CLIENT_SECRET:
        logging.error("ML_CLIENT_ID / ML_CLIENT_SECRET não encontrados no .env.")
        return

    logging.info("Iniciando troca do TG-Code pelos tokens do Mercado Livre...")
    logging.info("client_id: %s | redirect_uri: %r", ML_CLIENT_ID, ML_REDIRECT_URI)

    ml = MercadoLivreAPI(ML_CLIENT_ID, ML_CLIENT_SECRET, ML_REDIRECT_URI)
    try:
        ml.inicializar_com_code(tg_code)
        logging.info("Autenticação concluída! Arquivo data/ml_tokens.json gerado.")
    except Exception as e:
        logging.error(f"Falha ao autenticar no Mercado Livre: {e}")


if __name__ == "__main__":
    if "--auth-ml" in sys.argv:
        try:
            code_index = sys.argv.index("--auth-ml") + 1
            tg_code = sys.argv[code_index]
            autenticar_ml(tg_code)
        except IndexError:
            logging.error("Informe o código TG após o comando. Ex: python main.py --auth-ml TG-xxxxxx")
    elif "--teste" in sys.argv:
        enviar_mensagem_teste()
    elif "--uma-vez" in sys.argv:
        executar_ciclo()
    else:
        iniciar_receptor(ML_JSON_MAX_IDADE_HORAS)
        rodar_loop()
