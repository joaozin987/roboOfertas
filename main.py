"""
Ponto de entrada do bot de promoções.

Uso:
    python main.py             # Inicia o robô em loop contínuo (roda a cada X minutos)
    python main.py --uma-vez   # Executa apenas um ciclo e encerra
    python main.py --teste     # Apenas valida a conexão com o Telegram
"""

import logging
import sys

# Configura logs detalhados para exibir o progresso no terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from app.bot import enviar_mensagem_teste, executar_ciclo, rodar_loop

if __name__ == "__main__":
    if "--teste" in sys.argv:
        enviar_mensagem_teste()
    elif "--uma-vez" in sys.argv:
        executar_ciclo()
    else:
        rodar_loop()