"use client";

import { useState } from "react";

type Props = {
  gameId: string;
  category: "Survivor" | "Spread" | "Total";
  pick: string;
  confidence: number;
};

export function SavePickButton({ gameId, category, pick, confidence }: Props) {
  const [saved, setSaved] = useState(false);

  function savePick() {
    const current = JSON.parse(localStorage.getItem("sportsintel-picks") ?? "[]");
    const next = [
      ...current.filter((item: any) => item.category !== category),
      { gameId, category, pick, confidence },
    ];
    localStorage.setItem("sportsintel-picks", JSON.stringify(next));
    setSaved(true);
  }

  return (
    <button type="button" onClick={savePick}>
      {saved ? "Saved ✓" : `Save ${category}`}
    </button>
  );
}
