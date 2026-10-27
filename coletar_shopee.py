"""
Coletor da Shopee (roda no SEU PC, na pasta raiz do projeto).

Abre o painel de afiliados num Chrome de verdade (perfil salvo em
data/shopee_profile, então o login só é feito uma vez), escuta as respostas
da API que trazem a lista de produtos e grava data/shopee_oferta.json no
mesmo formato que você colava na mão.

Uso:
    python coletar_shopee.py

Fluxo:
  1. A janela abre no painel de ofertas de produtos.
  2. Faça login (se pedir), navegue pelas categorias/páginas que quiser.
     O script também rola a página sozinho.
  3. Volte ao terminal e aperte ENTER para salvar.
"""

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).parent
PERFIL = RAIZ / "data" / "shopee_profile"
SAIDA = RAIZ / "data" / "shopee_oferta.json"
URL_PAINEL = "https://affiliate.shopee.com.br/offer/product_offer"

itens_por_id = {}


def _extrair_lista(corpo):
    """Retorna a lista de produtos se a resposta tiver o formato esperado."""
    if not isinstance(corpo, dict):
        return []
    lista = (corpo.get("data") or {}).get("list")
    if not isinstance(lista, list):
        return []
    return [i for i in lista if isinstance(i, dict) and i.get("item_id") and (i.get("long_link") or i.get("product_link"))]


def _ao_receber(response):
    try:
        if response.request.resource_type not in ("xhr", "fetch"):
            return
        corpo = response.json()
    except Exception:
        return
    novos = 0
    for item in _extrair_lista(corpo):
        iid = str(item["item_id"])
        if iid not in itens_por_id:
            itens_por_id[iid] = item
            novos += 1
    if novos:
        print(f"  + {novos} produtos capturados (total {len(itens_por_id)})")


def main():
    PERFIL.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        contexto = pw.chromium.launch_persistent_context(
            user_data_dir=str(PERFIL),
            headless=False,
            locale="pt-BR",
            viewport={"width": 1366, "height": 850},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = contexto.pages[0] if contexto.pages else contexto.new_page()
        page.on("response", _ao_receber)

        print(f"Abrindo {URL_PAINEL}")
        try:
            page.goto(URL_PAINEL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"Aviso ao abrir o painel: {e}")

        print("\nFaça login se for pedido e navegue pelas ofertas.")
        print("O script rola a página sozinho por alguns segundos...")
        time.sleep(8)
        for _ in range(10):
            try:
                page.mouse.wheel(0, 2000)
            except Exception:
                break
            time.sleep(1.5)

        input("\nQuando terminar de navegar, volte aqui e aperte ENTER para salvar... ")
        contexto.close()

    if not itens_por_id:
        print("\nNenhum produto foi capturado; o arquivo NÃO foi alterado.")
        print("Confira se você estava na lista de produtos do painel e tente de novo.")
        return

    resposta = {"code": 0, "msg": "success", "data": {"list": list(itens_por_id.values())}}
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(resposta, f, ensure_ascii=False, indent=4)
    print(f"\n{len(itens_por_id)} produtos salvos em {SAIDA}")


if __name__ == "__main__":
    main()