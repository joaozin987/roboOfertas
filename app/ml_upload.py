"""Transferência do lote do coletor ao serviço do robô."""

import hmac
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

import requests

logger = logging.getLogger(__name__)
MAX_BYTES = 20 * 1024 * 1024
ROTA = "/ingest/ml"


def caminho_lote() -> Path:
    configurado = os.getenv("ML_JSON_PATH", "").strip()
    return Path(configurado) if configurado else Path(__file__).resolve().parents[1] / "data/ml_ofertas.json"


def enviar_lote(arquivo: Path) -> bool:
    url = os.getenv("ML_UPLOAD_URL", "").strip()
    token = os.getenv("ML_UPLOAD_TOKEN", "").strip()
    if not url and not token:
        return False
    destino = urlsplit(url)
    if destino.scheme != "https" or not destino.hostname or destino.path != ROTA or len(token) < 32:
        raise RuntimeError("Configure ML_UPLOAD_URL (HTTPS, rota /ingest/ml) e ML_UPLOAD_TOKEN (32 caracteres ou mais).")
    try:
        with arquivo.open("rb") as lote:
            resposta = requests.put(
                url, data=lote, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=(5, 45), allow_redirects=False,
            )
    except requests.RequestException as erro:
        raise RuntimeError(f"Upload não confirmado ({type(erro).__name__}). Use --reenviar.") from None
    if resposta.status_code != 204:
        raise RuntimeError(f"Railway retornou HTTP {resposta.status_code}. Confira a configuração. Use --reenviar.")
    return True


def _validar_lote(conteudo: bytes) -> datetime:
    dados = json.loads(conteudo)
    if not isinstance(dados, dict):
        raise ValueError("Lote inválido")
    data = datetime.fromisoformat(dados.get("gerado_em", ""))
    ofertas = dados.get("ofertas")
    if data.tzinfo is None or not isinstance(ofertas, list) or not ofertas:
        raise ValueError("Lote sem horário com fuso ou sem ofertas")
    if any(
        not isinstance(oferta, dict)
        or not isinstance(oferta.get("url_produto"), str)
        or not oferta["url_produto"].startswith("https://")
        for oferta in ofertas
    ):
        raise ValueError("Oferta inválida")
    return data


def _receber_lote(caminho: Path, conteudo: bytes, validade_horas: int) -> int:
    gerado = _validar_lote(conteudo)
    idade = (datetime.now(timezone.utc) - gerado).total_seconds()
    if not 0 <= idade <= validade_horas * 3600:
        return 422

    try:
        anterior = caminho.read_bytes()
        data_anterior = datetime.fromisoformat(json.loads(anterior).get("gerado_em", ""))
    except (FileNotFoundError, ValueError, TypeError, AttributeError):
        data_anterior = None
    if data_anterior is not None and data_anterior.tzinfo is not None and gerado <= data_anterior:
        return 204 if conteudo == anterior else 409

    caminho.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=caminho.parent, delete=False) as temporario:
        arquivo = Path(temporario.name)
        try:
            temporario.write(conteudo)
            temporario.close()
            os.replace(arquivo, caminho)
        finally:
            arquivo.unlink(missing_ok=True)
    return 204


def iniciar_receptor(validade_horas: int) -> HTTPServer | None:
    token = os.getenv("ML_UPLOAD_TOKEN", "").strip()
    if not token:
        return None
    if len(token) < 32:
        raise ValueError("ML_UPLOAD_TOKEN deve ter pelo menos 32 caracteres.")
    esperado = f"Bearer {token}".encode("utf-8")
    caminho = caminho_lote()

    class Receptor(BaseHTTPRequestHandler):
        def setup(self) -> None:
            self.request.settimeout(10)
            super().setup()

        def do_PUT(self) -> None:
            status = self.receber()
            self.send_response(status)
            self.end_headers()

        def receber(self) -> int:
            if self.path != ROTA:
                return 404
            credencial = self.headers.get("Authorization", "").encode("utf-8")
            if not hmac.compare_digest(credencial, esperado):
                return 401
            try:
                tamanho = int(self.headers.get("Content-Length", "0"))
                if not 0 < tamanho <= MAX_BYTES:
                    return 413
                conteudo = self.rfile.read(tamanho)
                if len(conteudo) != tamanho:
                    return 400
                return _receber_lote(caminho, conteudo, validade_horas)
            except (ValueError, TypeError):
                return 400
            except OSError:
                logger.exception("Falha de I/O no recebimento do lote do Mercado Livre.")
                return 500

        def log_message(self, format: str, *args: object) -> None:
            pass

    servidor = HTTPServer(("0.0.0.0", int(os.getenv("PORT", "8080"))), Receptor)
    Thread(target=servidor.serve_forever, daemon=True).start()
    logger.info("Receptor de lotes do Mercado Livre ativo na porta %d.", servidor.server_port)
    return servidor
