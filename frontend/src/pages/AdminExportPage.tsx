import { useState } from "react";
import { downloadAdminExport, type ExportFormat, type ExportKind } from "../api/admin";
import { ModalOverlay } from "../components/ModalPortal";
import { useToast } from "../context/ToastContext";

type ExportCard = {
  kind: ExportKind;
  title: string;
  layer: string;
  defaultName: string;
  summary: string;
  details: string[];
};

const CARDS: ExportCard[] = [
  {
    kind: "users",
    title: "用户层",
    layer: "users",
    defaultName: "users",
    summary: "每位参与者一行：账号信息、问卷完成与质量状态、大五人格得分与摘要、博弈场次与总分。",
    details: [
      "适合做被试名单与总体描述统计",
      "CSV 为中文表头；JSON 为原始字段结构",
    ],
  },
  {
    kind: "survey-answers",
    title: "问卷答卷明细",
    layer: "问卷层 · 答卷",
    defaultName: "survey_answers",
    summary: "每位参与者一行，横向展开 BFI-44 全部 44 题作答（题1…题44）。",
    details: [
      "与质量信息分开，便于直接进分析软件",
      "含重做前归档答卷（记录来源会标明）",
    ],
  },
  {
    kind: "survey-quality",
    title: "问卷质量",
    layer: "问卷层 · 质量",
    defaultName: "survey_quality",
    summary: "每位答卷一行：是否通过、注意力题、自报认真程度、时长、失焦、硬排除与软标记、管理员复核。",
    details: [
      "CSV 已把质量指标拆成可读中文列",
      "JSON 保留 quality_flags 等原始嵌套结构",
    ],
  },
  {
    kind: "runs",
    title: "博弈轮次",
    layer: "runs",
    defaultName: "runs",
    summary: "每位参与者每轮一行：场景、对局与轮次、双方选项与得分、决策时间、超时、双方问卷质量与理解测试。",
    details: [
      "含「可用于主分析」等研究筛选字段",
      "文件名默认 runs，与分析约定一致",
    ],
  },
];

export function AdminExportPage() {
  const { toast } = useToast();
  const [active, setActive] = useState<ExportCard | null>(null);
  const [format, setFormat] = useState<ExportFormat>("csv");
  const [filename, setFilename] = useState("users");
  const [busy, setBusy] = useState(false);

  function openCard(card: ExportCard) {
    setActive(card);
    setFormat("csv");
    setFilename(card.defaultName);
  }

  async function confirmExport() {
    if (!active) return;
    const name = filename.trim() || active.defaultName;
    setBusy(true);
    try {
      await downloadAdminExport(active.kind, format, name);
      toast("导出已开始下载（请在浏览器下载位置查看）");
      setActive(null);
    } catch (e) {
      toast(e instanceof Error ? e.message : "导出失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <section className="export-hero card">
        <div className="eyebrow">研究数据导出</div>
        <h2>按数据层级下载分析文件</h2>
        <p>
          共四个导出块。点某一块后选择 CSV（中文可读）或 JSON（原始结构）。浏览器会弹出下载 /
          另存为，无法指定服务器上的文件夹。
        </p>
      </section>

      <div className="export-grid">
        {CARDS.map((card) => (
          <article key={card.kind} className="export-block card">
            <div className="eyebrow">{card.layer}</div>
            <h3>{card.title}</h3>
            <p>{card.summary}</p>
            <ul>
              {card.details.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <button className="primary" type="button" onClick={() => openCard(card)}>
              导出…
            </button>
          </article>
        ))}
      </div>

      {active ? (
        <ModalOverlay onClose={() => !busy && setActive(null)}>
          <section className="modal card export-modal" role="dialog" aria-modal="true">
            <header className="profile-modal-head">
              <div>
                <b>导出 · {active.title}</b>
                <small>默认文件名可改；扩展名会按格式自动补上</small>
              </div>
              <button type="button" onClick={() => setActive(null)} aria-label="关闭" disabled={busy}>
                ×
              </button>
            </header>
            <div className="profile-modal-body">
              <p className="export-modal-summary">{active.summary}</p>
              <fieldset className="export-format">
                <legend>导出格式</legend>
                <label>
                  <input
                    type="radio"
                    name="export-format"
                    checked={format === "csv"}
                    onChange={() => setFormat("csv")}
                  />
                  CSV（中文表头，适合 Excel）
                </label>
                <label>
                  <input
                    type="radio"
                    name="export-format"
                    checked={format === "json"}
                    onChange={() => setFormat("json")}
                  />
                  JSON（原始结构，适合脚本）
                </label>
              </fieldset>
              <label className="field">
                文件名
                <input
                  value={filename}
                  onChange={(e) => setFilename(e.target.value)}
                  placeholder={active.defaultName}
                />
              </label>
              <p className="export-modal-hint">
                将保存为 <code>{(filename.trim() || active.defaultName).replace(/\.(csv|json)$/i, "")}.{format}</code>
                。保存位置由浏览器决定（通常是「下载」文件夹，或另存为对话框）。
              </p>
              <div className="export-actions" style={{ marginTop: 16 }}>
                <button className="primary" type="button" disabled={busy} onClick={confirmExport}>
                  {busy ? "导出中…" : "开始导出"}
                </button>
                <button className="secondary" type="button" disabled={busy} onClick={() => setActive(null)}>
                  取消
                </button>
              </div>
            </div>
          </section>
        </ModalOverlay>
      ) : null}
    </div>
  );
}
