import { useEffect, useRef, useState } from "react";
import type { NowPlaying } from "../hooks/useWebSocket";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

interface Props {
  nowPlaying: NowPlaying;
  companyName: string;
}

export default function ImpactPanel({ nowPlaying, companyName }: Props) {
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const prevArticleUrl = useRef("");

  // Close and clear when article changes
  useEffect(() => {
    if (nowPlaying.url && nowPlaying.url !== prevArticleUrl.current) {
      prevArticleUrl.current = nowPlaying.url;
      setOpen(false);
      setContent("");
    }
  }, [nowPlaying.url]);

  const isPlaying = nowPlaying.status === "playing";

  const analyze = async () => {
    if (loading) return;
    setOpen(true);
    setContent("");
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/analyze-impact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const text = line.slice(6);
          if (text === "[DONE]") break;
          setContent((c) => c + text.replace(/\\n/g, "\n"));
        }
      }
    } catch (e) {
      setContent(`分析出错：${e}`);
    } finally {
      setLoading(false);
    }
  };

  if (!isPlaying) return null;

  return (
    <div style={styles.wrapper}>
      <button
        style={{ ...styles.triggerBtn, opacity: loading ? 0.6 : 1 }}
        onClick={open && content ? () => setOpen(!open) : analyze}
        disabled={loading}
        title={`分析对${companyName}的业务影响与合作机会`}
      >
        💼 {loading ? "分析中…" : open && content ? (open ? "收起分析" : "展开分析") : `对${companyName}的影响`}
      </button>

      {open && (
        <div style={styles.panel}>
          {loading && !content && (
            <div style={styles.skeleton}>
              <div style={styles.skRow} />
              <div style={{ ...styles.skRow, width: "80%" }} />
              <div style={{ ...styles.skRow, width: "60%", marginTop: 12 }} />
              <div style={styles.skRow} />
            </div>
          )}
          {content && (
            <div style={styles.markdown}>
              {renderMarkdown(content, companyName)}
            </div>
          )}
          {loading && content && (
            <span style={styles.cursor}>▋</span>
          )}
        </div>
      )}

      <style>{`
        @keyframes shimmer {
          0% { opacity: 0.4; } 50% { opacity: 0.8; } 100% { opacity: 0.4; }
        }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
      `}</style>
    </div>
  );
}

/** Minimal markdown renderer: ## headings + • bullets + plain text */
function renderMarkdown(text: string, company: string) {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];
  let key = 0;

  for (const line of lines) {
    if (line.startsWith("## ")) {
      const heading = line.slice(3).trim();
      const isImpact = heading.includes("影响");
      elements.push(
        <div key={key++} style={{ ...styles.heading, color: isImpact ? "var(--yellow)" : "var(--accent)" }}>
          {isImpact ? "📊 " : "🤝 "}{heading}
        </div>
      );
    } else if (line.startsWith("• ") || line.startsWith("- ")) {
      elements.push(
        <div key={key++} style={styles.bullet}>
          <span style={styles.dot}>•</span>
          <span>{line.slice(2)}</span>
        </div>
      );
    } else if (line.trim()) {
      // Check for inline risk/positive markers
      const styled = line
        .replace(/🟢/g, "🟢")
        .replace(/🔴/g, "🔴");
      elements.push(<p key={key++} style={styles.para}>{styled}</p>);
    }
  }
  return elements;
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  triggerBtn: {
    alignSelf: "flex-start",
    fontSize: 12,
    fontWeight: 600,
    color: "var(--accent2)",
    background: "rgba(99,102,241,0.08)",
    border: "1px solid rgba(99,102,241,0.3)",
    borderRadius: 8,
    padding: "5px 12px",
    cursor: "pointer",
    transition: "opacity 0.2s",
    letterSpacing: 0.3,
  },
  panel: {
    background: "var(--surface2)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: "14px 16px",
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  skeleton: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  skRow: {
    height: 12,
    borderRadius: 4,
    background: "var(--border)",
    width: "100%",
    animation: "shimmer 1.2s ease-in-out infinite",
  },
  markdown: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
    fontSize: 12,
    lineHeight: 1.7,
    color: "var(--text)",
  },
  heading: {
    fontWeight: 700,
    fontSize: 12,
    letterSpacing: 0.5,
    marginTop: 6,
    marginBottom: 2,
  },
  bullet: {
    display: "flex",
    gap: 6,
    alignItems: "flex-start",
    color: "var(--text2)",
  },
  dot: {
    color: "var(--accent)",
    flexShrink: 0,
    marginTop: 1,
  },
  para: {
    color: "var(--text2)",
    margin: 0,
  },
  cursor: {
    display: "inline-block",
    color: "var(--accent2)",
    animation: "blink 0.8s step-end infinite",
    fontSize: 14,
  },
};
