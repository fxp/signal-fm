import { useEffect, useState, useCallback } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export interface Channel {
  id: string;
  name: string;
  topic: string;
  rss_feeds: string[];
  keywords: string[];
  crawl_urls: string[];
  preference: string;
  style: string;
  interval_minutes: number;
}

export interface QueueItem {
  title: string;
  source: string;
  score: number;
  channel_id: string;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export function useChannels() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setChannels(await apiFetch<Channel[]>("/api/channels"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const createChannel = async (data: Omit<Channel, "id">) => {
    const ch = await apiFetch<Channel>("/api/channels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    await refresh();
    return ch;
  };

  const deleteChannel = async (id: string) => {
    await apiFetch(`/api/channels/${id}`, { method: "DELETE" });
    await refresh();
  };

  return { channels, loading, refresh, createChannel, deleteChannel };
}

export function useQueue() {
  const [queue, setQueue] = useState<QueueItem[]>([]);

  useEffect(() => {
    const poll = async () => {
      try {
        setQueue(await apiFetch<QueueItem[]>("/api/queue"));
      } catch {}
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  }, []);

  return queue;
}
