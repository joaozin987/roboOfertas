"""
Utilitário para disparo manual de produtos específicos para o Telegram.
Extrai dados via API pública do Mercado Livre com fallback robusto.
"""

import logging
import re
import time
from typing import Optional, Dict
import requests

from app import config, database, mercado_livre, promocoes, telegram

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _consultar_api_ml(item_id: str) -> Optional[dict]:
    """Consulta os dados oficiais do produto via API pública do Mercado Livre."""
    # Normaliza ID para o padrão MLB123456789
    id_limpo = item_id.replace("MLBU", "MLB").replace("-", "")
    match = re.search(r"(MLB\d+)", id_limpo)
    if not match:
        return None
    
    api_id = match.group(1)
    url_api = f"https://api.mercadolibre.com/items/{api_id}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        resp = requests.get(url_api, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning("Falha ao consultar API do ML para %s: %s", api_id, e)

    return None


def preparar_dados_item(item: dict) -> Optional[dict]:
    """Monta o payload da promoção mesclando API pública e valores manuais."""
    url = item.get("url", "").strip()
    produto_id = database.extrair_produto_id(url)
    
    # Se na URL tiver item_id nos filtros (ex: pdp_filters=item_id:MLB7447850164), prioriza ele
    match_filter = re.search(r"item_id:(MLB\d+)", url)
    id_para_busca = match_filter.group(1) if match_filter else produto_id

    dados_api = _consultar_api_ml(id_para_busca) if id_para_busca else None

    # 1. Título
    titulo = item.get("titulo")
    if not titulo and dados_api:
        titulo = dados_api.get("title")

    # 2. Preços
    preco_atual = item.get("preco_atual")
    preco_anterior = item.get("preco_anterior")

    if preco_atual is None and dados_api:
        preco_atual = float(dados_api.get("price", 0.0))
        if dados_api.get("original_price"):
            preco_anterior = float(dados_api.get("original_price"))

    # 3. Imagem
    imagem = item.get("imagem")
    if not imagem and dados_api:
        pictures = dados_api.get("pictures", [])
        if pictures:
            imagem = pictures[0].get("secure_url") or pictures[0].get("url")
        else:
            imagem = dados_api.get("thumbnail")

    # 4. Desconto
    desconto = item.get("desconto")
    if desconto is None and preco_atual and preco_anterior:
        desconto = mercado_livre.calcular_desconto(preco_atual, preco_anterior)

    if not titulo or preco_atual is None:
        logger.warning("Não foi possível obter dados automáticos para o link: %s", url)
        return None

    return {
        "produto_id": produto_id,
        "titulo": titulo,
        "categoria": item.get("categoria", "Destaque"),
        "preco_atual": preco_atual,
        "preco_anterior": preco_anterior,
        "desconto": desconto,
        "imagem": imagem,
        "url_produto": mercado_livre.limpar_url_produto(url),
        "url_afiliado": None,
        "cupom": getattr(config, "CUPOM_DESCONTO", None),
    }


def _publicar_no_telegram(texto_mensagem: str, imagem_url: Optional[str] = None) -> bool:
    if imagem_url and hasattr(telegram, "enviar_foto"):
        try:
            return telegram.enviar_foto(imagem_url, texto_mensagem)
        except Exception:
            try:
                return telegram.enviar_foto(url_imagem=imagem_url, legenda=texto_mensagem)
            except Exception as err:
                logger.warning("Falha ao enviar foto: %s. Tentando texto...", err)

    if hasattr(telegram, "enviar_mensagem"):
        return telegram.enviar_mensagem(texto_mensagem)

    return False


def enviar_links_especificos(itens: list[dict]) -> None:
    database.inicializar_banco()

    for item in itens:
        url = item.get("url", "").strip()
        if not url:
            continue

        logger.info("=== Processando link manual: %s ===", url)

        promo = preparar_dados_item(item)
        if not promo:
            logger.error("❌ Falha crítica: Preencha os campos manualmente na lista para prosseguir.")
            continue

        produto_id = promo["produto_id"]
        logger.info("🔎 PRODUTO ID: %s", produto_id)

        # Gera o link de afiliado oficial
        logger.info("🔗 Gerando link de afiliado...")
        promo["url_afiliado"] = mercado_livre.montar_link_afiliado(url)

        # Monta a mensagem no mesmo padrão do bot oficial
        texto_mensagem = promocoes.montar_mensagem(promo)
        imagem_url = promo.get("imagem")

        logger.info("📢 Publicando no Telegram: %s", promo.get("titulo"))
        sucesso = _publicar_no_telegram(texto_mensagem, imagem_url)

        if sucesso:
            database.salvar_promocao(promo)
            logger.info("💾 Produto %s postado e salvo no banco!", produto_id)
        else:
            logger.error("❌ Falha no disparo do produto %s para o Telegram.", produto_id)

        time.sleep(3)


if __name__ == "__main__":
    LINKS_PARA_ENVIAR = [
        {
            "url": "https://www.mercadolivre.com.br/cadeira-de-escritorio-ergonomica-giratoria-tela-mesh-premium/up/MLBU4814507932?pdp_filters=item_id:MLB7447850164",
            "titulo": "Cadeira De Escritório Ergonômica Giratória Tela Mesh Premium",
            "categoria": "Cadeiras & Escritório",
            "preco_atual": 426.55,
            "preco_anterior": 1199.00,  # Corrigido sem o ponto de milhar
            "desconto": 64.4,
            "imagem": "https://http2.mlstatic.com/D_NQ_NP_2X_854402-MLB114990215620_082026-F-cadeira-de-escritorio-ergonomica-giratoria-tela-mesh-premium.webp",
        },
        {
            "url": "https://produto.mercadolivre.com.br/MLB-3078170721-mesa-escritorio-industrial-150x60-reforcado-ferro-homeoffice-_JM",
            "titulo": "Mesa Escritório Industrial 150x60 Reforçado Ferro Home Office",
            "categoria": "Móveis & Escritório",
            "preco_atual": 221.00,
            "preco_anterior": 271.99,
            "desconto": 18.7,
            # Lembre de colar a URL real da foto da mesa no lugar do placeholder abaixo:
            "imagem": "https://http2.mlstatic.com/D_NQ_NP_2X_789427-MLB109415561252_042026-F-mesa-escritorio-industrial-150x60-reforcado-ferro-homeoffice.webp",
        },
    ]

    enviar_links_especificos(LINKS_PARA_ENVIAR)