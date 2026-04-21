import { useEffect, useRef, useState } from "react";
import type { NowPlaying } from "../hooks/useWebSocket";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

interface Props {
  nowPlaying: NowPlaying;
  connected: boolean;
}

export default function Player({ nowPlaying, connected }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const prevAudioUrl = useRef<string>("");

  // Auto-load and play when audio_url changes from WebSocket
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !nowPlaying.audio_url) return;
    if (nowPlaying.audio_url === prevAudioUrl.current) return;

    prevAudioUrl.current = nowPlaying.audio_url;
    audio.src = `${API_BASE}${nowPlaying.audio_url}`;
    audio.load();
    audio.play().then(() => setPlaying(true)).catch(() => {});
  }, [nowPlaying.audio_url]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onEnded = () => setPlaying(false);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("ended", onEnded);
    return () => {
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("ended", onEnded);
    };
  }, []);

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) audio.pause();
    else audio.play().catch(() => {});
  };

  const skip = async () => {
    await fetch(`${API_BASE}/api/skip`, { method: "POST" });
  };

  const scoreColor = (score?: number) => {
    if (!score) return "var(--text3)";
    if (score >= 90) return "var(--red)";
    if (score >= 75) return "var(--yellow)";
    return "var(--green)";
  };

  const isPlaying = nowPlaying.status === "playing";

  return (
    <div style={styles.container}>
      <div style={styles.brand}>
        <div style={styles.logo}><span style={styles.logoText}>📻</span></div>
        <div>
          <div style={styles.stationName}>SIGNAL FM</div>
          <div style={styles.tagline}>AI-Powered Domain Radio</div>
        </div>
        <div style={{ ...styles.dot, background: connected ? "var(--green)" : "var(--text3)" }} />
      </div>

      <div style={styles.nowPlaying}>
        {isPlaying ? (
          <>
            <div style={styles.nowLabel}>ON AIR</div>
            <div style={styles.title}>{nowPlaying.title}</div>
            <div style={styles.meta}>
              <span style={styles.source}>来源：{nowPlaying.source}</span>
              {nowPlaying.score && (
                <span style={{ ...styles.score, color: scoreColor(nowPlaying.score) }}>
                  评分 {nowPlaying.score}
                </span>
              )}
            </div>
            {nowPlaying.score_reason && (
              <div style={styles.reason}>{nowPlaying.score_reason}</div>
            )}
            {nowPlaying.url && (
              <a href={nowPlaying.url} target="_blank" rel="noreferrer" style={styles.link}>
                查看原文 →
              </a>
            )}
          </>
        ) : (
          <div style={styles.idle}>
            <div style={styles.idleIcon}>〜</div>
            <div style={styles.idleText}>等待播报中…</div>
            <div style={styles.idleHint}>请添加频道并配置数据源</div>
          </div>
        )}
      </div>

      <div style={styles.controls}>
        <audio ref={audioRef} />
        <button
          style={{ ...styles.playBtn, opacity: isPlaying ? 1 : 0.4 }}
          onClick={togglePlay}
          disabled={!isPlaying}
          title={playing ? "暂停" : "播放"}
        >
          {playing ? "⏸" : "▶"}
        </button>
        <button
          style={{ ...styles.skipBtn, opacity: isPlaying ? 1 : 0.3 }}
          onClick={skip}
          disabled={!isPlaying}
          title="跳过"
        >
          ⏭
        </button>
        <div style={styles.waveform}>
          {playing && isPlaying && (
            [1, 2, 3, 4, 5].map((i) => (
              <div key={i} style={{ ...styles.bar, animationDelay: `${i * 0.1}s` }} />
            ))
          )}
        </div>
        {!isPlaying && (
          <span style={{ fontSize: 12, color: "var(--text3)" }}>等待内容上播…</span>
        )}
      </div>

      <style>{`
        @keyframes wave {
          0%, 100% { height: 6px; }
          50% { height: 20px; }
        }
      `}</style>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 16, padding: "24px", display: "flex", flexDirection: "column", gap: 20 },
  brand: { display: "flex", alignItems: "center", gap: 12 },
  logo: { width: 44, height: 44, background: "linear-gradient(135deg, var(--accent), var(--accent2))", borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22 },
  logoText: { lineHeight: 1 },
  stationName: { fontWeight: 700, fontSize: 18, letterSpacing: 2 },
  tagline: { fontSize: 11, color: "var(--text2)", letterSpacing: 1 },
  dot: { width: 8, height: 8, borderRadius: "50%", marginLeft: "auto", flexShrink: 0 },
  nowPlaying: { background: "var(--surface2)", borderRadius: 12, padding: "20px", minHeight: 120, display: "flex", flexDirection: "column", gap: 8 },
  nowLabel: { fontSize: 10, fontWeight: 700, letterSpacing: 2, color: "var(--accent2)", marginBottom: 4 },
  title: { fontSize: 16, fontWeight: 600, lineHeight: 1.4 },
  meta: { display: "flex", gap: 16, marginTop: 4 },
  source: { fontSize: 12, color: "var(--text2)" },
  score: { fontSize: 12, fontWeight: 700 },
  reason: { fontSize: 12, color: "var(--text2)", fontStyle: "italic", marginTop: 4 },
  link: { fontSize: 12, marginTop: 4 },
  idle: { display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", flex: 1, gap: 8 },
  idleIcon: { fontSize: 32, color: "var(--text3)" },
  idleText: { color: "var(--text2)", fontWeight: 500 },
  idleHint: { fontSize: 12, color: "var(--text3)" },
  controls: { display: "flex", alignItems: "center", gap: 12 },
  playBtn: { width: 48, height: 48, borderRadius: "50%", background: "linear-gradient(135deg, var(--accent), var(--accent2))", fontSize: 20, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "opacity 0.2s", cursor: "pointer" },
  skipBtn: { width: 36, height: 36, borderRadius: "50%", background: "var(--surface2)", border: "1px solid var(--border)", fontSize: 16, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "opacity 0.2s", cursor: "pointer" },
  waveform: { display: "flex", alignItems: "center", gap: 3, height: 24 },
  bar: { width: 3, height: 6, borderRadius: 2, background: "var(--accent)", animation: "wave 0.8s ease-in-out infinite" },
};
