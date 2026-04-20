import type { QueueItem } from "../hooks/useApi";

interface Props {
  items: QueueItem[];
}

const scoreColor = (score: number) => {
  if (score >= 90) return "var(--red)";
  if (score >= 75) return "var(--yellow)";
  return "var(--green)";
};

export default function Queue({ items }: Props) {
  return (
    <div style={styles.container}>
      <div style={styles.header}>
        播放队列
        <span style={styles.count}>{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div style={styles.empty}>队列为空</div>
      ) : (
        <div style={styles.list}>
          {items.map((item, i) => (
            <div key={i} style={styles.item}>
              <div style={{ ...styles.scoreBar, background: scoreColor(item.score) }} />
              <div style={styles.itemContent}>
                <div style={styles.itemTitle}>{item.title}</div>
                <div style={styles.itemMeta}>
                  <span>{item.source}</span>
                  <span style={{ color: scoreColor(item.score), fontWeight: 700 }}>
                    {item.score}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 16,
    padding: "20px",
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
    gap: 8,
  },
  count: {
    background: "var(--surface2)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: "1px 8px",
    fontSize: 11,
    color: "var(--text2)",
  },
  empty: { color: "var(--text3)", fontSize: 13, textAlign: "center", padding: "20px 0" },
  list: { display: "flex", flexDirection: "column", gap: 8, maxHeight: 320, overflowY: "auto" },
  item: { display: "flex", gap: 10, alignItems: "stretch" },
  scoreBar: { width: 3, borderRadius: 2, flexShrink: 0 },
  itemContent: { flex: 1, minWidth: 0 },
  itemTitle: {
    fontSize: 13,
    fontWeight: 500,
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  itemMeta: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 11,
    color: "var(--text2)",
    marginTop: 2,
  },
};
