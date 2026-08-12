"""
Ponto de entrada do bot de promoções.

Uso:
    python main.py            # roda o ciclo completo (Fase 5)
    python main.py --teste    # só valida a conexão com o Telegram (Fase 1)
"""

import sys

from app.bot import enviar_mensagem_teste, executar_ciclo

if __name__ == "__main__":
    if "--teste" in sys.argv:
        enviar_mensagem_teste()
    else:
        executar_ciclo()