# 🤖 Bot de Promoções — Mercado Livre + Telegram

Bot automatizado para encontrar, filtrar e divulgar promoções do Mercado
Livre em um canal do Telegram, usando links de afiliado e cupons de
desconto.

> **Status atual: Fase 1 — Bot básico.**
> Nesta fase o bot só sabe carregar a configuração e enviar uma mensagem
> de teste para o Telegram. A integração com o Mercado Livre, o banco de
> dados, os filtros e o agendamento automático serão adicionados nas
> próximas fases.

---

## 📁 Estrutura do projeto

```text
bot-promocoes/
│
├── app/
│   ├── __init__.py
│   ├── bot.py            # Orquestração / logging (Fase 1)
│   ├── config.py         # Carrega e valida variáveis de ambiente
│   ├── database.py       # (stub — Fase 2)
│   ├── telegram.py       # Envio de mensagens ao Telegram
│   ├── promocoes.py      # (stub — Fases 3/4)
│   └── mercado_livre.py  # (stub — Fase 3)
│
├── data/
│   └── .gitkeep
│
├── tests/
│   └── __init__.py
│
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── main.py
```

---

## ✅ Pré-requisitos

- Python 3.11 ou superior
- Uma conta no Telegram
- Um bot criado através do [@BotFather](https://t.me/BotFather)

---

## 🚀 Como executar localmente

### 1. Clonar o projeto e criar o ambiente virtual

```bash
cd bot-promocoes
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
```

### 2. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 3. Configurar as variáveis de ambiente

Copie o arquivo de exemplo e preencha os valores:

```bash
cp .env.example .env
```

Edite o `.env` com um editor de texto. Veja a seção **Como configurar o
Telegram** abaixo para saber como obter `TELEGRAM_BOT_TOKEN` e
`TELEGRAM_CHANNEL_ID`.

> ⚠️ O arquivo `.env` nunca deve ser commitado — ele já está listado no
> `.gitignore`.

### 4. Validar o envio sem publicar

Para executar uma rodada sem publicar, defina `TEST_MODE=true` no `.env`:

```bash
python main.py --uma-vez
```

Quando estiver pronto para publicar de verdade nos canais configurados,
confirme que `TEST_MODE=false` está definido no `.env` e execute:

```bash
python main.py
```

---

## 📲 Como configurar o Telegram

1. **Criar o bot**
   - Abra uma conversa com [@BotFather](https://t.me/BotFather) no
     Telegram.
   - Envie `/newbot` e siga as instruções (nome e username do bot).
   - O BotFather vai te dar um **token** — copie esse valor para
     `TELEGRAM_BOT_TOKEN` no `.env`.

2. **Criar o canal**
   - Crie um canal no Telegram (pode ser público ou privado).
   - Adicione o bot criado como **administrador** do canal, com
     permissão para publicar mensagens.

3. **Obter o ID do canal**
   - Se o canal for **público**, use o `@username` do canal como
     `TELEGRAM_CHANNEL_ID` (ex.: `@meucanaldepromocoes`).
   - Se o canal for **privado**, você precisa do ID numérico (algo como
     `-1001234567890`). Uma forma simples de obter esse ID:
     1. Envie qualquer mensagem no canal.
     2. Encaminhe essa mensagem para o bot
        [@userinfobot](https://t.me/userinfobot) ou consulte o método
        `getUpdates` da API do Telegram
        (`https://api.telegram.org/bot<SEU_TOKEN>/getUpdates`) para ver
        o `chat_id` do canal.
   - Copie o valor para `TELEGRAM_CHANNEL_ID` no `.env`.

4. **Testar**
   - Com `TEST_MODE=false` no `.env`, rode `python main.py`.
   - Se tudo estiver certo, a mensagem de teste aparecerá no canal.

---

## ⚙️ Variáveis de ambiente (Fase 1)

| Variável                      | Obrigatória na Fase 1 | Descrição                                                        |
|--------------------------------|:---------------------:|-------------------------------------------------------------------|
| `TELEGRAM_BOT_TOKEN`           | Sim (se `TEST_MODE=false`) | Token do bot, gerado pelo BotFather                          |
| `TELEGRAM_CHANNEL_ID`          | Sim (se `TEST_MODE=false`) | ID ou `@username` do canal onde o bot publica                |
| `TEST_MODE`                    | Não (padrão `false`)  | Se `true`, não publica de verdade — só mostra no terminal        |
| `MERCADO_LIVRE_CLIENT_ID`      | Não (Fase 3)           | Usado apenas a partir da integração com o Mercado Livre           |
| `MERCADO_LIVRE_CLIENT_SECRET`  | Não (Fase 3)           | Usado apenas a partir da integração com o Mercado Livre           |
| `AFILIADO_ID`                  | Não (Fase 3+)          | Identificador de afiliado usado ao montar os links               |
| `CUPOM_DESCONTO`               | Não (Fase 3+)          | Cupom padrão a ser exibido nas mensagens, se aplicável            |
| `CHECK_INTERVAL_MINUTES`       | Não (Fase 6)           | Intervalo entre rodadas automáticas                                |
| `MAX_PROMOTIONS_PER_RUN`       | Não (Fase 4+)          | Limite de promoções publicadas por execução                       |

O bot aguarda `CHECK_INTERVAL_MINUTES` entre as buscas sem enviar mensagens
de status aos canais. Se `data/ml_ofertas.json` estiver vencido (mais de 12
horas), o bot tenta buscar ofertas diretamente no Mercado Livre.

### Atualizar as fontes de ofertas

Se o Mercado Livre redirecionar a busca para uma verificação de conta, atualize
o arquivo de ofertas pelo navegador:

```bash
python coletar_ml.py 1
```

Uma janela do Chrome será aberta. Entre na sua conta ou resolva a verificação
se solicitada. Se interromper com Ctrl+C, as ofertas já coletadas serão salvas;
se nenhuma oferta for coletada, o arquivo anterior será preservado. Pare o bot
antes de atualizar o arquivo e inicie `python main.py` depois da coleta.

A Shopee usa o arquivo exportado do painel de afiliados em
`data/shopee_oferta.json`; substitua-o por uma exportação recente. Arquivos
vencidos são ignorados para evitar publicar ofertas antigas.

---

## 🗺️ Próximas fases

- **Fase 2** — Banco de dados SQLite para registrar promoções já publicadas.
- **Fase 3** — Integração oficial com a API de afiliados do Mercado Livre.
- **Fase 4** — Filtros de desconto mínimo, faixa de preço e remoção de duplicados.
- **Fase 5** — Fluxo completo: buscar → filtrar → verificar banco → publicar → salvar.
- **Fase 6** — Agendamento automático com APScheduler (`CHECK_INTERVAL_MINUTES`).
