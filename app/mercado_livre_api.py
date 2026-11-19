"""
Camada de integração com a API oficial do Mercado Livre (OAuth 2.0).
Gerencia tokens, renovação automática e sincronização de estoque.
"""

import os
import json
import time
import logging
import tempfile
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

TOKEN_FILE = Path(__file__).resolve().parent.parent / "data" / "ml_tokens.json"


class MercadoLivreAPI:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.base_url = "https://api.mercadolibre.com"
        self._carregar_tokens()

    def _carregar_tokens(self):
        caminho = self._caminho_tokens()
        if caminho.exists():
            try:
                with caminho.open(encoding="utf-8") as f:
                    self.tokens = json.load(f)
            except Exception as erro:
                logger.warning("Falha ao ler %s: %s", TOKEN_FILE, erro)
                self.tokens = {}
        else:
            self.tokens = {}

    def _caminho_tokens(self) -> Path:
        configurado = os.getenv("ML_TOKEN_PATH", "").strip()
        return Path(configurado) if configurado else TOKEN_FILE

    def _salvar_tokens(self, data: dict):
        data["expires_at"] = time.time() + data.get("expires_in", 21600) - 120
        # Se a resposta não trouxer refresh_token, mantém o que já existia
        if not data.get("refresh_token") and self.tokens.get("refresh_token"):
            data["refresh_token"] = self.tokens["refresh_token"]
        logger.info("Tokens salvos (campos: %s)", sorted(data.keys()))
        caminho = self._caminho_tokens()
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=caminho.parent, delete=False
        ) as arquivo:
            temporario = Path(arquivo.name)
            try:
                json.dump(data, arquivo, indent=2)
                arquivo.close()
                os.replace(temporario, caminho)
            finally:
                temporario.unlink(missing_ok=True)
        self.tokens = data

    def inicializar_com_code(self, tg_code: str):
        url = f"{self.base_url}/oauth/token"
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": tg_code,
            "redirect_uri": self.redirect_uri,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        res = requests.post(url, data=payload, headers=headers, timeout=15)

        if res.status_code == 200:
            self._salvar_tokens(res.json())
            logger.info("Conexão oficial com a API do Mercado Livre concluída com sucesso.")
            return True
        else:
            raise ValueError(f"Erro ao trocar token (HTTP {res.status_code})")

    def get_token_valido(self) -> str:
        if not self.tokens.get("access_token"):
            raise ValueError("Token não encontrado. Execute com --auth-ml primeiro.")

        # Token ainda válido: usa direto (não exige refresh_token)
        if time.time() < self.tokens.get("expires_at", 0):
            return self.tokens["access_token"]

        if not self.tokens.get("refresh_token"):
            raise ValueError(
                "Token expirado e o arquivo não tem refresh_token. "
                "Reautorize com --auth-ml (o app precisa permitir acesso offline)."
            )

        logger.info("Renovando access_token expirado via refresh_token...")
        url = f"{self.base_url}/oauth/token"
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.tokens["refresh_token"],
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        res = requests.post(url, data=payload, headers=headers, timeout=15)

        if res.status_code == 200:
            self._salvar_tokens(res.json())
            return self.tokens["access_token"]
        else:
            raise ValueError(f"Erro ao renovar token (HTTP {res.status_code})")

    def atualizar_estoque(self, item_id: str, quantidade: int) -> dict:
        token = self.get_token_valido()
        url = f"{self.base_url}/items/{item_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {"available_quantity": int(quantidade)}
        res = requests.put(url, json=payload, headers=headers, timeout=15)
        return res.json()

    def obter_item(self, item_id: str) -> dict:
        token = self.get_token_valido()
        url = f"{self.base_url}/items/{item_id}"
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get(url, headers=headers, timeout=15)
        return res.json()
