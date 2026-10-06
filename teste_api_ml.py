"""
Teste: a API oficial do Mercado Livre serve para achar ofertas?

Rode no seu PC, na raiz do projeto, com a .venv ativada:

    python teste_api_ml.py

Usa o token já salvo em data/ml_tokens.json (o mesmo do mercado_livre_api.py).
Não imprime tokens nem segredos; só resultados da busca pública.
"""

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import config  # noqa: E402
from app.mercado_livre_api import TOKEN_FILE, MercadoLivreAPI  # noqa: E402

BUSCA = "https://api.mercadolibre.com/sites/MLB/search"
CATEGORIAS = {"MLB1051": "Celulares", "MLB1430": "Moda/Calçados"}


def resumir(resp) -> int:
    """Imprime um resumo e devolve quantos itens vieram COM preço original (desconto)."""
    print(f"   HTTP {resp.status_code}")
    if resp.status_code != 200:
        print("   resposta:", resp.text[:200].replace("\n", " "))
        return 0
    dados = resp.json()
    itens = dados.get("results", [])
    com_desconto = [i for i in itens if i.get("original_price")]
    total = dados.get("paging", {}).get("total")
    print(
        f"   total no site: {total} | retornados: {len(itens)} | "
        f"com preço original (em promoção): {len(com_desconto)}"
    )
    for i in (com_desconto or itens)[:3]:
        print(
            "   -", (i.get("title") or "")[:55],
            "| R$", i.get("price"), "| de", i.get("original_price"),
            "|", i.get("category_id"),
        )
    return len(com_desconto)


def buscar(categoria: str, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.get(
        BUSCA, params={"category": categoria, "limit": 20}, headers=headers, timeout=20
    )


def main() -> None:
    print("client_id configurado:", bool(config.MERCADO_LIVRE_CLIENT_ID))
    print("client_secret configurado:", bool(config.MERCADO_LIVRE_CLIENT_SECRET))
    print("arquivo de tokens existe:", TOKEN_FILE.exists())

    token = None
    try:
        api = MercadoLivreAPI(
            config.MERCADO_LIVRE_CLIENT_ID, config.MERCADO_LIVRE_CLIENT_SECRET, ""
        )
        token = api.get_token_valido()
        print("token válido obtido: sim")
    except Exception as erro:  # noqa: BLE001
        print("token válido obtido: NÃO ->", type(erro).__name__, str(erro)[:150])

    total_desconto = 0
    for cat, nome in CATEGORIAS.items():
        print(f"\n[{cat} {nome}] sem token:")
        try:
            resumir(buscar(cat))
        except requests.RequestException as erro:
            print("   falha de rede:", type(erro).__name__)
        if token:
            print(f"[{cat} {nome}] com token:")
            try:
                total_desconto += resumir(buscar(cat, token))
            except requests.RequestException as erro:
                print("   falha de rede:", type(erro).__name__)

    print("\n" + "=" * 60)
    if total_desconto:
        print("A busca da API funciona e traz itens em promoção: dá para usá-la no lugar do scraping.")
    else:
        print("Nenhum item em promoção veio da API (ou ela recusou o acesso). "
              "Mande a saída acima para eu decidir o próximo passo.")


if __name__ == "__main__":
    main()