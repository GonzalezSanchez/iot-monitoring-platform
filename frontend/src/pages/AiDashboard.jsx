import { useEffect, useRef, useState } from 'react';
import PageHeader from '../components/PageHeader';

const API = import.meta.env.VITE_AI_ENDPOINT || 'http://localhost:8001';

// Server also caps history (MAX_HISTORY_MESSAGES); this keeps requests small
const HISTORY_LIMIT = 6;

const SUGGESTIONS = [
  'Which rooms are being monitored?',
  'Which room is the warmest right now?',
  'How many anomalies did the lakehouse detect?',
];

function ToolBadge({ name }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-violet-50 text-violet-700 border border-violet-200">
      🔧 {name}
    </span>
  );
}

function Bubble({ message }) {
  const isUser = message.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-xl px-4 py-2.5 text-sm ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-white border border-gray-200 text-gray-700'
        }`}
      >
        {message.tools?.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {message.tools.map((t, i) => (
              <ToolBadge key={i} name={t} />
            ))}
          </div>
        )}
        {/* Plain text rendering only — LLM output is untrusted (PRD §13) */}
        <p className="whitespace-pre-wrap">{message.content || (isUser ? '' : '…')}</p>
      </div>
    </div>
  );
}

export default function AiDashboard() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const updateLast = (fn) =>
    setMessages((msgs) => {
      const next = [...msgs];
      next[next.length - 1] = fn(next[next.length - 1]);
      return next;
    });

  async function send(text) {
    const question = (text ?? input).trim();
    if (!question || busy) return;
    setError(null);
    setInput('');
    const history = [...messages, { role: 'user', content: question }];
    setMessages([...history, { role: 'assistant', content: '', tools: [] }]);
    setBusy(true);

    try {
      const res = await fetch(`${API}/ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: history
            .slice(-HISTORY_LIMIT)
            .map(({ role, content }) => ({ role, content })),
        }),
      });
      if (res.status === 429) {
        throw new Error('Too many requests — please wait a minute and try again.');
      }
      if (!res.ok) {
        throw new Error(`The assistant is unavailable right now (HTTP ${res.status}).`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split('\n\n');
        buffer = frames.pop();
        for (const frame of frames) {
          const line = frame.trim();
          if (!line.startsWith('data: ')) continue;
          const event = JSON.parse(line.slice(6));
          if (event.type === 'token') {
            updateLast((m) => ({ ...m, content: m.content + event.content }));
          } else if (event.type === 'tool_use') {
            updateLast((m) => ({ ...m, tools: [...m.tools, event.name] }));
          } else if (event.type === 'error') {
            throw new Error(event.message);
          }
        }
      }
    } catch (e) {
      setError(e.message);
      // Drop the empty assistant bubble if nothing arrived
      setMessages((msgs) => {
        const last = msgs[msgs.length - 1];
        return last?.role === 'assistant' && !last.content && !last.tools?.length
          ? msgs.slice(0, -1)
          : msgs;
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col h-full font-sans">
      <PageHeader
        title="AI Assistant"
        subtitle="Claude Haiku · MCP tools over the live platform APIs · SSE streaming"
      >
        <div className="mt-2 flex flex-wrap gap-2">
          {['Claude API', 'MCP', 'fastapi-mcp', 'SSE', 'Rate limited'].map((t) => (
            <span
              key={t}
              className="px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200"
            >
              {t}
            </span>
          ))}
        </div>
      </PageHeader>

      <div className="flex-1 overflow-auto px-6 py-5">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-64 gap-4 text-gray-400">
            <div className="text-4xl">💬</div>
            <p className="text-sm">Ask a question about the live sensor data.</p>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="px-3 py-1.5 rounded-full text-xs bg-white border border-gray-200 text-gray-600 hover:border-blue-300 hover:text-blue-700"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-col gap-3 max-w-3xl mx-auto">
          {messages.map((m, i) => (
            <Bubble key={i} message={m} />
          ))}
          <div ref={bottomRef} />
        </div>

        {error && (
          <div className="max-w-3xl mx-auto mt-3 bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">
            {error}
          </div>
        )}
      </div>

      <div className="border-t border-gray-200 bg-white px-6 py-4 shrink-0">
        <form
          className="flex gap-2 max-w-3xl mx-auto"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={busy ? 'Answering…' : 'Ask about rooms, events, or anomalies…'}
            disabled={busy}
            maxLength={2000}
            className="flex-1 rounded-xl border border-gray-300 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:bg-gray-50"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="rounded-xl bg-blue-600 text-white px-5 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-40"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
