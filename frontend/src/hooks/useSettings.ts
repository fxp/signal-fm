import { useCallback, useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export interface Settings {
  company_name: string;
}

export function useSettings() {
  const [settings, setSettings] = useState<Settings>({ company_name: "智谱" });

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/settings`);
      if (res.ok) setSettings(await res.json());
    } catch {}
  }, []);

  useEffect(() => { load(); }, [load]);

  const updateCompanyName = async (name: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company_name: name }),
      });
      if (res.ok) setSettings(await res.json());
    } catch {}
  };

  return { settings, updateCompanyName };
}
