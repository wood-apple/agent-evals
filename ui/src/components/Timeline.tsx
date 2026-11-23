import { usd } from '../format';
import type { TraceEvent } from '../types';

function Json({ value }: { value: unknown }) {
  return <pre>{typeof value === 'string' ? value : JSON.stringify(value, null, 2)}</pre>;
}

function Collapsible({ title, children, open = false }: { title: string; children: React.ReactNode; open?: boolean }) {
  return (
    <details open={open}>
      <summary>{title}</summary>
      {children}
    </details>
  );
}

interface ToolCallView {
  id: string;
  name: string;
  arguments: unknown;
  raw_arguments?: string;
}

function EventView({ event }: { event: TraceEvent }) {
  switch (event.type) {
    case 'session_start':
      return (
        <>
          <h4>Session {Number(event.session) + 1}</h4>
          {typeof event.system === 'string' && (
            <Collapsible title="System prompt">
              <Json value={event.system} />
            </Collapsible>
          )}
          <div className="bubble user">
            <span className="who">user</span>
            <Json value={event.prompt} />
          </div>
        </>
      );
    case 'model_response': {
      const calls = (event.tool_calls as ToolCallView[]) ?? [];
      return (
        <div className="bubble assistant">
          <span className="who">
            assistant · step {Number(event.step) + 1}
            {event.input_tokens !== undefined && (
              <> · {String(event.input_tokens)} in / {String(event.output_tokens)} out · {usd(event.cost_usd as number)}</>
            )}
            {Number(event.retries) > 0 && <> · {String(event.retries)} retries</>}
          </span>
          {typeof event.reasoning === 'string' && event.reasoning && (
            <Collapsible title="Reasoning">
              <Json value={event.reasoning} />
            </Collapsible>
          )}
          {typeof event.text === 'string' && event.text && <Json value={event.text} />}
          {calls.map((call) => (
            <div key={call.id} className="tool-call">
              <span className="badge">tool call</span> <code>{call.name}</code>
              {call.arguments === null ? (
                <span className="badge bad">invalid JSON arguments</span>
              ) : null}
              <Json value={call.arguments ?? call.raw_arguments} />
            </div>
          ))}
        </div>
      );
    }
    case 'tool_result':
      return (
        <div className={`bubble tool ${event.error ? 'has-error' : ''}`}>
          <span className="who">
            result · <code>{String(event.name ?? 'rejected call')}</code>
            {event.error ? <span className="badge bad">{String(event.error)}</span> : null}
          </span>
          <Collapsible title={`${String(event.result ?? '').length} characters`} open={Boolean(event.error)}>
            <Json value={event.result} />
          </Collapsible>
        </div>
      );
    case 'memory_read':
      return (
        <div className="bubble memory">
          <span className="who">memory read</span>
          <Json value={event.content || '(empty)'} />
        </div>
      );
    case 'memory_write':
      return (
        <div className="bubble memory">
          <span className="who">memory write</span>
          <Json value={event.content} />
        </div>
      );
    case 'skill_load':
      return (
        <div className="bubble skill">
          <span className="who">skill loaded</span> <code>{String(event.name)}</code>
        </div>
      );
    case 'retried':
      return (
        <div className="bubble stop">
          <span className="who">retried after infrastructure errors · this is attempt {String(event.attempts)}</span>
          <Json value={(event.errors as string[]).join('\n')} />
        </div>
      );
    case 'stop':
      return <div className="bubble stop">Stopped: {String(event.reason)}</div>;
    case 'error':
      return (
        <div className="bubble has-error">
          <span className="who">error</span>
          <Json value={event.message} />
          <Collapsible title="Traceback">
            <Json value={event.traceback} />
          </Collapsible>
        </div>
      );
    case 'grading':
      return (
        <div className="bubble grading">
          <span className="who">graded · judge cost {usd(event.cost_usd as number)}</span>
          <Collapsible title="Final answer" open>
            <Json value={event.answer || '(empty)'} />
          </Collapsible>
          <Collapsible title="Files in the sandbox">
            <Json value={(event.files as string[]).join('\n') || '(none)'} />
          </Collapsible>
        </div>
      );
    default:
      return (
        <div className="bubble">
          <span className="who">{event.type}</span>
          <Json value={event} />
        </div>
      );
  }
}

export function Timeline({ events }: { events: TraceEvent[] }) {
  return (
    <div className="timeline">
      {events.map((event, i) => (
        <div key={i} className="event">
          <span className="time">{event.t_ms !== undefined ? `${(event.t_ms / 1000).toFixed(1)}s` : ''}</span>
          <div className="body">
            <EventView event={event} />
          </div>
        </div>
      ))}
    </div>
  );
}
