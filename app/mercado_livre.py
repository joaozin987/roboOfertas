"""
Camada de comunicação com o Mercado Livre (Versão API JSON Pública com Tratamento de Conexão).
"""

import logging
import os
import random
import time
from typing import Dict, List, Optional

import requests

from app import config
from app.afiliados import gerar_link_afiliado

logger = logging.getLogger(__name__)
BASE_URL = "https://www.mercadolivre.com.br"


def _preco_maximo() -> float:
    try:
        return float(os.getenv("ML_PRECO_MAXIMO") or getattr(config, "ML_PRECO_MAXIMO", 900.0))
    except (TypeError, ValueError):
        return 900.0


NICHOS_ESTRATEGICOS = [
    {"nome": "Smartphones & Celulares", "termo": "celulares smartphones", "url": "https://lista.mercadolivre.com.br/celulares-smartphones_NoIndex_True"},
    {"nome": "Moda & Calçados", "termo": "calcados roupas", "url": "https://lista.mercadolivre.com.br/calcados-roupas_NoIndex_True"},
    {"nome": "Corrida & Esportes", "termo": "esportes fitness", "url": "https://lista.mercadolivre.com.br/esportes-fitness_NoIndex_True"},
    {"nome": "Informática & Games", "termo": "informatica games", "url": "https://lista.mercadolivre.com.br/informatica-games_NoIndex_True"},
    {"nome": "Casa & Eletrodomésticos", "termo": "eletrodomesticos", "url": "https://lista.mercadolivre.com.br/eletrodomesticos_NoIndex_True"},
    {"nome": "Beleza & Cuidados", "termo": "beleza cuidado pessoal", "url": "https://lista.mercadolivre.com.br/beleza-cuidado-pessoal_NoIndex_True"},
]

TERMOS_OBRIGATORIOS_POR_CATEGORIA = {
    "Smartphones & Celulares": ["smartphone", "celular", "iphone", "samsung", "galaxy", "xiaomi", "motorola", "moto"],
    "Moda & Calçados": ["tênis", "sapato", "camisa", "camiseta", "calça", "bermuda", "sandália", "chinelo", "mochila"],
    "Corrida & Esportes": ["tênis", "corrida", "esporte", "academia", "treino", "chuteira", "bicicleta", "whey", "creatina", "suplemento"],
    "Informática & Games": ["notebook", "laptop", "placa de vídeo", "processador", "monitor", "teclado", "mouse", "headset", "ssd", "gamer"],
    "Casa & Eletrodomésticos": ["air fryer", "liquidificador", "aspirador", "panela", "ventilador", "cafeteira", "micro-ondas"],
    "Beleza & Cuidados": ["perfume", "colônia", "desodorante", "creme", "shampoo", "secador", "prancha"],
}


def _validar_relevancia_titulo(titulo: str, categoria_nome: str) -> bool:
    if not titulo:
        return False
    titulo_lower = titulo.lower()
    termos = TERMOS_OBRIGATORIOS_POR_CATEGORIA.get(categoria_nome, [])
    if not termos:
        return True
    return any(termo in titulo_lower for termo in termos)


def calcular_desconto(preco_atual: float, preco_anterior: float) -> Optional[float]:
    if not preco_anterior or preco_anterior <= 0:
        return None
    return round(((preco_anterior - preco_atual) / preco_anterior) * 100, 1)


def montar_link_afiliado(url_produto: str) -> Optional[str]:
    return gerar_link_afiliado(url_produto) if url_produto else None


def buscar_ofertas(url_categoria: Optional[str] = None, max_paginas: Optional[int] = None) -> List[Dict]:
    """Busca ofertas diretamente na API JSON pública do Mercado Livre com estabilização de rede."""
    
    # Pausa de segurança na primeira execução para estabilizar o DNS do container no Railway
    time.sleep(3)

    paginas_para_buscar = max_paginas or getattr(config, "SCRAPER_MAX_PAGINAS", 3)
    promocoes = []

    nicho_atual = next((n for n in NICHOS_ESTRATEGICOS if n["url"] == url_categoria), None)
    termo_busca = nicho_atual["termo"] if nicho_atual else "ofertas"
    categoria_nome = nicho_atual["nome"] if nicho_atual else "Ofertas"

    url_api = "https://api.mercadolivre.com.br/sites/MLB/search"
    limite_por_pagina = 50

    logger.info("ML API: iniciando busca [%s] (termo: '%s') | páginas=%d", categoria_nome, termo_busca, paginas_para_buscar)

    for pagina in range(paginas_para_buscar):
        offset = pagina * limite_por_pagina
        params = {
            "q": termo_busca,
            "limit": limite_por_pagina,
            "offset": offset,
            "condition": "new"
        }

        tentativas = 3
        sucesso = False
        
        for tentativa in range(tentativas):
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Accept": "application/json",
                }
                response = requests.get(url_api, params=params, headers=headers, timeout=20)

                if response.status_code == 200:
                    sucesso = True
                    break
                else:
                    logger.warning("ML API status %d na tentativa %d", response.status_code, tentativa + 1)
                    time.sleep(2)
            except Exception as ce:
                logger.warning("ML API falha de conexão (tentativa %d/%d): %s", tentativa + 1, tentativas, ce)
                time.sleep(3)

        if not sucesso:
            logger.warning("ML API: Falha persistente de conexão/DNS para o nicho [%s]", categoria_nome)
            break

        try:
            dados = response.json()
            resultados = dados.get("results", [])

            if not resultados:
                break

            for item in resultados:
                titulo = item.get("title", "")
                if not _validar_relevancia_titulo(titulo, categoria_nome):
                    continue

                preco_atual = float(item.get("price", 0))
                if preco_atual <= 0 or preco_atual > _preco_maximo():
                    continue

                preco_original = item.get("original_price")
                preco_anterior = float(preco_original) if preco_original else None

                if preco_anterior is not None and preco_anterior <= preco_atual:
                    preco_anterior = None

                desconto = calcular_desconto(preco_atual, preco_anterior) if preco_anterior else None

                imagem = item.get("thumbnail", "").replace("http://", "https://")
                if "I.jpg" in imagem:
                    imagem = imagem.replace("I.jpg", "O.jpg")

                promocoes.append({
                    "origem": "mercado_livre",
                    "titulo": titulo,
                    "categoria": categoria_nome,
                    "preco_atual": preco_atual,
                    "preco_anterior": preco_anterior,
                    "desconto": desconto,
                    "imagem": imagem,
                    "url_produto": item.get("permalink", ""),
                    "url_afiliado": None,
                    "cupom": getattr(config, "CUPOM_DESCONTO", None),
                })

            time.sleep(getattr(config, "SCRAPER_REQUEST_DELAY_SECONDS", 2) + random.random())

        except Exception as err:
            logger.error("Erro ao processar dados da API JSON do Mercado Livre: %s", err, exc_info=True)
            break

    logger.info("ML API: %d promoções obtidas com sucesso em [%s]", len(promocoes), categoria_nome)
    return promocoes