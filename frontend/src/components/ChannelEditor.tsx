import { useState } from "react";
import type { Channel } from "../hooks/useApi";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

interface Props {
  channels: Channel[];
  onCreate: (data: Omit<Channel, "id">) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}

const STYLE_LABELS: Record<string, string> = {
  formal: "严肃简报",
  casual: "轻松点评",
  deep: "深度解读",
};

const VOICE_LABELS: Record<string, string> = {
  "zh-CN-female": "晓晓（女）",
  "zh-CN-male": "云希（男）",
  "zh-TW-female": "晓臻（台湾女）",
};

export default function ChannelEditor({ channels, onCreate, onDelete }: Props) {
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [triggering, setTriggering] = useState<string | null>(null);

  const triggerFetch = async (id: string) => {
    setTriggering(id);
    try {
      await fetch(`${API_BASE}/api/channels/${id}/trigger`, { method: "POST" });
    } finally {
      setTriggering(null);
    }
  };
  const [form, setForm] = useState({
    name: "",
    topic: "",
    rss_feeds: "",
    keywords: "",
    crawl_urls: "",
    preference: "",
    style: "formal",
    voice: "zh-CN-female",
    interval_minutes: 15,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onCreate({
        name: form.name,
        topic: form.topic,
        rss_feeds: form.rss_feeds.split("\n").map((s) => s.trim()).filter(Boolean),
        keywords: form.keywords.split(",").map((s) => s.trim()).filter(Boolean),
        crawl_urls: form.crawl_urls.split("\n").map((s) => s.trim()).filter(Boolean),
        preference: form.preference,
        style: form.style,
        voice: form.voice,
        interval_minutes: form.interval_minutes,
      });
      setShowForm(false);
      setForm({ name: "", topic: "", rss_feeds: "", keywords: "", crawl_urls: "", preference: "", style: "formal", voice: "zh-CN-female", interval_minutes: 15 });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        频道管理
        <button style={styles.addBtn} onClick={() => setShowForm(!showForm)}>
          {showForm ? "✕ 取消" : "+ 新建频道"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} style={styles.form}>
          <Field label="频道名称" required>
            <input style={styles.input} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="如：AI 速报" required />
          </Field>
          <Field label="频道主题" required>
            <input style={styles.input} value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })} placeholder="如：AI 大模型与科技产品进展" required />
          </Field>
          <Field label="RSS 源（每行一个）">
            <textarea style={{ ...styles.input, height: 72 }} value={form.rss_feeds} onChange={(e) => setForm({ ...form, rss_feeds: e.target.value })} placeholder="https://36kr.com/feed&#10;https://feeds.feedburner.com/..." />
          </Field>
          <Field label="关键词（逗号分隔）">
            <input style={styles.input} value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} placeholder="GPT-5, Claude, 大模型" />
          </Field>
          <Field label="爬虫网址（每行一个，无 RSS 的站点）">
            <textarea style={{ ...styles.input, height: 56 }} value={form.crawl_urls} onChange={(e) => setForm({ ...form, crawl_urls: e.target.value })} placeholder="https://venturebeat.com/ai/" />
          </Field>
          <Field label="播报偏好（自然语言描述）">
            <textarea style={{ ...styles.input, height: 60 }} value={form.preference} onChange={(e) => setForm({ ...form, preference: e.target.value })} placeholder="优先播报 GPT/Claude 的突破进展，淡化纯融资新闻" />
          </Field>
          <div style={styles.row}>
            <Field label="播报风格">
              <select style={styles.input} value={form.style} onChange={(e) => setForm({ ...form, style: e.target.value })}>
                {Object.entries(STYLE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </Field>
            <Field label="主播音色">
              <select style={styles.input} value={form.voice} onChange={(e) => setForm({ ...form, voice: e.target.value })}>
                {Object.entries(VOICE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </Field>
            <Field label="抓取间隔（分钟）">
              <input type="number" style={styles.input} value={form.interval_minutes} onChange={(e) => setForm({ ...form, interval_minutes: Number(e.target.value) })} min={5} max={60} />
            </Field>
          </div>
          <button type="submit" style={styles.submitBtn} disabled={submitting}>
            {submitting ? "创建中…" : "创建频道"}
          </button>
        </form>
      )}

      <div style={styles.list}>
        {channels.length === 0 && !showForm && (
          <div style={styles.empty}>还没有频道，点击"新建频道"开始</div>
        )}
        {channels.map((ch) => (
          <div key={ch.id} style={styles.channelCard}>
            <div style={styles.channelInfo}>
              <div style={styles.channelName}>{ch.name}</div>
              <div style={styles.channelMeta}>
                {ch.topic} · {STYLE_LABELS[ch.style] || ch.style} · {VOICE_LABELS[ch.voice] || ch.voice} · 每 {ch.interval_minutes} 分钟
              </div>
              <div style={styles.channelTags}>
                {ch.rss_feeds.length > 0 && <Tag>{ch.rss_feeds.length} 个 RSS</Tag>}
                {ch.keywords.length > 0 && <Tag>{ch.keywords.join("、")}</Tag>}
                {ch.crawl_urls.length > 0 && <Tag>{ch.crawl_urls.length} 个爬虫</Tag>}
              </div>
            </div>
            <div style={styles.cardActions}>
              <button
                style={{ ...styles.triggerBtn, opacity: triggering === ch.id ? 0.5 : 1 }}
                onClick={() => triggerFetch(ch.id)}
                disabled={triggering === ch.id}
                title="立即抓取"
              >
                {triggering === ch.id ? "⟳" : "↺"}
              </button>
              <button style={styles.deleteBtn} onClick={() => onDelete(ch.id)} title="删除">✕</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <label style={{ fontSize: 12, color: "var(--text2)", fontWeight: 500 }}>
        {label}{required && <span style={{ color: "var(--accent2)" }}> *</span>}
      </label>
      {children}
    </div>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 6, padding: "2px 8px", fontSize: 11, color: "var(--text2)" }}>
      {children}
    </span>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 16, padding: "20px", display: "flex", flexDirection: "column", gap: 16 },
  header: { fontWeight: 700, fontSize: 13, letterSpacing: 1, color: "var(--text2)", textTransform: "uppercase", display: "flex", alignItems: "center", justifyContent: "space-between" },
  addBtn: { fontSize: 12, color: "var(--accent)", fontWeight: 600, padding: "4px 10px", border: "1px solid var(--accent)", borderRadius: 8 },
  form: { display: "flex", flexDirection: "column", gap: 12, background: "var(--surface2)", borderRadius: 12, padding: 16 },
  input: { background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, padding: "8px 10px", color: "var(--text)", fontSize: 13, width: "100%", outline: "none", resize: "vertical" },
  row: { display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 },
  submitBtn: { background: "linear-gradient(135deg, var(--accent), var(--accent2))", color: "#fff", fontWeight: 700, padding: "10px", borderRadius: 10, fontSize: 14, marginTop: 4 },
  list: { display: "flex", flexDirection: "column", gap: 8 },
  empty: { color: "var(--text3)", fontSize: 13, textAlign: "center", padding: "20px 0" },
  channelCard: { display: "flex", alignItems: "flex-start", gap: 12, background: "var(--surface2)", borderRadius: 10, padding: "12px 14px" },
  channelInfo: { flex: 1, display: "flex", flexDirection: "column", gap: 4 },
  channelName: { fontWeight: 600, fontSize: 14 },
  channelMeta: { fontSize: 11, color: "var(--text2)" },
  channelTags: { display: "flex", flexWrap: "wrap", gap: 4, marginTop: 2 },
  cardActions: { display: "flex", flexDirection: "column", gap: 4, alignItems: "center" },
  triggerBtn: { color: "var(--accent)", fontSize: 16, padding: 4, transition: "opacity 0.2s", cursor: "pointer" },
  deleteBtn: { color: "var(--text3)", fontSize: 14, padding: 4 },
};
