import { useCallback, useEffect, useRef, useState, type DependencyList } from "react";

export function useApi<T>(loader: () => Promise<T>, refreshMs = 0, dependencies: DependencyList = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const reload = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const result = await loaderRef.current();
      setData(result);
      setError(null);
      setUpdatedAt(Date.now());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Bilinmeyen API hatası");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const guarded = async (silent: boolean) => { if (active) await reload(silent); };
    void guarded(false);
    const timer = refreshMs > 0 ? window.setInterval(() => void guarded(true), refreshMs) : null;
    return () => { active = false; if (timer) window.clearInterval(timer); };
  }, [reload, refreshMs, ...dependencies]);

  return { data, error, loading, updatedAt, reload };
}
