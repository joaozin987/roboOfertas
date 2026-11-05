"""
Coletor do Mercado Livre (roda no SEU PC, na pasta raiz do projeto).

Abre um Chrome de verdade (Playwright), usa um perfil salvo em data/ml_profile
(então o captcha só precisa ser resolvido uma vez) e grava data/ml_ofertas.json.

Uso:
    python coletar_ml.py              # todos os nichos, 5 páginas cada
    python coletar_ml.py 3            # todos os nichos, 3 páginas cada

Instalação (uma vez):
    python -m pip install -r requirements.txt
    python -m playwright install chromium
"""

import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from app import mercado_livre as ml

RAIZ = Path(__file__).parent
PERFIL = RAIZ / "data" / "ml_profile"
SAIDA = RAIZ / "data" / "ml_ofertas.json"
ESPERA_CAPTCHA_S = 300  # tempo máximo para você resolver o captcha na janela

SELETOR_CARDS = "div.poly-card, li.ui-search-layout__item, li.promotion-item"


def _tem_bloqueio(url: str) -> bool:
    return any(t in url for t in ("captcha", "account-verification", "/login", "gz/"))


def _aguardar_liberacao(page, url_destino: str) -> bool:
    """Se cair em captcha/verificação, espera você resolver na janela aberta."""
    if not _tem_bloqueio(page.url):
        return True
    print(f"\n>>> VERIFICAÇÃO DO ML detectada. Resolva na janela do navegador (até {ESPERA_CAPTCHA_S}s)...")
    limite = time.time() + ESPERA_CAPTCHA_S
    while time.time() < limite:
        time.sleep(2)
        if not _tem_bloqueio(page.url):
            return True
    return False


def coletar(max_paginas: int) -> list:
    PERFIL.mkdir(parents=True, exist_ok=True)
    todas, vistos = [], set()

    with sync_playwright() as pw:
        contexto = pw.chromium.launch_persistent_context(
            user_data_dir=str(PERFIL),
            headless=False,  # janela visível: necessário para resolver captcha
            locale="pt-BR",
            viewport={"width": 1366, "height": 850},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = contexto.pages[0] if contexto.pages else contexto.new_page()

        for nicho in ml.NICHOS_ESTRATEGICOS:
            nome, base = nicho["nome"], nicho["url"]
            print(f"\n=== {nome} ===")
            for pagina in range(1, max_paginas + 1):
                url = ml._montar_url_paginada(base, pagina)
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                except Exception as e:
                    print(f"  pág {pagina}: erro ao abrir ({e})")
                    break

                if not _aguardar_liberacao(page, url):
                    print("  captcha não resolvido a tempo; pulando nicho")
                    break
                if _tem_bloqueio(page.url) is False and page.url.split("?")[0] != url.split("?")[0] and "mercadolivre" not in page.url:
                    break

                try:
                    page.wait_for_selector(SELETOR_CARDS, timeout=15000)
                except Exception:
                    print(f"  pág {pagina}: nenhum card apareceu; encerrando nicho")
                    break

                # rolagem para carregar imagens preguiçosas
                for _ in range(4):
                    page.mouse.wheel(0, 1500)
                    time.sleep(0.6)

                soup = BeautifulSoup(page.content(), "html.parser")
                cards = []
                for sel in ml._SELETORES["card"]:
                    if achados := soup.select(sel):
                        cards = achados
                        break

                novos = 0
                for card in cards:
                    promo = ml._extrair_promocao(card, categoria_nome=nome)
                    if promo and promo["url_produto"] not in vistos:
                        vistos.add(promo["url_produto"])
                        todas.append(promo)
                        novos += 1
                print(f"  pág {pagina}: {len(cards)} cards, {novos} aproveitados")
                time.sleep(3 + random.random() * 2)

        contexto.close()
    return todas


if __name__ == "__main__":
    paginas = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    ofertas = coletar(paginas)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump({"gerado_em": datetime.now().isoformat(), "ofertas": ofertas}, f, ensure_ascii=False, indent=2)
    print(f"\n{len(ofertas)} ofertas salvas em {SAIDA}")