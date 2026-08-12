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

### 4. Testar o envio da primeira mensagem

Por padrão, `TEST_MODE=true` no `.env.example`, então o bot só **imprime
no terminal** a mensagem que seria enviada, sem publicar de verdade:

```bash
python main.py
```

Saída esperada:

```text
[INFO] Bot iniciado
[INFO] Enviando mensagem de teste para o Telegram
[INFO] TEST_MODE ativo: mensagem não enviada de verdade.
[TESTE] Mensagem que seria enviada ao Telegram:

✅ Bot de Promoções conectado com sucesso!

Esta é uma mensagem de teste da Fase 1.

Não publicado no Telegram (TEST_MODE=true).
[INFO] Mensagem de teste enviada com sucesso
[INFO] Execução finalizada
```

Quando quiser publicar de verdade no canal, defina `TEST_MODE=false` no
`.env` e rode `python main.py` novamente.

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
| `TEST_MODE`                    | Não (padrão `true`)   | Se `true`, não publica de verdade — só mostra no terminal        |
| `MERCADO_LIVRE_CLIENT_ID`      | Não (Fase 3)           | Usado apenas a partir da integração com o Mercado Livre           |
| `MERCADO_LIVRE_CLIENT_SECRET`  | Não (Fase 3)           | Usado apenas a partir da integração com o Mercado Livre           |
| `AFILIADO_ID`                  | Não (Fase 3+)          | Identificador de afiliado usado ao montar os links               |
| `CUPOM_DESCONTO`               | Não (Fase 3+)          | Cupom padrão a ser exibido nas mensagens, se aplicável            |
| `CHECK_INTERVAL_MINUTES`       | Não (Fase 6)           | Intervalo entre execuções automáticas                             |
| `MAX_PROMOTIONS_PER_RUN`       | Não (Fase 4+)          | Limite de promoções publicadas por execução                       |

---

## 🗺️ Próximas fases

- **Fase 2** — Banco de dados SQLite para registrar promoções já publicadas.
- **Fase 3** — Integração oficial com a API de afiliados do Mercado Livre.
- **Fase 4** — Filtros de desconto mínimo, faixa de preço e remoção de duplicados.
- **Fase 5** — Fluxo completo: buscar → filtrar → verificar banco → publicar → salvar.
- **Fase 6** — Agendamento automático com APScheduler (`CHECK_INTERVAL_MINUTES`).
