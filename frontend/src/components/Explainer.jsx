// AI explainer panel: a gold "AI" tag + button that narrates the computed numbers in
// plain language. Numbers always come from the engine; this only explains them.
import { useEffect, useState } from "react";
import { getAIStatus, sendJSON } from "../api/client";
import { Button } from "./ui";

export default function Explainer({ module, data, label = "Explain this with AI" }) {
  const [status, setStatus] = useState(null);
  const [text, setText] = useState("");
  const [isError, setIsError] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getAIStatus().then(setStatus);
  }, []);

  // A new data set invalidates the previous explanation.
  useEffect(() => {
    setText("");
    setIsError(false);
  }, [data]);

  async function run() {
    setLoading(true);
    setIsError(false);
    try {
      const res = await sendJSON("/api/ai/explain", { module, data });
      setText(res.text || "");
      setIsError(Boolean(res.error));
    } catch (e) {
      setText(e.message);
      setIsError(true);
    } finally {
      setLoading(false);
    }
  }

  const configured = status?.configured;

  return (
    <div className="rounded-xl border border-hairline bg-card p-5">
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-2 text-sm font-semibold text-headline">
          <span className="rounded bg-gold px-1.5 py-0.5 text-[10px] font-bold text-onprimary">
            AI
          </span>
          Plain-language explanation
        </span>
        {configured && (
          <Button variant="secondary" onClick={run} disabled={loading}>
            {loading ? "Thinking…" : text && !isError ? "Regenerate" : label}
          </Button>
        )}
      </div>

      {status && !configured && (
        <p className="mt-2 text-sm text-muted">
          AI explainer is off — the numbers above are computed without AI. To enable
          beginner-friendly explanations, set <code className="text-body">AI_PROVIDER</code> and a
          key in <code className="text-body">backend/.env</code> (free Gemini works).
        </p>
      )}

      {configured && !text && !loading && (
        <p className="mt-2 text-sm text-muted">
          Get a beginner-friendly explanation of the figures above — what they mean and the
          single most important risk. Educational only, not advice.
        </p>
      )}

      {text && (
        <p className={`mt-3 whitespace-pre-line text-sm leading-relaxed ${isError ? "text-warn" : "text-body"}`}>
          {text}
        </p>
      )}
    </div>
  );
}
