import { useWebSocket } from "./hooks/useWebSocket";
import { useChannels, useQueue } from "./hooks/useApi";
import { useSettings } from "./hooks/useSettings";
import Player from "./components/Player";
import Queue from "./components/Queue";
import ChannelEditor from "./components/ChannelEditor";
import History from "./components/History";
import AskPanel from "./components/AskPanel";
import SettingsPanel from "./components/SettingsPanel";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws";

export default function App() {
  const { nowPlaying, connected } = useWebSocket(WS_URL);
  const { channels, createChannel, deleteChannel } = useChannels();
  const queue = useQueue();
  const { settings, updateCompanyName } = useSettings();

  return (
    <div style={styles.root}>
      <style>{`@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }`}</style>
      <div style={styles.layout}>
        {/* Left column: player + ask panel + queue + history */}
        <div style={styles.left}>
          <Player nowPlaying={nowPlaying} connected={connected} companyName={settings.company_name} />
          <AskPanel nowPlaying={nowPlaying} />
          <Queue items={queue} />
          <History />
        </div>

        {/* Right column: settings + channel editor */}
        <div style={styles.right}>
          <SettingsPanel settings={settings} onUpdate={updateCompanyName} />
          <ChannelEditor
            channels={channels}
            onCreate={async (data) => { await createChannel(data); }}
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
