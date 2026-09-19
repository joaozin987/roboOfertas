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

# Configura logs detalhados para exibir o progresso no terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from app.bot import enviar_mensagem_teste, executar_ciclo, rodar_loop
from app.mercado_livre_api import MercadoLivreAPI

# Credenciais da aplicação do Mercado Livre
ML_CLIENT_ID = os.getenv("ML_CLIENT_ID", "4484676904253948")
ML_CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET", "COLE_SUA_SECRET_KEY_AQUI")
ML_REDIRECT_URI = "https://httpbin.org/get"

def autenticar_ml(tg_code: str):
    logging.info("Iniciando troca do TG-Code pelos tokens do Mercado Livre...")
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
        rodar_loop()