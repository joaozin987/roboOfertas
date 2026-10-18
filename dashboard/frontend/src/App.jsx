import React from "react";

/* ============================================================
   LINKS
   ============================================================ */
const WHATSAPP_GROUP_URL = "https://chat.whatsapp.com/Gvs5pMsyjr80LqJtIESaMX";
const TELEGRAM_GROUP_URL = "https://t.me/promocoesjpzz";

/* ============================================================
   PROVAS REAIS (o que mais passa segurança)
   Preencha só com informação verdadeira. Campo vazio = não aparece.
   ============================================================ */
const PROOF = {
  members: "",      // ex: "1.200 pessoas" (número real do grupo)
  screenshot: "",   // print real do grupo: coloque em /public e use "/grupo.jpg"
  ownerName: "",    // ex: "João"
  ownerPhoto: "",   // sua foto: "/joao.jpg"
  ownerText: "",    // ex: "Eu mesmo cuido do grupo e confiro as ofertas."
};

/* ============================================================
   OFERTAS DE EXEMPLO (2 a 3 REAIS e conferidas). Vazio = seção some.
   { store, name, image, price, oldPrice, url, checkedAt }
   ============================================================ */
const OFFERS = [];

/* ============================================================
   RASTREAMENTO (Pixel da Meta, Google Analytics ou GTM)
   ============================================================ */
const track = (eventName) => {
  try {
    if (window.fbq) {
      window.fbq("trackCustom", eventName);
      window.fbq("track", "Lead");
    }
    if (window.gtag) window.gtag("event", eventName);
    if (window.dataLayer) window.dataLayer.push({ event: eventName });
  } catch (e) {}
};

const FACTS = [
  ["Grátis", "Entrada livre"],
  ["Sem cadastro", "Abre no WhatsApp"],
  ["Saia quando quiser", "Sem compromisso"],
];

const STEPS = [
  "Nosso robô monitora oportunidades e promoções.",
  "As ofertas selecionadas são compartilhadas nos grupos.",
  "Você acessa os links e aproveita as oportunidades disponíveis.",
];

const RULES = [
  ["Entrar é grátis e sem cadastro", "O convite abre direto no seu WhatsApp."],
  ["Só os administradores enviam mensagens", "Ninguém fica mandando recado no meio das ofertas."],
  ["As ofertas chegam em intervalos", "Dá para acompanhar uma de cada vez."],
  ["Os links levam para as lojas oficiais", "Você compra direto no Mercado Livre ou na Shopee."],
];

const WhatsIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z" />
  </svg>
);

const CheckIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0F7A3A"
    strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </svg>
);

export default function App() {
  const hasOwner = PROOF.ownerName && PROOF.ownerPhoto;

  return (
    <div className="jpz">
      <style>{css}</style>

      {/* ============ TOPO ============ */}
      <header className="top">
        <div className="wrap top-in">
          <div className="logo">JP</div>
          <div className="brand">JPZ Ofertas</div>
        </div>
      </header>

      {/* ============ PRIMEIRA TELA ============ */}
      <section className="hero">
        <div className="wrap hero-in">
          <div className="hero-text">
            <h1 className="title">
              As melhores ofertas do Mercado Livre e da Shopee em um só lugar!
            </h1>
            <p className="subtitle">
              Nosso robô monitora promoções para você aproveitar oportunidades
              antes que acabem.
            </p>

            <a className="btn" href={WHATSAPP_GROUP_URL} onClick={() => track("click_whatsapp")}>
              <WhatsIcon />
              ENTRAR NO GRUPO DO WHATSAPP
            </a>
            <p className="cta-note">Receba ofertas e descontos diretamente no grupo.</p>

            <ul className="facts">
              {FACTS.map(([t, s]) => (
                <li key={t}>
                  <strong>{t}</strong>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="hero-art">
            {PROOF.screenshot ? (
              <img className="shot" src={PROOF.screenshot}
                alt="Print do grupo de ofertas no WhatsApp" />
            ) : (
              <div className="stores">
                <div className="store store-ml">
                  <strong>Mercado Livre</strong>
                  <span>Ofertas monitoradas pelo nosso robô</span>
                </div>
                <div className="store store-sp">
                  <strong>Shopee</strong>
                  <span>Ofertas monitoradas pelo nosso robô</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ============ COMO FUNCIONA ============ */}
      <section className="sec sec-gray">
        <div className="wrap">
          <h2 className="sec-title">Como funciona o Jpz Ofertas?</h2>
          <ol className="steps">
            {STEPS.map((text, i) => (
              <li key={i} className="step">
                <span className="step-n">{i + 1}</span>
                <p>{text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ============ OFERTAS (só se houver) ============ */}
      {OFFERS.length > 0 && (
        <section className="sec">
          <div className="wrap">
            <h2 className="sec-title">Exemplos de ofertas</h2>
            <div className="offers">
              {OFFERS.map((o) => {
                const Tag = o.url ? "a" : "div";
                const link = o.url ? { href: o.url, target: "_blank", rel: "noreferrer" } : {};
                return (
                  <Tag key={o.name} className="offer" {...link}>
                    {o.image && <img src={o.image} alt={o.name} width="84" height="84" loading="lazy" />}
                    <div>
                      <small>{o.store}</small>
                      <b>{o.name}</b>
                      <div className="price">
                        <strong>{o.price}</strong>
                        {o.oldPrice && <s>{o.oldPrice}</s>}
                      </div>
                      {o.checkedAt && <em>Preço conferido em {o.checkedAt}</em>}
                    </div>
                  </Tag>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {/* ============ SEGURANÇA ============ */}
      <section className="sec">
        <div className="wrap">
          <h2 className="sec-title">O que você pode esperar do grupo</h2>

          <ul className="rules">
            {RULES.map(([t, s]) => (
              <li key={t} className="rule">
                <CheckIcon />
                <div>
                  <strong>{t}</strong>
                  <span>{s}</span>
                </div>
              </li>
            ))}
          </ul>

          {(PROOF.members || hasOwner) && (
            <div className="proof">
              {hasOwner && (
                <div className="owner">
                  <img src={PROOF.ownerPhoto} alt={PROOF.ownerName} width="60" height="60" loading="lazy" />
                  <div>
                    <strong>{PROOF.ownerName}</strong>
                    {PROOF.ownerText && <p>{PROOF.ownerText}</p>}
                  </div>
                </div>
              )}
              {PROOF.members && (
                <p className="members"><strong>{PROOF.members}</strong> já participam do grupo.</p>
              )}
            </div>
          )}
        </div>
      </section>

      {/* ============ CHAMADA FINAL + TELEGRAM ============ */}
      <section className="final">
        <div className="wrap final-in">
          <div>
            <h2>Entre no grupo e receba as ofertas direto no WhatsApp.</h2>
            <p>É grátis e você pode sair quando quiser.</p>
          </div>
          <div className="final-actions">
            <a className="btn" href={WHATSAPP_GROUP_URL} onClick={() => track("click_whatsapp_final")}>
              <WhatsIcon />
              ENTRAR NO GRUPO DO WHATSAPP
            </a>
            <p className="tg-text">Prefere o Telegram? Acompanhe nossas ofertas por lá também.</p>
            <a className="btn-outline" href={TELEGRAM_GROUP_URL} target="_blank" rel="noreferrer"
              onClick={() => track("click_telegram")}>
              Acessar o canal do Telegram
            </a>
          </div>
        </div>
      </section>

      {/* ============ RODAPÉ ============ */}
      <footer className="foot">
        <div className="wrap">
          <p>
            Preços e disponibilidade podem mudar nas lojas a qualquer momento.
            Mercado Livre e Shopee são marcas de seus respectivos proprietários.
          </p>
          <p>© 2026 JPZ Ofertas</p>
        </div>
      </footer>
    </div>
  );
}

const css = `
  html, body { margin: 0; padding: 0; background: #fff; }
  * { -webkit-tap-highlight-color: transparent; }

  .jpz {
    --ink: #101828; --text: #1F2937; --muted: #5B6472; --faint: #8A93A0;
    --line: #E3E6EA; --gray: #F4F5F7; --wa: #25D366; --wa-dark: #1AAE52; --green: #0F7A3A;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: var(--text); background: #fff; line-height: 1.5;
  }
  .jpz *, .jpz *::before, .jpz *::after { box-sizing: border-box; }
  .jpz p { margin: 0; }
  .jpz ul, .jpz ol { list-style: none; margin: 0; padding: 0; }
  .wrap { max-width: 1040px; margin: 0 auto; padding: 0 20px; }

  /* Topo */
  .top { background: var(--ink); }
  .top-in { display: flex; align-items: center; gap: 10px; height: 56px; }
  .logo { width: 32px; height: 32px; border-radius: 8px; background: #fff; color: var(--ink);
    display: grid; place-items: center; font-size: 12px; font-weight: 800; }
  .brand { color: #fff; font-size: 16px; font-weight: 700; }

  /* Botões */
  .btn { display: flex; align-items: center; justify-content: center; gap: 10px; width: 100%;
    min-height: 58px; padding: 0 20px; border-radius: 12px; background: var(--wa); color: #06210F;
    font-size: 15.5px; font-weight: 800; text-decoration: none; border-bottom: 3px solid var(--wa-dark); }
  .btn:active { transform: translateY(1px); }
  .btn-outline { display: flex; align-items: center; justify-content: center; width: 100%;
    min-height: 50px; padding: 0 20px; border-radius: 12px; border: 1.5px solid rgba(255,255,255,.35);
    color: #fff; font-size: 15px; font-weight: 700; text-decoration: none; }
  .btn:focus-visible, .btn-outline:focus-visible { outline: 3px solid #fff; outline-offset: 3px; }
  .hero .btn:focus-visible { outline-color: var(--ink); }

  /* Primeira tela */
  .hero { border-bottom: 1px solid var(--line); }
  .hero-in { display: grid; gap: 28px; padding-top: 26px; padding-bottom: 32px; }
  .title { margin: 0; color: var(--ink); font-size: clamp(28px, 7.4vw, 46px); line-height: 1.12;
    font-weight: 800; letter-spacing: -0.015em; }
  .subtitle { margin-top: 14px !important; color: var(--muted); font-size: 17px; line-height: 1.5; max-width: 520px; }
  .hero .btn { margin-top: 24px; max-width: 460px; }
  .cta-note { margin-top: 12px !important; color: var(--text); font-size: 14.5px; font-weight: 600; }

  .facts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 22px !important;
    padding-top: 18px !important; border-top: 1px solid var(--line); max-width: 460px; }
  .facts li { display: flex; flex-direction: column; gap: 2px; }
  .facts strong { color: var(--ink); font-size: 14px; line-height: 1.25; }
  .facts span { color: var(--muted); font-size: 12.5px; line-height: 1.3; }

  .stores { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .store { display: flex; flex-direction: column; justify-content: space-between; gap: 18px;
    min-height: 120px; padding: 16px; border-radius: 14px; }
  .store strong { font-size: 20px; line-height: 1.15; }
  .store span { font-size: 13px; line-height: 1.35; opacity: .85; }
  .store-ml { background: #FFE600; color: #2D3277; }
  .store-sp { background: #EE4D2D; color: #fff; }
  .shot { display: block; width: 100%; max-height: 480px; object-fit: cover; object-position: top;
    border-radius: 14px; border: 1px solid var(--line); }

  /* Seções */
  .sec { padding: 40px 0; }
  .sec-gray { background: var(--gray); }
  .sec-title { margin: 0 0 22px; color: var(--ink); font-size: 24px; line-height: 1.2; font-weight: 800; }

  .steps { display: grid; gap: 12px; }
  .step { background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: 18px;
    display: flex; flex-direction: column; gap: 12px; }
  .step-n { width: 34px; height: 34px; border-radius: 10px; background: var(--ink); color: #fff;
    display: grid; place-items: center; font-size: 16px; font-weight: 800; }
  .step p { font-size: 16px; color: var(--text); }

  .rules { display: grid; gap: 0; }
  .rule { display: flex; align-items: flex-start; gap: 12px; padding: 16px 0; border-top: 1px solid var(--line); }
  .rule svg { flex: none; margin-top: 2px; }
  .rule strong { display: block; color: var(--ink); font-size: 16px; line-height: 1.35; }
  .rule span { display: block; margin-top: 2px; color: var(--muted); font-size: 14.5px; line-height: 1.4; }

  .proof { margin-top: 12px; padding-top: 20px; border-top: 1px solid var(--line); display: grid; gap: 14px; }
  .owner { display: flex; align-items: center; gap: 14px; }
  .owner img { width: 60px; height: 60px; border-radius: 50%; object-fit: cover; flex: none; }
  .owner strong { color: var(--ink); }
  .owner p { color: var(--muted); font-size: 14.5px; }

  .offers { display: grid; gap: 12px; }
  .offer { display: flex; align-items: center; gap: 14px; padding: 12px; border: 1px solid var(--line);
    border-radius: 14px; text-decoration: none; color: inherit; }
  .offer img { width: 84px; height: 84px; object-fit: contain; border-radius: 10px; border: 1px solid var(--line); flex: none; }
  .offer small { display: block; color: var(--muted); font-size: 12px; font-weight: 700; }
  .offer b { display: block; color: var(--text); font-size: 15px; line-height: 1.25; }
  .offer .price { display: flex; align-items: baseline; gap: 8px; margin-top: 2px; }
  .offer .price strong { color: var(--ink); font-size: 20px; }
  .offer .price s { color: var(--faint); font-size: 13px; }
  .offer em { display: block; color: var(--faint); font-size: 12px; font-style: normal; }

  /* Chamada final */
  .final { background: var(--ink); color: #fff; padding: 40px 0; }
  .final-in { display: grid; gap: 24px; }
  .final h2 { margin: 0; font-size: 24px; line-height: 1.2; font-weight: 800; }
  .final p { color: rgba(255,255,255,.7); }
  .final-in > div:first-child p { margin-top: 8px; font-size: 15.5px; }
  .final-actions { display: grid; gap: 12px; }
  .tg-text { margin-top: 10px !important; font-size: 14.5px; }

  .foot { background: var(--gray); padding: 22px 0 28px; }
  .foot p { color: var(--faint); font-size: 12.5px; line-height: 1.5; }
  .foot p + p { margin-top: 8px; }

  /* Desktop */
  @media (min-width: 860px) {
    .hero-in { grid-template-columns: 1.15fr .85fr; align-items: center; gap: 56px; padding-top: 64px; padding-bottom: 64px; }
    .store { min-height: 190px; padding: 22px; }
    .store strong { font-size: 24px; }
    .stores { grid-template-columns: 1fr; }
    .store { min-height: 130px; }
    .steps { grid-template-columns: repeat(3, 1fr); gap: 16px; }
    .rules { grid-template-columns: 1fr 1fr; column-gap: 40px; }
    .offers { grid-template-columns: repeat(3, 1fr); }
    .final-in { grid-template-columns: 1.1fr .9fr; align-items: center; gap: 56px; }
    .sec { padding: 56px 0; }
    .final { padding: 56px 0; }
  }
`;