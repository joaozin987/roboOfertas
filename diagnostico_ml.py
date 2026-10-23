"""
Diagnóstico da API do Mercado Livre: mostra quais endpoints respondem
para o seu token. Não imprime o token.

Uso (na raiz do projeto, com o .venv ativo):
    python diagnostico_ml.py
"""

import json
import time
from pathlib import Path

import requests

BASE = "https://api.mercadolibre.com"
TOKEN_FILE = Path("data") / "ml_tokens.json"


def carregar_token():
    if not TOKEN_FILE.exists():
        print("Sem data/ml_tokens.json. Rode antes: python main.py --auth-ml TG-...")
        return None
    dados = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    if time.time() >= dados.get("expires_at", 0):
        print("AVISO: o access_token no arquivo está vencido; os testes autenticados podem dar 401.")
    return dados.get("access_token")


def testar(rotulo, caminho, params=None, token=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(BASE + caminho, params=params, headers=headers, timeout=20)
        corpo = r.text.replace("\n", " ")[:160]
        print(f"[{r.status_code}] {rotulo}\n      {corpo}\n")
    except requests.RequestException as erro:
        print(f"[ERRO] {rotulo}\n      {erro}\n")


def main():
    token = carregar_token()
    print("=" * 60)
    testar("1) /users/me (com token)  -> o token é válido?", "/users/me", token=token)
    testar("2) /categories/MLB1051 (sem token) -> API pública abre?", "/categories/MLB1051")
    testar("3) /sites/MLB/search COM token", "/sites/MLB/search", {"q": "celular", "limit": 3}, token)
    testar("4) /sites/MLB/search SEM token", "/sites/MLB/search", {"q": "celular", "limit": 3})
    testar("5) /highlights categoria COM token", "/highlights/MLB/category/MLB1051", token=token)
    testar("6) /products/search COM token", "/products/search",
           {"status": "active", "site_id": "MLB", "q": "celular", "limit": 3}, token)
    print("=" * 60)
    print("Cole aqui só os números entre colchetes e o início de cada resposta.")


if __name__ == "__main__":
    main()