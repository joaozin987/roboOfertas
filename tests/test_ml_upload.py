import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import requests

from app import ml_upload


class UploadTests(unittest.TestCase):
    def test_receptor_requires_token_and_preserves_latest_batch(self):
        token = "x" * 32
        agora = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as diretorio:
            caminho = Path(diretorio) / "lote.json"
            with patch.dict(os.environ, {"PORT": "0", "ML_UPLOAD_TOKEN": token, "ML_JSON_PATH": str(caminho)}):
                servidor = ml_upload.iniciar_receptor(12)
            self.addCleanup(servidor.server_close)
            self.addCleanup(servidor.shutdown)
            url = f"http://127.0.0.1:{servidor.server_port}/ingest/ml"

            def lote(data):
                return json.dumps({
                    "gerado_em": data.isoformat(),
                    "ofertas": [{"url_produto": "https://example.test/item"}],
                }).encode()

            atual = lote(agora)
            self.assertEqual(requests.put(url, data=atual, timeout=5).status_code, 401)
            self.assertFalse(caminho.exists())
            headers = {"Authorization": f"Bearer {token}"}
            for corpo, status in (
                (b"{}", 400),
                (lote(agora - timedelta(hours=13)), 422),
                (atual, 204),
                (atual, 204),
                (lote(agora - timedelta(minutes=1)), 409),
            ):
                self.assertEqual(requests.put(url, data=corpo, headers=headers, timeout=5).status_code, status)
            self.assertEqual(caminho.read_bytes(), atual)
