import { useState } from 'react';

// POST a JSON body to `url` with submitting/result state.
// `result` is { ok, data }; network errors land in data.detail / data.error.
function usePostJson(url) {
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  const submit = (body, onSuccess) => {
    setSubmitting(true);
    setResult(null);
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
      .then(res => res.json().then(data => ({ ok: res.ok, data })))
      .catch(err => ({ ok: false, data: { detail: err.message, error: err.message } }))
      .then(({ ok, data }) => {
        setResult({ ok, data });
        setSubmitting(false);
        if (ok) onSuccess?.(data);
      });
  };

  return { submit, submitting, result, setResult };
}

export default usePostJson;
