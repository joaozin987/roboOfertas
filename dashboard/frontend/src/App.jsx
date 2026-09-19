import React from "react";

export default function App() {
  // CONFIGURAÇÃO DOS SEUS LINKS
  const WHATSAPP_GROUP_URL = "https://chat.whatsapp.com/Gvs5pMsyjr80LqJtIESaMX";
  const TELEGRAM_GROUP_URL = "https://t.me/promocoesjpzz";

  const handleWhatsAppClick = () => {
    window.location.href = WHATSAPP_GROUP_URL;
  };

  return (
    <div style={styles.body}>
      <main style={styles.container}>
        {/* Cabeçalho / Identidade do Robô */}
        <header style={styles.header}>
          <div style={styles.avatarWrapper}>
            <span style={styles.avatarIcon}>🤖</span>
          </div>
          <h1 style={styles.title}>Jpz Ofertas</h1>
          <p style={styles.subtitle}>
            Varredura automática das maiores liquidações e queimas de estoque do <strong>Mercado Livre</strong>.
          </p>
        </header>

        {/* Pilares de Confiança (Mata as objeções na hora) */}
        <section style={styles.trustGrid}>
          <div style={styles.trustItem}>
            <span style={styles.trustIcon}>🔒</span>
            <div>
              <strong>100% Silencioso</strong>
              <p style={styles.trustSub}>Apenas os admins postam</p>
            </div>
          </div>
          <div style={styles.trustItem}>
            <span style={styles.trustIcon}>⚡</span>
            <div>
              <strong>Achados Full</strong>
              <p style={styles.trustSub}>Promoções exclusivas</p>
            </div>
          </div>
          <div style={styles.trustItem}>
            <span style={styles.trustIcon}>🏷️</span>
            <div>
              <strong>Descontos Reais</strong>
              <p style={styles.trustSub}>Até 81% OFF testados</p>
            </div>
          </div>
          <div style={styles.trustItem}>
            <span style={styles.trustIcon}>🛡️</span>
            <div>
              <strong>Links Seguros</strong>
              <p style={styles.trustSub}>Direto no app oficial</p>
            </div>
          </div>
        </section>

        {/* Botão de Ação Principal (CTA) */}
        <div style={styles.ctaWrapper}>
          <button 
            type="button" 
            onClick={handleWhatsAppClick} 
            style={styles.btnPrimary}
          >
            <span style={styles.btnIcon}>💬</span>
            <div style={styles.btnTextWrapper}>
              <span style={styles.btnTitle}>ENTRAR NO GRUPO  (WHATSAPP)</span>
              <span style={styles.btnSub}>Acesso gratuito • Vagas abertas</span>
            </div>
          </button>
        </div>

        {/* Prova Visual: Exemplos de Achadinhos Recentes */}
        <section style={styles.previewSection}>
          <p style={styles.previewTitle}>Exemplos que o bot encontrou hoje:</p>
          
          <div style={styles.cardOffer}>
            <div style={styles.offerBadge}>-72% OFF</div>
            <div style={styles.offerInfo}>
              <strong>Fone Sem Fio Bluetooth TWS</strong>
              <div style={styles.priceRow}>
                <span style={styles.oldPrice}>De R$ 149,90</span>
                <span style={styles.newPrice}>Por R$ 41,90</span>
              </div>
            </div>
          </div>

          <div style={styles.cardOffer}>
            <div style={styles.offerBadge}>-48% OFF</div>
            <div style={styles.offerInfo}>
              <strong>Fritadeira Air Fryer 4L Inox</strong>
              <div style={styles.priceRow}>
                <span style={styles.oldPrice}>De R$ 389,00</span>
                <span style={styles.newPrice}>Por R$ 199,90</span>
              </div>
            </div>
          </div>

            <div style={styles.cardOffer}>
            <div style={styles.offerBadge}>-71% OFF</div>
            <div style={styles.offerInfo}>
              <strong>Tênis Puma Caven Suede</strong>
              <div style={styles.priceRow}>
                <span style={styles.oldPrice}>De R$ 333,00</span>
                <span style={styles.newPrice}>Por R$ 96,90</span>
              </div>
            </div>
          </div>
        </section>

        {/* Rodapé / Link Discreto do Telegram */}
        <footer style={styles.footer}>
          <p style={styles.footerNote}>Prefere acompanhar por outro canal?</p>
          <a href={TELEGRAM_GROUP_URL} target="_blank" rel="noreferrer" style={styles.telegramLink}>
            Acessar canal no Telegram ↗
          </a>
          <small style={styles.copyright}>© 2026 Jpz Ofertas • Todos os direitos reservados</small>
        </footer>
      </main>
    </div>
  );
}

// Estilos limpos, ultraleves e responsivos (Mobile First)
const styles = {
  body: {
    minHeight: "100vh",
    backgroundColor: "#0b1320",
    color: "#f8fafc",
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    display: "flex",
    justifyContent: "center",
    alignItems: "flex-start",
    padding: "20px 16px",
    boxSizing: "border-box"
  },
  container: {
    width: "100%",
    maxWidth: "420px",
    display: "flex",
    flexDirection: "column",
    gap: "20px",
    paddingTop: "10px"
  },
  header: {
    textAlign: "center",
    display: "flex",
    flexDirection: "column",
    alignItems: "center"
  },
  avatarWrapper: {
    width: "74px",
    height: "74px",
    borderRadius: "50%",
    backgroundColor: "#162235",
    border: "2px solid #22c55e",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: "12px",
    boxShadow: "0 0 20px rgba(34, 197, 94, 0.25)"
  },
  avatarIcon: {
    fontSize: "36px"
  },
  title: {
    fontSize: "24px",
    fontWeight: "800",
    margin: "0 0 6px 0",
    letterSpacing: "-0.5px"
  },
  subtitle: {
    fontSize: "14px",
    color: "#94a3b8",
    margin: 0,
    lineHeight: "1.4"
  },
  trustGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "10px",
    backgroundColor: "#111c2e",
    padding: "14px",
    borderRadius: "14px",
    border: "1px solid #1e293b"
  },
  trustItem: {
    display: "flex",
    alignItems: "center",
    gap: "8px"
  },
  trustIcon: {
    fontSize: "20px"
  },
  trustSub: {
    fontSize: "11px",
    color: "#64748b",
    margin: 0
  },
  ctaWrapper: {
    display: "flex",
    flexDirection: "column",
    gap: "8px"
  },
  btnPrimary: {
    width: "100%",
    backgroundColor: "#22c55e",
    color: "#ffffff",
    border: "none",
    borderRadius: "14px",
    padding: "16px 20px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "12px",
    cursor: "pointer",
    boxShadow: "0 8px 24px rgba(34, 197, 94, 0.4)",
    transition: "transform 0.1s ease",
    boxSizing: "border-box"
  },
  btnIcon: {
    fontSize: "28px"
  },
  btnTextWrapper: {
    display: "flex",
    flexDirection: "column",
    textAlign: "left"
  },
  btnTitle: {
    fontSize: "15px",
    fontWeight: "800",
    letterSpacing: "0.2px"
  },
  btnSub: {
    fontSize: "12px",
    opacity: 0.9,
    fontWeight: "500"
  },
  previewSection: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    backgroundColor: "#111c2e",
    padding: "14px",
    borderRadius: "14px",
    border: "1px solid #1e293b"
  },
  previewTitle: {
    fontSize: "12px",
    fontWeight: "700",
    color: "#94a3b8",
    margin: 0,
    textTransform: "uppercase",
    letterSpacing: "0.5px"
  },
  cardOffer: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "#162235",
    padding: "10px 12px",
    borderRadius: "10px",
    border: "1px solid #1e293b"
  },
  offerBadge: {
    backgroundColor: "#ef4444",
    color: "#ffffff",
    fontSize: "12px",
    fontWeight: "800",
    padding: "4px 6px",
    borderRadius: "6px"
  },
  offerInfo: {
    display: "flex",
    flexDirection: "column",
    textAlign: "right"
  },
  priceRow: {
    display: "flex",
    gap: "6px",
    justifyContent: "flex-end",
    alignItems: "baseline"
  },
  oldPrice: {
    fontSize: "11px",
    color: "#64748b",
    textDecoration: "line-through"
  },
  newPrice: {
    fontSize: "13px",
    color: "#22c55e",
    fontWeight: "700"
  },
  footer: {
    textAlign: "center",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "6px",
    marginTop: "8px"
  },
  footerNote: {
    fontSize: "12px",
    color: "#64748b",
    margin: 0
  },
  telegramLink: {
    fontSize: "13px",
    color: "#38bdf8",
    textDecoration: "none",
    fontWeight: "600"
  },
  copyright: {
    fontSize: "10px",
    color: "#475569",
    marginTop: "12px"
  }
};