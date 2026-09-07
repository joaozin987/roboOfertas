import os
import requests
from typing import Optional
from app import config

API_URL = "https://www.mercadolivre.com.br/affiliate-program/api/v2/affiliates/createLink"


def _obter_config(chave: str, padrao: str = "") -> str:
    return getattr(config, chave, None) or os.getenv(chave, padrao)


def gerar_link_afiliado(url_produto: str, usar_link_curto: bool = True) -> str:
    """
    Gera o link oficial de afiliado do Mercado Livre chamando a API interna.
    Retorna o short_url (https://meli.la/...) ou long_url (/social/...).
    Se houver falha, retorna a URL original.
    """
    affiliate_tag = _obter_config("MELI_AFFILIATE_TAG", "dosjoao20220906213738")
    csrf_token = _obter_config("MELI_CSRF_TOKEN", "")
    cookie_header = _obter_config("MELI_COOKIE_HEADER", "")

    if not csrf_token or not cookie_header:
        print("[AVISO AFILIADOS] CSRF_TOKEN ou COOKIE_HEADER não configurados.")
        return url_produto

    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "content-type": "application/json",
        "origin": "https://www.mercadolivre.com.br",
        "referer": "https://www.mercadolivre.com.br/afiliados/linkbuilder",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "x-csrf-token": csrf_token,
        "cookie": cookie_header,
    }

    payload = {
        "urls": [url_produto],
        "tag": affiliate_tag,
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=10)

        if response.status_code in (200, 201):
            data = response.json()
            urls = data.get("urls", [])
            if urls and isinstance(urls, list) and len(urls) > 0:
                item = urls[0]
                if usar_link_curto:
                    link = item.get("short_url") or item.get("long_url")
                else:
                    link = item.get("long_url") or item.get("short_url")

                if link:
                    return link

        print(f"[ERRO AFILIADOS] Status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[ERRO AFILIADOS] Exceção na requisição: {e}")

    return url_produto

# if __name__ == "__main__":
#     url = "https://www.mercadolivre.com.br/desempenadeira-de-aco-inox-25cm-para-acabamentos-profissionais-em-gesso-e-massa-corrida-liso-perfeito-aero-home/p/MLB65320859?product_trigger_id=MLB65320860&pdp_filters=shipping_time%3Anextday&applied_product_filters=MLB65320859&picker=true&quantity=1"

#     print("URL original:")
#     print(url)

#     print("\nGerando link de afiliado...")

#     link = gerar_link_afiliado(url)

#     print("\nLINK GERADO:")
#     print(link)