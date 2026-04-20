import { useEffect, useRef, useState } from "react";

export interface NowPlaying {
  status: "playing" | "idle";
  title?: string;
  source?: string;
  score?: number;
  score_reason?: string;
  url?: string;
  channel_id?: string;
}

export function useWebSocket(url: string) {
  const [nowPlaying, setNowPlaying] = useState<NowPlaying>({ status: "idle" });
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    function connect() {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        retryRef.current = setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (e) => {
        try {
          setNowPlaying(JSON.parse(e.data));
        } catch {}
      };
    }

    connect();
    return () => {
      wsRef.current?.close();
      clearTimeout(retryRef.current);
    };
  }, [url]);

  return { nowPlaying, connected };
}
