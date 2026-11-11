import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, mock_open, patch

from app import bot, config
from app import mercado_livre
import coletar_ml


class BotTests(unittest.TestCase):
    def test_expired_ml_json_is_ignored(self):
        generated = datetime(2026, 1, 1)
        now = generated + timedelta(hours=bot.ML_JSON_MAX_IDADE_HORAS + 1)
        payload = json.dumps({"gerado_em": generated.isoformat(), "ofertas": [{"titulo": "antiga"}]})

        with patch("builtins.open", mock_open(read_data=payload)), patch("app.bot.datetime") as mocked_datetime:
            mocked_datetime.fromisoformat.return_value = generated
            mocked_datetime.now.return_value = now

            self.assertEqual(bot._ler_ofertas_ml_json(), [])

    def test_stale_ml_json_falls_back_to_live_search(self):
        categoria_url = "https://lista.mercadolivre.com.br/celulares-smartphones_NoIndex_True"
        oferta = {"titulo": "Oferta atual"}

        with patch.dict(os.environ, {"ML_USAR_JSON": "true"}), \
                patch("app.bot._ler_ofertas_ml_json", return_value=[]), \
                patch("app.bot.mercado_livre.buscar_ofertas", return_value=[oferta]) as buscar, \
                patch("app.bot._filtrar_apenas_ineditas", return_value=[oferta]), \
                patch("app.bot.promocoes.preparar_promocoes_para_publicar", return_value=[oferta]):
            resultado = bot._candidatos_ml(categoria_url, 1)

        self.assertEqual(resultado, [oferta])
        buscar.assert_called_once_with(url_categoria=categoria_url)

    def test_partial_ml_json_falls_back_for_missing_category(self):
        categoria_url = "https://lista.mercadolivre.com.br/celulares-smartphones_NoIndex_True"
        oferta = {"titulo": "Oferta atual"}

        with patch.dict(os.environ, {"ML_USAR_JSON": "true"}), \
                patch("app.bot._ler_ofertas_ml_json", return_value=[{"categoria": "Moda"}]), \
                patch("app.bot.mercado_livre.buscar_ofertas", return_value=[oferta]) as buscar, \
                patch("app.bot._filtrar_apenas_ineditas", return_value=[oferta]), \
                patch("app.bot.promocoes.preparar_promocoes_para_publicar", return_value=[oferta]):
            resultado = bot._candidatos_ml(categoria_url, 1)

        self.assertEqual(resultado, [oferta])
        buscar.assert_called_once_with(url_categoria=categoria_url)

    def test_next_round_wait_does_not_message_channels(self):
        with patch("app.bot.telegram.enviar_mensagem") as telegram_send, \
                patch("app.bot.whatsapp.enviar_mensagem") as whatsapp_send, \
                patch("app.bot.time.sleep") as dormir:
            bot._aguardar_proxima_rodada(2)

        telegram_send.assert_not_called()
        whatsapp_send.assert_not_called()
        dormir.assert_called_once_with(120)

    def test_offer_is_published_when_test_mode_is_disabled(self):
        oferta = {
            "produto_id": "MLB12345678",
            "url_produto": "https://produto.mercadolivre.com.br/MLB12345678",
            "url_afiliado": "https://mercadolivre.com/sec/afiliado",
        }

        with patch.object(config, "TEST_MODE", False), \
                patch("app.bot.database.produto_ja_publicado", return_value=False), \
                patch("app.bot.promocoes.montar_mensagem", return_value="Oferta"), \
                patch("app.bot._enviar_para_telegram", return_value=True) as telegram_send, \
                patch("app.bot._publicar_no_whatsapp", return_value=False), \
                patch("app.bot.database.salvar_promocao") as salvar, \
                patch("app.bot.time.sleep"):
            self.assertTrue(bot._processar_e_publicar_oferta(oferta, 0))

        telegram_send.assert_called_once()
        salvar.assert_called_once_with(oferta)

    def test_account_verification_redirect_stops_http_scraping(self):
        response = SimpleNamespace(
            status_code=200,
            url="https://www.mercadolivre.com.br/gz/account-verification",
            text="<html>verification</html>",
        )
        with patch("app.mercado_livre.requests.get", return_value=response):
            self.assertEqual(mercado_livre.buscar_ofertas(max_paginas=1), [])

    def test_empty_collection_preserves_existing_offers_file(self):
        with tempfile.TemporaryDirectory() as diretorio:
            arquivo = Path(diretorio) / "ml_ofertas.json"
            original = '{"ofertas":[{"titulo":"oferta existente"}]}'
            arquivo.write_text(original, encoding="utf-8")
            with patch.object(coletar_ml, "SAIDA", arquivo):
                with self.assertRaisesRegex(RuntimeError, "arquivo atual foi preservado"):
                    coletar_ml.salvar_ofertas([])
            self.assertEqual(arquivo.read_text(encoding="utf-8"), original)

    def test_interrupted_collection_returns_offers_already_collected(self):
        page = Mock()
        page.url = "https://lista.mercadolivre.com.br/celulares-smartphones_NoIndex_True"
        page.content.return_value = "<html></html>"
        page.mouse.wheel.return_value = None
        context = Mock()
        context.pages = [page]
        playwright = SimpleNamespace(
            chromium=SimpleNamespace(launch_persistent_context=Mock(return_value=context))
        )
        oferta = {
            "url_produto": "https://produto.mercadolivre.com.br/MLB12345678",
            "titulo": "Celular",
        }

        with patch.object(coletar_ml, "sync_playwright") as launch, \
                patch.object(coletar_ml.ml, "NICHOS_ESTRATEGICOS", [
                    {"nome": "Teste", "url": page.url},
                ]), \
                patch.object(coletar_ml, "_aguardar_liberacao", side_effect=[True, KeyboardInterrupt]), \
                patch.object(coletar_ml, "BeautifulSoup") as soup, \
                patch.object(coletar_ml.ml, "_extrair_promocao", return_value=oferta), \
                patch.object(coletar_ml.time, "sleep"):
            launch.return_value.__enter__.return_value = playwright
            soup.return_value.select.return_value = [object()]

            ofertas = coletar_ml.coletar(2)

        self.assertEqual(ofertas, [oferta])
        context.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
