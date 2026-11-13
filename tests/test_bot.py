import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, mock_open, patch

from app import bot, config
from app import mercado_livre, promocoes, whatsapp
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
        with patch.object(mercado_livre, "_proxima_busca_http", 0.0), \
                patch.object(mercado_livre, "_alerta_verificacao_entregue", False), \
                patch.object(mercado_livre.time, "monotonic", side_effect=[1, 1, 61, 1801, 1801]), \
                patch("app.mercado_livre.requests.get", return_value=response) as buscar, \
                patch.object(whatsapp, "enviar_alerta_privado", return_value=True) as avisar:
            self.assertEqual(mercado_livre.buscar_ofertas(max_paginas=1), [])
            self.assertEqual(mercado_livre.buscar_ofertas(max_paginas=1), [])
            buscar.assert_called_once()
            self.assertEqual(mercado_livre.buscar_ofertas(max_paginas=1), [])
            self.assertEqual(buscar.call_count, 2)
            avisar.assert_called_once()

    def test_alert_only_uses_individual_number(self):
        ambiente = {
            "WHATSAPP_API_URL": "https://example.invalid",
            "WHATSAPP_API_KEY": "test-key",
            "WHATSAPP_INSTANCE": "teste",
            "WHATSAPP_GROUP_JID": "123456789@g.us",
            "WHATSAPP_ADMIN_NUMBER": "+5511000000000",
        }
        with patch.dict(os.environ, ambiente), patch.object(config, "TEST_MODE", False), \
                patch.object(whatsapp.requests, "post", return_value=SimpleNamespace(status_code=201)) as post:
            self.assertTrue(whatsapp.enviar_alerta_privado("Alerta"))
            self.assertEqual(post.call_args.kwargs["json"]["number"], "5511000000000")
            post.reset_mock()
            for destino in ("", ambiente["WHATSAPP_GROUP_JID"]):
                with patch.dict(os.environ, {"WHATSAPP_ADMIN_NUMBER": destino}):
                    self.assertFalse(whatsapp.enviar_alerta_privado("Alerta"))
            post.assert_not_called()

    def test_final_filter_logs_rejection_reason(self):
        ofertas = [
            {"origem": "shopee", "preco_atual": 29.99, "desconto": 20},
            {"origem": "shopee", "preco_atual": 30.0, "desconto": 20},
        ]
        with patch.object(config, "PRECO_MINIMO", 30), patch.object(config, "PRECO_MAXIMO", 50000), \
                patch.object(config, "DESCONTO_MAXIMO_SUSPEITO", 90), \
                self.assertLogs("app.promocoes", level="INFO") as logs:
            self.assertEqual(promocoes.filtrar_ofertas(ofertas, desconto_min=20), ofertas[1:])
        self.assertIn("'preco_baixo': 1", logs.output[-1])

    def test_shopee_uses_its_own_price_floor(self):
        oferta = {
            "produto_id": "shopee_1_2", "origem": "shopee", "titulo": "Oferta",
            "preco_atual": 18.58, "desconto": 20,
        }
        with patch.object(config, "PRECO_MINIMO", 30), patch.object(config, "SHOPEE_PRECO_MINIMO", 10), \
                patch.object(config, "SHOPEE_MIN_DESCONTO", 20), patch.object(config, "PRECO_MAXIMO", 50000), \
                patch.object(promocoes, "filtrar_por_categoria", side_effect=lambda ofertas: ofertas), \
                patch.object(bot.shopee, "buscar_ofertas", return_value=[oferta]), \
                patch.object(bot.database, "ids_ja_publicados", return_value=set()):
            self.assertEqual(len(bot._candidatos_shopee(1)), 1)
            self.assertEqual(promocoes.filtrar_ofertas([oferta], desconto_min=20), [])

    def test_empty_collection_preserves_existing_offers_file(self):
        with tempfile.TemporaryDirectory() as diretorio:
            arquivo = Path(diretorio) / "ml_ofertas.json"
            original = '{"ofertas":[{"titulo":"oferta existente"}]}'
            arquivo.write_text(original, encoding="utf-8")
            with patch.object(coletar_ml, "SAIDA", arquivo):
                with self.assertRaisesRegex(RuntimeError, "arquivo atual foi preservado"):
                    coletar_ml.salvar_ofertas([])
            self.assertEqual(arquivo.read_text(encoding="utf-8"), original)

    def test_saved_collection_uses_utc_and_can_be_loaded(self):
        with tempfile.TemporaryDirectory() as diretorio:
            arquivo = Path(diretorio) / "ml_ofertas.json"
            ofertas = [{"titulo": "Oferta coletada"}]
            with patch.object(coletar_ml, "SAIDA", arquivo):
                coletar_ml.salvar_ofertas(ofertas)
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
            self.assertTrue(dados["gerado_em"].endswith("+00:00"))
            with patch.dict(os.environ, {"ML_JSON_PATH": str(arquivo)}):
                self.assertEqual(bot._ler_ofertas_ml_json(), ofertas)

    def test_interrupted_collection_returns_offers_already_collected(self):
        page = Mock()
        page.url = "https://lista.mercadolivre.com.br/celulares-smartphones_NoIndex_True"
        page.content.return_value = "<html></html>"
        page.mouse.wheel.return_value = None
        context = Mock()
        context.pages = [page]
        context.close.side_effect = Exception("Connection closed while reading from the driver")
        salvar_parcial = Mock()
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

            ofertas = coletar_ml.coletar(2, salvar_parcial=salvar_parcial)

        self.assertEqual(ofertas, [oferta])
        salvar_parcial.assert_called_once_with([oferta])
        context.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
