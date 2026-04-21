import { useEffect, useRef, useState } from "react";
import type { NowPlaying } from "../hooks/useWebSocket";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

interface Message {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

interface Props {
  nowPlaying: NowPlaying;
}

export default function AskPanel({ nowPlaying }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const prevArticleUrl = useRef<string>("");

  // Clear chat history when article changes
  useEffect(() => {
    if (nowPlaying.url && nowPlaying.url !== prevArticleUrl.current) {
      prevArticleUrl.current = nowPlaying.url;
      setMessages([]);
    }
  }, [nowPlaying.url]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const isPlaying = nowPlaying.status === "playing";

  const send = async () => {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setLoading(true);

    const userMsg: Message = { role: "user", content: q };
    setMessages((prev) => [...prev, userMsg, { role: "assistant", content: "", streaming: true }]);

    try {
      const res = await fetch(`${API_BASE}/api/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
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
          const chunk = text.replace(/\\n/g, "\n");
          setMessages((prev) => {
            const copy = [...prev];
            const last = copy[copy.length - 1];
            if (last?.role === "assistant") {
              copy[copy.length - 1] = { ...last, content: last.content + chunk };
            }
            return copy;
          });
        }
      }
    } catch (e) {
      setMessages((prev) => {
        const copy = [...prev];
        const last = copy[copy.length - 1];
        if (last?.role === "assistant") {
          copy[copy.length - 1] = { ...last, content: `请求失败：${e}`, streaming: false };
        }
        return copy;
      });
    } finally {
      setMessages((prev) => {
        const copy = [...prev];
        const last = copy[copy.length - 1];
        if (last?.role === "assistant") {
          copy[copy.length - 1] = { ...last, streaming: false };
        }
        return copy;
      });
      setLoading(false);
    }
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.icon}>💬</span>
        追问当前内容
        {!isPlaying && <span style={styles.hint}>（等待播报中）</span>}
      </div>

      {messages.length > 0 && (
        <div style={styles.messages}>
          {messages.map((msg, i) => (
            <div
              key={i}
              style={{
                ...styles.bubble,
                ...(msg.role === "user" ? styles.userBubble : styles.aiBubble),
              }}
            >
              {msg.content || (msg.streaming ? <span style={styles.cursor}>▋</span> : "")}
              {msg.streaming && msg.content && <span style={styles.cursor}>▋</span>}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}

      {messages.length === 0 && isPlaying && (
        <div style={styles.placeholder}>
          对「{nowPlaying.title?.slice(0, 20)}…」有疑问？直接问我
        </div>
      )}

      <div style={styles.inputRow}>
        <input
          style={{ ...styles.input, opacity: isPlaying ? 1 : 0.5 }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder={isPlaying ? "输入问题，按 Enter 发送…" : "等待播报中…"}
          disabled={!isPlaying || loading}
        />
        <button
          style={{ ...styles.sendBtn, opacity: isPlaying && input.trim() ? 1 : 0.4 }}
          onClick={send}
          disabled={!isPlaying || loading || !input.trim()}
        >
          {loading ? "…" : "↑"}
        </button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 16,
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  header: {
    fontWeight: 700,
    fontSize: 13,
    letterSpacing: 1,
    color: "var(--text2)",
    textTransform: "uppercase",
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  icon: { fontSize: 14 },
  hint: { fontSize: 11, fontWeight: 400, color: "var(--text3)", marginLeft: 4, textTransform: "none", letterSpacing: 0 },
  messages: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
    maxHeight: 280,
    overflowY: "auto",
    padding: "4px 0",
  },
  bubble: {
    borderRadius: 10,
    padding: "8px 12px",
    fontSize: 13,
    lineHeight: 1.6,
    maxWidth: "88%",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  },
  userBubble: {
    background: "linear-gradient(135deg, var(--accent), var(--accent2))",
    color: "#fff",
    alignSelf: "flex-end",
  },
  aiBubble: {
    background: "var(--surface2)",
    color: "var(--text)",
    alignSelf: "flex-start",
    border: "1px solid var(--border)",
  },
  cursor: {
    display: "inline-block",
    animation: "blink 0.8s step-end infinite",
    color: "var(--accent)",
  },
  placeholder: {
    fontSize: 12,
    color: "var(--text3)",
    fontStyle: "italic",
    padding: "4px 0",
  },
  inputRow: {
    display: "flex",
    gap: 8,
    alignItems: "center",
  },
  input: {
    flex: 1,
    background: "var(--bg)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: "8px 10px",
    color: "var(--text)",
    fontSize: 13,
    outline: "none",
  },
  sendBtn: {
    width: 36,
    height: 36,
    borderRadius: "50%",
    background: "linear-gradient(135deg, var(--accent), var(--accent2))",
    color: "#fff",
    fontWeight: 700,
    fontSize: 16,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    cursor: "pointer",
    transition: "opacity 0.2s",
  },
};
