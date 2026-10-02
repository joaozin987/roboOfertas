
import React from "react";

export default function App() {
  const WHATSAPP_GROUP_URL =
    "https://chat.whatsapp.com/Gvs5pMsyjr80LqJtIESaMX";

  const TELEGRAM_GROUP_URL = "https://t.me/promocoesjpzz";

  const handleWhatsAppClick = () => {
    window.location.href = WHATSAPP_GROUP_URL;
  };

  return (
    <div style={styles.page}>
      <div style={styles.glowOne} />
      <div style={styles.glowTwo} />

      <main style={styles.wrapper}>
        {/* CARD PRINCIPAL */}
        <div style={styles.card}>

          {/* HEADER */}
          <header style={styles.header}>
            <div style={styles.logo}>JP</div>

            <div style={styles.brandArea}>
              <div style={styles.brand}>JPZ OFERTAS</div>
              <div style={styles.brandSub}>
                Ofertas filtradas automaticamente
              </div>
            </div>

            <div style={styles.online}>
              <span style={styles.onlineDot} />
              ONLINE
            </div>
          </header>

          {/* CONTEÚDO */}
          <section style={styles.content}>

            {/* BADGE */}
            <div style={styles.badge}>
              <span style={styles.badgeDot} />
              MERCADO LIVRE + SHOPEE
            </div>

            {/* TÍTULO */}
            <h1 style={styles.title}>
              Ofertas que
              <br />
              <span style={styles.titleAccent}>
                realmente valem a pena.
              </span>
            </h1>

            <p style={styles.description}>
              Nosso sistema monitora as lojas e filtra as oportunidades
              antes de enviar para o grupo.
            </p>

            {/* OFERTA EXEMPLO */}
            <div style={styles.offerCard}>
              <div style={styles.offerHeader}>
                <span style={styles.store}>
                  MERCADO LIVRE
                </span>

                <span style={styles.discount}>
                  74% OFF
                </span>
              </div>

              <div style={styles.productName}>
                Fritadeira Air Fryer 4L
              </div>

              <div style={styles.priceArea}>
                <span style={styles.oldPrice}>
                  R$ 389,00
                </span>

                <span style={styles.arrow}>
                  →
                </span>

                <strong style={styles.price}>
                  R$ 99,90
                </strong>
              </div>

              <div style={styles.verified}>
                <span style={styles.check}>
                  ✓
                </span>

                Oferta selecionada pelo nosso sistema
              </div>
            </div>

            {/* OFERTA SHOPEE */}
<div style={styles.offerCard}>
  <div style={styles.offerHeader}>
    <span style={styles.store}>
      SHOPEE
    </span>

    <span style={styles.discount}>
      68% OFF
    </span>
  </div>

  <div style={styles.productName}>
    Fone Bluetooth TWS Pro
  </div>

  <div style={styles.priceArea}>
    <span style={styles.oldPrice}>
      R$ 129,90
    </span>

    <span style={styles.arrow}>
      →
    </span>

    <strong style={styles.price}>
      R$ 41,90
    </strong>
  </div>

  <div style={styles.verified}>
    <span style={styles.check}>
      ✓
    </span>

    Oferta selecionada pelo nosso sistema
  </div>
</div>

            {/* COMO FUNCIONA */}
            <div style={styles.infoSection}>

              <div style={styles.infoHeader}>
                <span style={styles.infoTitle}>
                  COMO FUNCIONA
                </span>

                <span style={styles.infoLine} />
              </div>

              <div style={styles.infoGrid}>

                <div style={styles.infoItem}>
                  <div style={styles.infoIcon}>
                    🔒
                  </div>

                  <div>
                    <div style={styles.infoItemTitle}>
                      Grupo organizado
                    </div>

                    <div style={styles.infoItemText}>
                      Somente administradores enviam mensagens.
                    </div>
                  </div>
                </div>

                <div style={styles.infoItem}>
                  <div style={styles.infoIcon}>
                    ⏱
                  </div>

                  <div>
                    <div style={styles.infoItemTitle}>
                      Envio controlado
                    </div>

                    <div style={styles.infoItemText}>
                      As ofertas são enviadas em intervalos para você
                      conseguir acompanhar cada oportunidade.
                    </div>
                  </div>
                </div>

                <div style={styles.infoItem}>
                  <div style={styles.infoIcon}>
                    %
                  </div>

                  <div>
                    <div style={styles.infoItemTitle}>
                      Descontos selecionados
                    </div>

                    <div style={styles.infoItemText}>
                      Ofertas normalmente entre
                      <strong style={styles.range}>
                        {" "}46% e 81% OFF.
                      </strong>
                    </div>
                  </div>
                </div>

              </div>
            </div>

            {/* CTA */}
            <div style={styles.ctaArea}>

              <button
                type="button"
                onClick={handleWhatsAppClick}
                style={styles.primaryButton}
              >
                <span>
                  ENTRAR NO GRUPO GRATUITAMENTE
                </span>

                <span style={styles.buttonArrow}>
                  →
                </span>
              </button>

              <div style={styles.freeText}>
                Sem compromisso · Via WhatsApp
              </div>

              <a
                href={TELEGRAM_GROUP_URL}
                target="_blank"
                rel="noreferrer"
                style={styles.telegram}
              >
                Prefere Telegram?
                <span> Acessar canal →</span>
              </a>

            </div>

          </section>

          {/* FOOTER */}
          <footer style={styles.footer}>

            <div style={styles.trustItems}>

              <div style={styles.trust}>
                <span style={styles.trustIcon}>
                  ✓
                </span>
                Links oficiais das lojas
              </div>

              <div style={styles.trust}>
                <span style={styles.trustIcon}>
                  ✓
                </span>
                Robô próprio
              </div>

              <div style={styles.trust}>
                <span style={styles.trustIcon}>
                  ✓
                </span>
                Grupo gratuito
              </div>

            </div>

            <div style={styles.copyright}>
              © 2026 JPZ Ofertas
            </div>

          </footer>

        </div>
      </main>
    </div>
  );
}

const SANS =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';

const colors = {
  background: "#F4F6F8",
  white: "#FFFFFF",
  black: "#101828",
  text: "#182230",
  muted: "#667085",
  lightMuted: "#98A2B3",
  border: "#E4E7EC",
  green: "#16A34A",
  greenLight: "#ECFDF3",
  greenBorder: "#BBF7D0",
};

const styles = {
  page: {
    minHeight: "100vh",
    backgroundColor: colors.background,
    fontFamily: SANS,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "24px 16px",
    boxSizing: "border-box",
    position: "relative",
    overflow: "hidden",
  },

  glowOne: {
    position: "fixed",
    width: "450px",
    height: "450px",
    borderRadius: "50%",
    background:
      "radial-gradient(circle, rgba(34,197,94,0.08) 0%, rgba(34,197,94,0) 70%)",
    top: "-200px",
    right: "-180px",
    pointerEvents: "none",
  },

  glowTwo: {
    position: "fixed",
    width: "400px",
    height: "400px",
    borderRadius: "50%",
    background:
      "radial-gradient(circle, rgba(59,130,246,0.045) 0%, rgba(59,130,246,0) 70%)",
    bottom: "-200px",
    left: "-180px",
    pointerEvents: "none",
  },

  wrapper: {
    width: "100%",
    maxWidth: "500px",
    position: "relative",
    zIndex: 2,
  },

  card: {
    width: "100%",
    backgroundColor: colors.white,
    border: `1px solid ${colors.border}`,
    borderRadius: "28px",
    overflow: "hidden",
    boxShadow:
      "0 25px 70px rgba(16,24,40,0.08)",
  },

  header: {
    minHeight: "68px",
    padding: "0 22px",
    display: "flex",
    alignItems: "center",
    gap: "10px",
    borderBottom: `1px solid #F2F4F7`,
  },

  logo: {
    width: "35px",
    height: "35px",
    borderRadius: "10px",
    backgroundColor: colors.black,
    color: colors.white,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "12px",
    fontWeight: 900,
    letterSpacing: "-0.04em",
  },

  brandArea: {
    flex: 1,
  },

  brand: {
    color: colors.black,
    fontSize: "13px",
    fontWeight: 900,
    letterSpacing: "-0.02em",
  },

  brandSub: {
    marginTop: "3px",
    color: colors.lightMuted,
    fontSize: "8.5px",
    fontWeight: 650,
  },

  online: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    color: "#667085",
    fontSize: "8px",
    fontWeight: 800,
    letterSpacing: "0.06em",
  },

  onlineDot: {
    width: "6px",
    height: "6px",
    borderRadius: "50%",
    backgroundColor: colors.green,
    boxShadow:
      "0 0 0 3px rgba(22,163,74,0.10)",
  },

  content: {
    padding: "30px 30px 28px",
    textAlign: "center",
  },

  badge: {
    display: "inline-flex",
    alignItems: "center",
    gap: "7px",
    padding: "7px 10px",
    borderRadius: "999px",
    backgroundColor: colors.greenLight,
    border: `1px solid ${colors.greenBorder}`,
    color: "#15803D",
    fontSize: "8.5px",
    fontWeight: 850,
    letterSpacing: "0.07em",
  },

  badgeDot: {
    width: "6px",
    height: "6px",
    borderRadius: "50%",
    backgroundColor: colors.green,
  },

  title: {
    margin: "17px 0 0",
    color: colors.text,
    fontSize: "clamp(39px, 10vw, 54px)",
    lineHeight: "0.99",
    letterSpacing: "-0.065em",
    fontWeight: 900,
  },

  titleAccent: {
    color: colors.green,
  },

  description: {
    maxWidth: "390px",
    margin: "17px auto 0",
    color: colors.muted,
    fontSize: "13px",
    lineHeight: 1.55,
  },

  offerCard: {
    marginTop: "24px",
    padding: "18px",
    borderRadius: "18px",
    backgroundColor: "#FBFCFD",
    border: `1px solid ${colors.border}`,
    textAlign: "left",
  },

  offerHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },

  store: {
    color: colors.muted,
    fontSize: "8.5px",
    fontWeight: 850,
    letterSpacing: "0.08em",
  },

  discount: {
    padding: "5px 8px",
    borderRadius: "7px",
    backgroundColor: colors.greenLight,
    color: "#15803D",
    fontSize: "9px",
    fontWeight: 850,
  },

  productName: {
    marginTop: "14px",
    color: colors.text,
    fontSize: "15px",
    fontWeight: 750,
    letterSpacing: "-0.02em",
  },

  priceArea: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "center",
    gap: "8px",
    marginTop: "13px",
  },

  oldPrice: {
    color: colors.lightMuted,
    fontSize: "10px",
    textDecoration: "line-through",
  },

  arrow: {
    color: colors.lightMuted,
    fontSize: "12px",
  },

  price: {
    color: colors.text,
    fontSize: "24px",
    lineHeight: 1,
    fontWeight: 900,
    letterSpacing: "-0.045em",
  },

  verified: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "6px",
    marginTop: "14px",
    paddingTop: "12px",
    borderTop: "1px solid #EAECF0",
    color: colors.muted,
    fontSize: "9px",
    fontWeight: 650,
  },

  check: {
    width: "16px",
    height: "16px",
    borderRadius: "50%",
    backgroundColor: colors.greenLight,
    color: colors.green,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "8px",
    fontWeight: 900,
  },

  infoSection: {
    marginTop: "20px",
    padding: "18px",
    borderRadius: "18px",
    backgroundColor: "#F8FAFC",
    border: "1px solid #EAECF0",
    textAlign: "left",
  },

  infoHeader: {
    display: "flex",
    alignItems: "center",
    gap: "9px",
    marginBottom: "15px",
  },

  infoTitle: {
    color: colors.text,
    fontSize: "8.5px",
    fontWeight: 850,
    letterSpacing: "0.08em",
  },

  infoLine: {
    flex: 1,
    height: "1px",
    backgroundColor: "#E4E7EC",
  },

  infoGrid: {
    display: "flex",
    flexDirection: "column",
    gap: "13px",
  },

  infoItem: {
    display: "flex",
    alignItems: "flex-start",
    gap: "10px",
  },

  infoIcon: {
    width: "28px",
    height: "28px",
    flexShrink: 0,
    borderRadius: "9px",
    backgroundColor: colors.white,
    border: "1px solid #EAECF0",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "11px",
  },

  infoItemTitle: {
    color: colors.text,
    fontSize: "10.5px",
    fontWeight: 800,
  },

  infoItemText: {
    marginTop: "2px",
    color: colors.muted,
    fontSize: "9.5px",
    lineHeight: 1.4,
  },

  range: {
    color: colors.green,
    fontWeight: 800,
  },

  ctaArea: {
    marginTop: "20px",
  },

  primaryButton: {
    width: "100%",
    height: "55px",
    borderRadius: "14px",
    backgroundColor: colors.black,
    color: colors.white,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "11px",
    fontSize: "12px",
    fontWeight: 900,
    letterSpacing: "0.015em",
    cursor: "pointer",
    boxShadow:
      "0 12px 24px rgba(16,24,40,0.15)",
  },

  buttonArrow: {
    fontSize: "17px",
    fontWeight: 400,
  },

  freeText: {
    marginTop: "8px",
    color: colors.lightMuted,
    fontSize: "9px",
    fontWeight: 600,
  },

  telegram: {
    display: "inline-block",
    marginTop: "18px",
    color: colors.muted,
    fontSize: "10.5px",
    fontWeight: 650,
    textDecoration: "none",
  },

  footer: {
    padding: "15px 22px 20px",
    borderTop: "1px solid #F2F4F7",
  },

  trustItems: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "13px",
  },

  trust: {
    display: "flex",
    alignItems: "center",
    gap: "5px",
    color: "#667085",
    fontSize: "8.5px",
    fontWeight: 650,
  },

  trustIcon: {
    width: "15px",
    height: "15px",
    borderRadius: "50%",
    backgroundColor: "#F2F4F7",
    color: "#475467",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "7px",
    fontWeight: 900,
  },

  copyright: {
    marginTop: "12px",
    textAlign: "center",
    color: "#B0B7C3",
    fontSize: "8px",
  },
};