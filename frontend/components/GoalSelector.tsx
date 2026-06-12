"use client";

import { goals, type Goal } from "@/types/route";

type GoalSelectorProps = {
  value: Goal;
  disabled?: boolean;
  onChange: (goal: Goal) => void;
};

export function GoalSelector({ value, disabled = false, onChange }: GoalSelectorProps) {
  return (
    <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Goal">
      {goals.map((goal) => {
        const active = value === goal.value;
        return (
          <button
            key={goal.value}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={disabled}
            className={`rounded-md border px-4 py-2 text-sm font-semibold transition ${
              active ? "border-accent bg-accent text-white" : "border-line bg-white text-ink hover:border-accent/60"
            } disabled:cursor-not-allowed disabled:opacity-60`}
            onClick={() => onChange(goal.value)}
          >
            {goal.label}
          </button>
        );
      })}
    </div>
  );
}
