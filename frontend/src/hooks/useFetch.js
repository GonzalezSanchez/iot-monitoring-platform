import { useCallback, useEffect, useState } from 'react';

// GET JSON from `url` with loading/error state. Pass a falsy url to disable.
// `refreshMs` re-fetches on an interval (polling).
function useFetch(url, { refreshMs } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(Boolean(url));
  const [error, setError] = useState(null);

  const refetch = useCallback(() => {
    if (!url) return;
    fetch(url)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(d => {
        setData(d);
        setError(null);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [url]);

  useEffect(() => {
    if (!url) {
      setData(null);
      setError(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    refetch();
    if (refreshMs) {
      const interval = setInterval(refetch, refreshMs);
      return () => clearInterval(interval);
    }
  }, [url, refreshMs, refetch]);

  return { data, loading, error, refetch };
}

export default useFetch;
