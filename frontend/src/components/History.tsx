import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

interface HistoryItem {
  title: string;
  source: string;
  score: number;
  url: string;
  channel_id: string;
  audio_url: string;
}

const scoreColor = (score: number) => {
  if (score >= 90) return "var(--red)";
  if (score >= 75) return "var(--yellow)";
  return "var(--green)";
};

export default function History() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [playing, setPlaying] = useState<string | null>(null);
  const [ratings, setRatings] = useState<Record<string, 1 | -1>>({});
  const audioRef = { current: null as HTMLAudioElement | null };

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/history`);
        setItems(await res.json());
      } catch {}
    };
    poll();
    const id = setInterval(poll, 10000);
    return () => clearInterval(id);
  }, []);

  const replayItem = (item: HistoryItem) => {
    const audio = new Audio(`${API_BASE}${item.audio_url}`);
    audioRef.current = audio;
    audio.play();
    setPlaying(item.audio_url);
    audio.onended = () => setPlaying(null);
  };

  const rate = async (item: HistoryItem, rating: 1 | -1) => {
    const key = item.url || item.title;
    if (ratings[key]) return; // already rated
    setRatings((r) => ({ ...r, [key]: rating }));
    try {
      await fetch(`${API_BASE}/api/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: item.url,
          title: item.title,
          channel_id: item.channel_id,
          score: item.score,
          rating,
        }),
      });
    } catch {}
  };

  if (items.length === 0) return null;

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        已播历史
        <span style={styles.count}>{items.length}</span>
      </div>
      <div style={styles.list}>
        {items.slice(0, 10).map((item, i) => {
          const key = item.url || item.title;
          const myRating = ratings[key];
          return (
            <div key={i} style={styles.item}>
              <div style={{ ...styles.scoreBar, background: scoreColor(item.score) }} />
              <div style={styles.content}>
                <div style={styles.title}>{item.title}</div>
                <div style={styles.meta}>
                  <span>{item.source}</span>
                  <span style={{ color: scoreColor(item.score), fontWeight: 700 }}>{item.score}</span>
                </div>
              </div>
              <div style={styles.actions}>
                <button
                  style={{
                    ...styles.rateBtn,
                    color: myRating === 1 ? "var(--green)" : "var(--text3)",
                    opacity: myRating && myRating !== 1 ? 0.3 : 1,
                  }}
                  onClick={() => rate(item, 1)}
                  disabled={!!myRating}
                  title="有价值"
                >
                  👍
                </button>
                <button
                  style={{
                    ...styles.rateBtn,
                    color: myRating === -1 ? "var(--red)" : "var(--text3)",
                    opacity: myRating && myRating !== -1 ? 0.3 : 1,
                  }}
                  onClick={() => rate(item, -1)}
                  disabled={!!myRating}
                  title="没价值"
                >
                  👎
                </button>
                <button
                  style={{ ...styles.replayBtn, opacity: playing === item.audio_url ? 0.5 : 1 }}
                  onClick={() => replayItem(item)}
                  disabled={playing === item.audio_url}
                  title="重播"
                >
                  ▶
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 16, padding: "20px", display: "flex", flexDirection: "column", gap: 12 },
  header: { fontWeight: 700, fontSize: 13, letterSpacing: 1, color: "var(--text2)", textTransform: "uppercase", display: "flex", alignItems: "center", gap: 8 },
  count: { background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 10, padding: "1px 8px", fontSize: 11, color: "var(--text2)" },
  list: { display: "flex", flexDirection: "column", gap: 6, maxHeight: 280, overflowY: "auto" },
  item: { display: "flex", alignItems: "center", gap: 8 },
  scoreBar: { width: 3, height: 32, borderRadius: 2, flexShrink: 0 },
  content: { flex: 1, minWidth: 0 },
  title: { fontSize: 12, fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
  meta: { display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text2)", marginTop: 2 },
  actions: { display: "flex", alignItems: "center", gap: 4, flexShrink: 0 },
  rateBtn: { fontSize: 13, padding: "2px 3px", cursor: "pointer", transition: "opacity 0.15s", background: "none", border: "none" },
  replayBtn: { fontSize: 12, color: "var(--accent)", padding: "4px 6px", border: "1px solid var(--border)", borderRadius: 6, background: "var(--surface2)", cursor: "pointer", flexShrink: 0 },
};
