import { useState } from "react";
import type { Settings } from "../hooks/useSettings";

interface Props {
  settings: Settings;
  onUpdate: (name: string) => Promise<void>;
}

export default function SettingsPanel({ settings, onUpdate }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(settings.company_name);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!draft.trim() || draft === settings.company_name) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      await onUpdate(draft.trim());
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") save();
    if (e.key === "Escape") { setEditing(false); setDraft(settings.company_name); }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        ⚙️ 全局设置
      </div>

      <div style={styles.row}>
        <span style={styles.label}>我的公司</span>
        {editing ? (
          <div style={styles.editRow}>
            <input
              style={styles.input}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKey}
              autoFocus
              maxLength={20}
              placeholder="公司名称"
            />
            <button style={styles.saveBtn} onClick={save} disabled={saving}>
              {saving ? "…" : "保存"}
            </button>
            <button
              style={styles.cancelBtn}
              onClick={() => { setEditing(false); setDraft(settings.company_name); }}
            >
              取消
            </button>
          </div>
        ) : (
          <div style={styles.valueRow}>
            <span style={styles.value}>{settings.company_name}</span>
            <button style={styles.editBtn} onClick={() => { setDraft(settings.company_name); setEditing(true); }}>
              修改
            </button>
          </div>
        )}
      </div>

      <div style={styles.hint}>
        影响分析功能将基于此公司名称生成业务洞察与合作机会
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 16,
    padding: "16px 20px",
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  header: {
    fontWeight: 700,
    fontSize: 13,
    letterSpacing: 1,
    color: "var(--text2)",
    textTransform: "uppercase",
  },
  row: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  label: {
    fontSize: 12,
    color: "var(--text2)",
    flexShrink: 0,
    width: 56,
  },
  editRow: {
    display: "flex",
    gap: 6,
    alignItems: "center",
    flex: 1,
  },
  input: {
    flex: 1,
    background: "var(--bg)",
    border: "1px solid var(--accent)",
    borderRadius: 6,
    padding: "5px 8px",
    color: "var(--text)",
    fontSize: 13,
    outline: "none",
  },
  saveBtn: {
    fontSize: 12,
    fontWeight: 600,
    color: "#fff",
    background: "var(--accent)",
    borderRadius: 6,
    padding: "5px 10px",
    cursor: "pointer",
  },
  cancelBtn: {
    fontSize: 12,
    color: "var(--text3)",
    padding: "5px 8px",
    cursor: "pointer",
  },
  valueRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    flex: 1,
  },
  value: {
    fontSize: 14,
    fontWeight: 600,
    color: "var(--accent2)",
    letterSpacing: 0.5,
  },
  editBtn: {
    fontSize: 11,
    color: "var(--text3)",
    border: "1px solid var(--border)",
    borderRadius: 5,
    padding: "3px 8px",
    cursor: "pointer",
  },
  hint: {
    fontSize: 11,
    color: "var(--text3)",
    lineHeight: 1.5,
  },
};
