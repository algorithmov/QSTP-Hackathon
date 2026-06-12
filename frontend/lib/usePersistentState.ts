"use client";

import { useEffect, useState } from "react";

type NormalizeState<T> = (value: T) => T;

export function usePersistentState<T>(
  key: string,
  initialValue: T,
  normalize?: NormalizeState<T>,
) {
  const [value, setValue] = useState<T>(initialValue);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(key);
      if (stored) {
        const parsed = JSON.parse(stored) as T;
        setValue(normalize ? normalize(parsed) : parsed);
      }
    } catch {
      // Ignore invalid or blocked storage and keep the default state.
    } finally {
      setHydrated(true);
    }
  }, [key, normalize]);

  useEffect(() => {
    if (!hydrated) return;
    try {
      const nextValue = normalize ? normalize(value) : value;
      window.localStorage.setItem(key, JSON.stringify(nextValue));
    } catch {
      // Persistence is a convenience; the app should still work if storage is blocked.
    }
  }, [hydrated, key, normalize, value]);

  return [value, setValue] as const;
}
