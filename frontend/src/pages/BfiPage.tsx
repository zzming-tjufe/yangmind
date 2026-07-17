import { useEffect, useMemo, useState } from "react";
import { ApiError } from "../api/client";
import * as surveyApi from "../api/survey";
import type { MyResponse, SurveyInstrument } from "../api/survey";
import { useToast } from "../context/ToastContext";
import { useSiteContent } from "../hooks/useSite";

const PAGE_SIZE = 11;

export function BfiPage() {
  const { toast } = useToast();
  const { byKey: content } = useSiteContent();
  const [introDone, setIntroDone] = useState(false);
  const [instrument, setInstrument] = useState<SurveyInstrument | null>(null);
  const [mine, setMine] = useState<MyResponse | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [qpage, setQpage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [inst, resp] = await Promise.all([surveyApi.getBfi(), surveyApi.getMyResponse()]);
        if (cancelled) return;
        setInstrument(inst);
        setMine(resp);
        const map: Record<number, number> = {};
        Object.entries(resp.answers).forEach(([k, v]) => {
          map[Number(k)] = v;
        });
        setAnswers(map);
        if (resp.status === "submitted" || resp.answered_count > 0) setIntroDone(true);
      } catch (e) {
        toast(e instanceof ApiError ? e.message : "加载问卷失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [toast]);

  const answered = Object.keys(answers).length;
  const progress = Math.round((answered / 44) * 100);
  const start = (qpage - 1) * PAGE_SIZE;
  const pageItems = useMemo(
    () => instrument?.items.slice(start, start + PAGE_SIZE) ?? [],
    [instrument, start],
  );

  async function onAnswer(itemNo: number, value: number) {
    setAnswers((prev) => ({ ...prev, [itemNo]: value }));
    try {
      const resp = await surveyApi.saveAnswers([{ item_no: itemNo, value }]);
      setMine(resp);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "保存失败");
    }
  }

  async function onSubmit() {
    if (answered < 44) {
      toast(`还有 ${44 - answered} 题未完成，请检查后提交`);
      return;
    }
    setBusy(true);
    try {
      const resp = await surveyApi.submitSurvey();
      setMine(resp);
      toast("问卷已提交，博弈入口已解锁");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "提交失败");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <div className="page"><p>加载中…</p></div>;

  if (mine?.status === "submitted" && mine.personality) {
    const p = mine.personality;
    const dims = [
      `开放性 ${Math.round(p.o * 20)}`,
      `尽责性 ${Math.round(p.c * 20)}`,
      `外向性 ${Math.round(p.e * 20)}`,
      `宜人性 ${Math.round(p.a * 20)}`,
      `情绪敏感 ${Math.round(p.n * 20)}`,
    ];
    return (
      <div className="page">
        <section className="hero card">
          <div>
            <div className="eyebrow">已完成 · {mine.quality_passed ? "质量检查通过" : "已提交"}</div>
            <h2>你的人格轮廓已生成</h2>
            <p>
              {p.summary_label}。结果用于解释博弈中的决策倾向，不代表能力高低。
            </p>
          </div>
          <div className="ring" style={{ ["--p" as string]: "360deg" }}>
            <b>100%</b>
          </div>
        </section>
        <div className="statgrid" style={{ marginTop: 18 }}>
          {dims.map((x) => (
            <div className="stat card" key={x}>
              <span>人格维度</span>
              <b>{x}</b>
              <em>已生成</em>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!introDone) {
    const intro = content["bfi.intro"];
    const introTitle = intro?.title || "认识大五人格模型";
    const introParts = (intro?.body || "").split("\n\n");
    const introLead =
      introParts[0] ||
      "在开始作答前，请先阅读以下简要介绍，了解问卷所测量的五项人格维度。";
    const introNote =
      introParts[1] ||
      "人格特质没有绝对的好坏之分。本问卷结果仅用于本次研究中的行为分析，不作为临床诊断依据。";
    const announcement = content["announcement.banner"];

    return (
      <div className="page theory-page">
        {announcement?.body?.trim() && (
          <div className="alert" style={{ marginBottom: 16 }}>
            <i>!</i>
            <div>
              <b>{announcement.title || "平台公告"}</b>
              <small>{announcement.body}</small>
            </div>
          </div>
        )}
        <section className="theory-hero card">
          <div>
            <div className="eyebrow">BFI-44 · 理论导读</div>
            <h2>{introTitle}</h2>
            <p>{introLead}</p>
          </div>
          <div className="theory-index">
            <small>理论基础</small>
            <b>1.2</b>
          </div>
        </section>
        <div className="theory-note">
          <b>
            阅读
            <br />
            提示
          </b>
          <span>{introNote}</span>
        </div>
        <div className="theory-action card">
          <div>
            <small>预计用时</small>
            <b>6–8 分钟 · 共 44 题</b>
          </div>
          <button className="primary" type="button" onClick={() => setIntroDone(true)}>
            我已了解，开始填写 BFI-44 →
          </button>
        </div>
      </div>
    );
  }

  const surveyHero = content["bfi.survey_hero"];

  return (
    <div className="page">
      <section className="hero card">
        <div>
          <div className="eyebrow">参与博弈前置步骤</div>
          <h2>{surveyHero?.title || "先认识自己的决策底色"}</h2>
          <p>
            {surveyHero?.body ||
              "BFI-44 用 44 个简短陈述了解你的五项人格维度。请根据真实、稳定的自己作答。"}
          </p>
        </div>
        <div className="ring" style={{ ["--p" as string]: `${progress * 3.6}deg` }}>
          <b>{progress}%</b>
        </div>
      </section>
      <div className="quality">
        <i>✓</i>
        <div>
          <b>答案自动保存到服务器</b>
          <small>量表：1 = 非常不同意 · 5 = 非常同意。已作答 {answered} / 44</small>
        </div>
      </div>
      <section className="question-card card">
        <div className="qhead">
          <div>
            <span>
              第 {qpage} / 4 组
            </span>
            <br />
            <b>请判断以下描述与你的符合程度</b>
          </div>
          <span>
            {answered} / 44 已作答
          </span>
        </div>
        {pageItems.map((item) => (
          <div className="qrow" key={item.item_no}>
            <div className="qtext">
              <b>{String(item.item_no).padStart(2, "0")}</b>
              我认为自己是一个{item.stem}的人。
            </div>
            <div className="scale">
              {[1, 2, 3, 4, 5].map((v) => (
                <label key={v}>
                  <input
                    type="radio"
                    name={`q${item.item_no}`}
                    checked={answers[item.item_no] === v}
                    onChange={() => onAnswer(item.item_no, v)}
                  />
                  <i />
                  {v}
                </label>
              ))}
            </div>
          </div>
        ))}
        <div className="qfoot">
          <button
            className="secondary"
            type="button"
            disabled={qpage === 1}
            onClick={() => setQpage((p) => Math.max(1, p - 1))}
          >
            ← 上一组
          </button>
          <span>答案已同步到后端</span>
          {qpage < 4 ? (
            <button className="primary" type="button" onClick={() => setQpage((p) => p + 1)}>
              下一组 →
            </button>
          ) : (
            <button className="primary" type="button" disabled={busy} onClick={onSubmit}>
              {busy ? "提交中…" : "提交问卷 →"}
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
