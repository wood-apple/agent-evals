import { useCallback, useEffect, useState } from 'react';

export function useData<T>(load: () => Promise<T>, deps: unknown[], refreshMs?: number) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string>();
  const reload = useCallback(load, deps);

  useEffect(() => {
    let cancelled = false;
    const run = () =>
      reload()
        .then((value) => !cancelled && (setData(value), setError(undefined)))
        .catch((e: Error) => !cancelled && setError(e.message));
    run();
    const timer = refreshMs ? setInterval(run, refreshMs) : undefined;
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [reload, refreshMs]);

  const refresh = () =>
    reload()
      .then((value) => (setData(value), setError(undefined)))
      .catch((e: Error) => setError(e.message));
  return { data, error, reload: refresh };
}
