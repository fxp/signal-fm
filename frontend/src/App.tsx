import { useWebSocket } from "./hooks/useWebSocket";
import { useChannels, useQueue } from "./hooks/useApi";
import Player from "./components/Player";
import Queue from "./components/Queue";
import ChannelEditor from "./components/ChannelEditor";
import History from "./components/History";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws";

export default function App() {
  const { nowPlaying, connected } = useWebSocket(WS_URL);
  const { channels, createChannel, deleteChannel } = useChannels();
  const queue = useQueue();

  return (
    <div style={styles.root}>
      <div style={styles.layout}>
        {/* Left column: player + queue + history */}
        <div style={styles.left}>
          <Player nowPlaying={nowPlaying} connected={connected} />
          <Queue items={queue} />
          <History />
        </div>

        {/* Right column: channel editor */}
        <div style={styles.right}>
          <ChannelEditor
            channels={channels}
            onCreate={createChannel}
            onDelete={deleteChannel}
          />
        </div>
      </div>

      <footer style={styles.footer}>
        Signal FM · AI-Powered Domain Radio · {connected ? "● 已连接" : "○ 连接中…"}
      </footer>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  root: { minHeight: "100vh", display: "flex", flexDirection: "column", padding: "24px", gap: 24, maxWidth: 1100, margin: "0 auto" },
  layout: { display: "grid", gridTemplateColumns: "1fr 1.2fr", gap: 20, alignItems: "start" },
  left: { display: "flex", flexDirection: "column", gap: 16 },
  right: { display: "flex", flexDirection: "column", gap: 16 },
  footer: { textAlign: "center", fontSize: 11, color: "var(--text3)", letterSpacing: 1, paddingTop: 8 },
};
