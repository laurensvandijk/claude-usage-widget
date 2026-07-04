// Claude usage widget for Übersicht.
// Shows session / weekly / Fable limits, mirroring the `claude /usage` screen.
// Data comes from claude-usage.py (reads the Claude Code OAuth token from Keychain).

export const refreshFrequency = 300000; // 5 min — usage changes slowly; avoids rate limits

// Übersicht runs `command` with the widgets directory as the working directory.
// install.sh links this folder in as "claude-usage", so this path is portable across machines.
export const command = "python3 claude-usage/claude-usage.py";

export const className = `
  top: 24px;
  right: 24px;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif;
  color: #ede9e3;
  -webkit-font-smoothing: antialiased;
`;

const COLORS = {
  normal: "#d97757", // Claude coral
  warning: "#e0a458",
  danger: "#dc6a5b",
};

function colorFor(row) {
  if (!row) return COLORS.normal;
  if (row.pct >= 90 || row.severity === "exceeded") return COLORS.danger;
  if (row.pct >= 75 || row.severity === "warning") return COLORS.warning;
  return COLORS.normal;
}

function resetsIn(iso) {
  if (!iso) return "";
  const ms = new Date(iso).getTime() - Date.now();
  if (isNaN(ms) || ms <= 0) return "resetting";
  const mins = Math.round(ms / 60000);
  if (mins < 60) return `resets in ${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `resets in ${hrs}h ${mins % 60}m`;
  const days = Math.floor(hrs / 24);
  return `resets in ${days}d ${hrs % 24}h`;
}

const card = {
  width: 236,
  padding: "16px 18px",
  background: "rgba(28,25,23,0.92)",
  backdropFilter: "blur(18px)",
  WebkitBackdropFilter: "blur(18px)",
  borderRadius: 16,
  border: "1px solid rgba(255,255,255,0.08)",
  boxShadow: "0 8px 32px rgba(0,0,0,0.35)",
};

function Bar({ label, row }) {
  const pct = row ? row.pct : null;
  const color = colorFor(row);
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between",
                    fontSize: 12, marginBottom: 5 }}>
        <span style={{ color: "#d6d0c8", fontWeight: 500 }}>{label}</span>
        <span style={{ color: "#ede9e3", fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
          {pct == null ? "—" : `${pct}%`}
        </span>
      </div>
      <div style={{ height: 6, borderRadius: 3, background: "rgba(255,255,255,0.09)",
                    overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${Math.min(pct || 0, 100)}%`,
                      background: color, borderRadius: 3,
                      transition: "width 0.4s ease" }} />
      </div>
      {row && row.resets_at && (
        <div style={{ fontSize: 10, color: "#8f8a82", marginTop: 4 }}>
          {resetsIn(row.resets_at)}
        </div>
      )}
    </div>
  );
}

export const render = ({ output }) => {
  let data;
  try {
    data = JSON.parse(output);
  } catch (e) {
    data = null;
  }

  if (!data || !data.ok) {
    const code = data && data.error;
    let msg;
    if (code === "no-credential") msg = "no Claude Code login — run `claude`";
    else if (code === "expired" || code === "http-401" || code === "http-403") msg = "session expired — run `claude` to refresh";
    else if (code === "http-429") msg = "rate limited — retrying shortly";
    else if (code) msg = `error: ${code}`;
    else msg = "loading…";
    return (
      <div style={card}>
        <Header />
        <div style={{ fontSize: 12, color: "#a8a29e", marginTop: 4 }}>{msg}</div>
      </div>
    );
  }

  return (
    <div style={card}>
      <Header stale={data.stale} />
      <Bar label="Session" row={data.session} />
      <Bar label="Weekly" row={data.weekly} />
      {data.fable && <Bar label={data.fable_label || "Fable"} row={data.fable} />}
    </div>
  );
};

function Header({ stale } = {}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 14 }}>
      <div style={{ width: 8, height: 8, borderRadius: 2,
                    background: stale ? "#8f8a82" : "#d97757" }} />
      <span style={{ fontSize: 11, letterSpacing: 0.8, textTransform: "uppercase",
                     color: "#a8a29e", fontWeight: 600 }}>
        Claude usage{stale ? " · stale" : ""}
      </span>
    </div>
  );
}
