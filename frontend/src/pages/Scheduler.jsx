import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Plus, Play, Trash2, Pencil, Power, Check, X, RefreshCw, MessageCircle } from 'lucide-react';
import Layout from '../components/layout/Layout';
import Button from '../components/common/Button';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';
import MarkdownMessage from '../components/common/MarkdownMessage';
import { useAuthStore } from '../store/authStore';
import { schedulerApi, errorMessage } from '../services/scheduler';

// ─────────────────────────────────────────────────────────────────────────────
// Constants & helpers
// ─────────────────────────────────────────────────────────────────────────────
const STATUS_STYLES = {
  queued: { color: 'var(--gray-700)', bg: 'rgba(163,163,163,.15)', label: 'Queued' },
  running: { color: 'var(--primary)', bg: 'rgba(96,165,250,.15)', label: 'Running' },
  awaiting_approval: { color: 'var(--warning)', bg: 'rgba(251,191,36,.15)', label: 'Awaiting approval' },
  success: { color: 'var(--success)', bg: 'rgba(52,211,153,.15)', label: 'Success' },
  failed: { color: 'var(--danger)', bg: 'rgba(248,113,113,.15)', label: 'Failed' },
  rejected: { color: 'var(--gray-700)', bg: 'rgba(163,163,163,.15)', label: 'Rejected' },
  expired: { color: 'var(--gray-700)', bg: 'rgba(163,163,163,.15)', label: 'Expired' },
  skipped: { color: 'var(--gray-700)', bg: 'rgba(163,163,163,.15)', label: 'Skipped' },
};

const MODE_STYLES = {
  manual: { color: 'var(--warning)', bg: 'rgba(251,191,36,.15)', label: 'Manual' },
  auto: { color: 'var(--success)', bg: 'rgba(52,211,153,.15)', label: 'Auto' },
  skip_all: { color: 'var(--danger)', bg: 'rgba(248,113,113,.15)', label: 'Skip all' },
};

const KIND_LABELS = {
  internal: 'internal',
  read_external: 'reads external data',
  write_external: 'writes / sends',
  remote_exec: 'remote execution',
};

const Pill = ({ color, bg, children }) => (
  <span
    style={{
      display: 'inline-block', fontSize: '11px', fontWeight: 600, padding: '2px 8px',
      borderRadius: '99px', color, background: bg, whiteSpace: 'nowrap',
    }}
  >
    {children}
  </span>
);

const StatusPill = ({ status }) => {
  const s = STATUS_STYLES[status] || STATUS_STYLES.queued;
  return <Pill color={s.color} bg={s.bg}>{s.label}</Pill>;
};

const ModePill = ({ mode }) => {
  const s = MODE_STYLES[mode] || MODE_STYLES.manual;
  return <Pill color={s.color} bg={s.bg}>{s.label}</Pill>;
};

const fmt = (value, tz) => {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString(undefined, tz ? { timeZone: tz } : undefined);
  } catch (_) {
    return new Date(value).toLocaleString();
  }
};

const duration = (run) => {
  if (!run.started_at || !run.completed_at) return '';
  const seconds = Math.max(0, Math.round((new Date(run.completed_at) - new Date(run.started_at)) / 1000));
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
};

const defaultTimezone = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch (_) {
    return 'UTC';
  }
};

const timezoneList = () => {
  try {
    if (typeof Intl.supportedValuesOf === 'function') return Intl.supportedValuesOf('timeZone');
  } catch (_) { /* fall through */ }
  return ['UTC', 'Europe/Paris', 'Europe/London', 'America/New_York', 'America/Los_Angeles', 'Asia/Tokyo'];
};

// ── Cron presets ─────────────────────────────────────────────────────────────
const PRESET_KINDS = [
  { value: 'every_n_minutes', label: 'Every N minutes' },
  { value: 'hourly', label: 'Every hour' },
  { value: 'daily', label: 'Every day' },
  { value: 'weekdays', label: 'Weekdays (Mon–Fri)' },
  { value: 'weekly', label: 'Every week' },
  { value: 'monthly', label: 'Every month' },
  { value: 'custom', label: 'Custom cron expression' },
];

const DAYS_OF_WEEK = [
  { value: '1', label: 'Monday' }, { value: '2', label: 'Tuesday' }, { value: '3', label: 'Wednesday' },
  { value: '4', label: 'Thursday' }, { value: '5', label: 'Friday' }, { value: '6', label: 'Saturday' },
  { value: '0', label: 'Sunday' },
];

const SCHEDULE_DEFAULT = { kind: 'daily', hour: 8, minute: 0, dow: '1', dom: 1, n: 15, custom: '0 8 * * *' };

const clamp = (value, lo, hi) => {
  const n = Math.trunc(Number(value));
  if (!Number.isFinite(n)) return lo;
  return Math.min(hi, Math.max(lo, n));
};

const buildCron = (s) => {
  const m = clamp(s.minute, 0, 59);
  const h = clamp(s.hour, 0, 23);
  switch (s.kind) {
    case 'every_n_minutes': return `*/${clamp(s.n, 1, 59)} * * * *`;
    case 'hourly': return `${m} * * * *`;
    case 'daily': return `${m} ${h} * * *`;
    case 'weekdays': return `${m} ${h} * * 1-5`;
    case 'weekly': return `${m} ${h} * * ${s.dow}`;
    case 'monthly': return `${m} ${h} ${clamp(s.dom, 1, 28)} * *`;
    default: return (s.custom || '').trim();
  }
};

const parseCron = (expr) => {
  const e = (expr || '').trim();
  const base = { ...SCHEDULE_DEFAULT, custom: e };
  let m = e.match(/^\*\/(\d+) \* \* \* \*$/);
  if (m) return { ...base, kind: 'every_n_minutes', n: Number(m[1]) };
  m = e.match(/^(\d+) \* \* \* \*$/);
  if (m) return { ...base, kind: 'hourly', minute: Number(m[1]) };
  m = e.match(/^(\d+) (\d+) \* \* \*$/);
  if (m) return { ...base, kind: 'daily', minute: Number(m[1]), hour: Number(m[2]) };
  m = e.match(/^(\d+) (\d+) \* \* 1-5$/);
  if (m) return { ...base, kind: 'weekdays', minute: Number(m[1]), hour: Number(m[2]) };
  m = e.match(/^(\d+) (\d+) \* \* ([0-6])$/);
  if (m) return { ...base, kind: 'weekly', minute: Number(m[1]), hour: Number(m[2]), dow: m[3] };
  m = e.match(/^(\d+) (\d+) (\d+) \* \*$/);
  if (m) return { ...base, kind: 'monthly', minute: Number(m[1]), hour: Number(m[2]), dom: Number(m[3]) };
  return { ...base, kind: 'custom' };
};

// ── Quick templates (pre-fill the wizard) ────────────────────────────────────
const TEMPLATES = [
  {
    key: 'inbox', icon: '✉', title: 'Inbox recap', desc: 'Daily LLM analysis of your unread emails.',
    task_type: 'agent', agent_type: 'email_expert', name: 'Inbox recap',
    input: { mode: 'analyze_inbox', limit: 20, unread_only: true },
    schedule: { kind: 'daily', hour: 8, minute: 0 }, permission_mode: 'auto',
  },
  {
    key: 'web', icon: '⊕', title: 'Web briefing', desc: 'Daily web search on a topic you follow.',
    task_type: 'agent', agent_type: 'websearch', name: 'Daily web briefing',
    input: { query: '' },
    schedule: { kind: 'daily', hour: 7, minute: 30 }, permission_mode: 'auto',
  },
  {
    key: 'legal', icon: '⚖', title: 'Legal watch', desc: 'Weekly legislative monitoring.',
    task_type: 'agent', agent_type: 'legal_fiscal', name: 'Legal watch',
    input: { mode: 'monitoring', query: '' },
    schedule: { kind: 'weekly', hour: 9, minute: 0, dow: '1' }, permission_mode: 'auto',
  },
  {
    key: 'opendata', icon: '⊗', title: 'Open data watch', desc: 'Latest updated datasets on data.gouv.fr.',
    task_type: 'agent', agent_type: 'datagouv_explorer', name: 'Open data watch',
    input: { mode: 'search', query: '', sort: '-last_update', page_size: 10 },
    schedule: { kind: 'daily', hour: 9, minute: 0 }, permission_mode: 'auto',
  },
  {
    key: 'infra', icon: '⌥', title: 'Infra health check', desc: 'Run a skill command on a remote host.',
    task_type: 'agent', agent_type: 'skill', name: 'Infra health check',
    input: { query: 'disk', host: '' },
    schedule: { kind: 'daily', hour: 6, minute: 0 }, permission_mode: 'manual',
  },
  {
    key: 'review', icon: '⎔', title: 'Nightly code review', desc: 'Review a branch every night.',
    task_type: 'agent', agent_type: 'branch_code_review', name: 'Nightly code review',
    input: { branch: '' },
    schedule: { kind: 'daily', hour: 2, minute: 0 }, permission_mode: 'manual',
  },
  {
    key: 'digest', icon: '✎', title: 'Daily digest (prompt)', desc: 'A plain LLM prompt, no agent needed.',
    task_type: 'prompt', name: 'Daily digest',
    prompt: 'Give me a concise morning briefing: three priorities for today, one thing to avoid, and one short motivational line.',
    schedule: { kind: 'daily', hour: 8, minute: 0 }, permission_mode: 'auto',
  },
];

const defaultsFor = (agent) => {
  const out = {};
  ((agent && agent.fields) || []).forEach((f) => {
    if (f.default !== undefined) out[f.name] = f.default;
  });
  return out;
};

const isVisible = (field, input) => {
  if (!field.show_when) return true;
  return Object.entries(field.show_when).every(([key, allowed]) => allowed.includes(input[key]));
};

const emptyForm = () => ({
  name: '', description: '', task_type: 'agent', agent_id: '', input: {},
  prompt: '', llm_provider: '', llm_model: '', llm_temperature: 0.5,
  schedule: { ...SCHEDULE_DEFAULT }, timezone: defaultTimezone(),
  permission_mode: 'manual', allowed_recipients: '', approval_timeout_minutes: 1440, skipTyped: '',
  notify_channels: ['in_app'], notify_on: 'always',
});

const formFromTask = (task) => ({
  name: task.name,
  description: task.description || '',
  task_type: task.task_type,
  agent_id: task.agent_id || '',
  input: task.input_data || {},
  prompt: task.prompt || '',
  llm_provider: task.llm_provider || '',
  llm_model: task.llm_model || '',
  llm_temperature: task.llm_temperature ?? 0.5,
  schedule: parseCron(task.cron_expr),
  timezone: task.timezone || 'UTC',
  permission_mode: task.permission_mode,
  allowed_recipients: (task.allowed_recipients || []).join(', '),
  approval_timeout_minutes: task.approval_timeout_minutes,
  skipTyped: task.permission_mode === 'skip_all' ? 'SKIP' : '',
  notify_channels: task.notify_channels && task.notify_channels.length ? task.notify_channels : ['in_app'],
  notify_on: task.notify_on || 'always',
});

const buildPayload = (form) => {
  const isAgent = form.task_type === 'agent';
  const temperature = Number(form.llm_temperature);
  const timeout = Number(form.approval_timeout_minutes) || 1440;
  return {
    name: form.name.trim(),
    description: form.description.trim() || null,
    task_type: form.task_type,
    agent_id: isAgent ? (form.agent_id || null) : null,
    input_data: isAgent ? form.input : {},
    prompt: isAgent ? null : form.prompt,
    llm_provider: isAgent ? null : (form.llm_provider || null),
    llm_model: isAgent ? null : (form.llm_model.trim() || null),
    llm_temperature: Number.isFinite(temperature) ? Math.min(2, Math.max(0, temperature)) : 0.5,
    cron_expr: buildCron(form.schedule),
    timezone: form.timezone,
    permission_mode: form.permission_mode,
    allowed_recipients: form.allowed_recipients.split(',').map((s) => s.trim()).filter(Boolean),
    approval_timeout_minutes: Math.min(10080, Math.max(5, timeout)),
    notify_channels: form.notify_channels,
    notify_on: form.notify_on,
    confirm_skip_all: form.permission_mode === 'skip_all' && form.skipTyped.trim().toUpperCase() === 'SKIP',
  };
};

const cleanParams = (obj) => {
  const out = {};
  Object.entries(obj).forEach(([k, v]) => {
    if (v !== '' && v !== null && v !== undefined) out[k] = v;
  });
  return out;
};

const overlayStyle = {
  position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex',
  alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 'var(--spacing-4)',
};

const sectionLabel = {
  fontSize: 'var(--text-xs)', color: 'var(--gray-600)', textTransform: 'uppercase',
  letterSpacing: '.04em', marginBottom: 'var(--spacing-2)',
};

// ─────────────────────────────────────────────────────────────────────────────
// Dynamic agent input field
// ─────────────────────────────────────────────────────────────────────────────
function DynamicField({ field, value, onChange, hosts }) {
  const label = `${field.label}${field.required ? ' *' : ''}`;
  const current = value === undefined || value === null ? '' : value;

  if (field.type === 'checkbox') {
    return (
      <div className="form-group">
        <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', fontSize: 'var(--text-sm)' }}>
          <input type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(field.name, e.target.checked)} />
          {field.label}
        </label>
      </div>
    );
  }

  let control;
  if (field.type === 'textarea') {
    control = (
      <textarea className="form-input" rows={3} value={current} placeholder={field.placeholder}
        onChange={(e) => onChange(field.name, e.target.value)} />
    );
  } else if (field.type === 'select') {
    control = (
      <select className="form-input" value={current} onChange={(e) => onChange(field.name, e.target.value)}>
        <option value="">— select —</option>
        {(field.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    );
  } else if (field.type === 'host') {
    control = (
      <select className="form-input" value={current} onChange={(e) => onChange(field.name, e.target.value)}>
        <option value="">— select a host —</option>
        {hosts.map((h) => (
          <option key={h.name} value={h.name}>
            {h.name} — {h.host} ({h.protocol}){!h.is_active ? ' [inactive]' : ''}
          </option>
        ))}
      </select>
    );
  } else if (field.type === 'number') {
    control = (
      <input type="number" className="form-input" value={current} placeholder={field.placeholder}
        min={field.min} max={field.max} onChange={(e) => onChange(field.name, e.target.value)} />
    );
  } else {
    control = (
      <input type="text" className="form-input" value={Array.isArray(current) ? current.join(', ') : current}
        placeholder={field.placeholder} onChange={(e) => onChange(field.name, e.target.value)} />
    );
  }

  return (
    <div className="form-group">
      <label className="form-label">{label}</label>
      {control}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Task wizard
// ─────────────────────────────────────────────────────────────────────────────
const STEPS = ['Target', 'Frequency', 'Permissions', 'Notifications'];

function TaskModal({ catalog, task, user, onClose, onSaved }) {
  const navigate = useNavigate();
  const isEdit = Boolean(task);
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(() => (task ? formFromTask(task) : emptyForm()));
  const [validation, setValidation] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [hint, setHint] = useState(null);

  const timezones = useMemo(() => timezoneList(), []);
  const supportedAgents = useMemo(() => catalog.agents.filter((a) => a.supported), [catalog]);
  const selectedAgent = useMemo(
    () => catalog.agents.find((a) => a.id === form.agent_id) || null,
    [catalog, form.agent_id]
  );

  const payload = useMemo(() => buildPayload(form), [form]);
  const payloadKey = JSON.stringify(payload);

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const result = await schedulerApi.validate(payload, task ? task.id : undefined);
        if (!cancelled) setValidation(result);
      } catch (e) {
        if (!cancelled) {
          setValidation({ valid: false, errors: [errorMessage(e)], manifest: [], next_runs: [], policy: null });
        }
      }
    }, 400);
    return () => { cancelled = true; clearTimeout(timer); };
    // payload is derived from form: payloadKey is the stable dependency
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [payloadKey]);

  const set = (patch) => setForm((prev) => ({ ...prev, ...patch }));
  const setSchedule = (patch) => setForm((prev) => ({ ...prev, schedule: { ...prev.schedule, ...patch } }));
  const setInput = (name, value) => setForm((prev) => ({ ...prev, input: { ...prev.input, [name]: value } }));

  const selectAgent = (agentId) => {
    const agent = catalog.agents.find((a) => a.id === agentId);
    setForm((prev) => ({ ...prev, agent_id: agentId, input: defaultsFor(agent) }));
  };

  const toggleChannel = (channel) => {
    setForm((prev) => {
      const has = prev.notify_channels.includes(channel);
      const next = has ? prev.notify_channels.filter((c) => c !== channel) : [...prev.notify_channels, channel];
      return { ...prev, notify_channels: next.length ? next : ['in_app'] };
    });
  };

  const applyTemplate = (tpl) => {
    setHint(null);
    const schedule = { ...SCHEDULE_DEFAULT, ...tpl.schedule };
    schedule.custom = buildCron(schedule);
    let agent = null;
    if (tpl.task_type === 'agent') {
      agent = supportedAgents.find((a) => a.agent_type === tpl.agent_type && a.is_active)
        || supportedAgents.find((a) => a.agent_type === tpl.agent_type)
        || null;
      if (!agent) {
        setHint(`No "${tpl.agent_type}" agent exists yet. Create one in the Agents page first, then come back.`);
      }
    }
    setForm((prev) => ({
      ...prev,
      name: prev.name.trim() ? prev.name : tpl.name,
      task_type: tpl.task_type,
      agent_id: agent ? agent.id : '',
      input: agent ? { ...defaultsFor(agent), ...tpl.input } : {},
      prompt: tpl.task_type === 'prompt' ? tpl.prompt : prev.prompt,
      schedule,
      permission_mode: tpl.permission_mode,
    }));
  };

  const canGoNext = () => {
    if (step === 0) {
      if (!form.name.trim()) return false;
      if (form.task_type === 'agent') return Boolean(form.agent_id);
      return Boolean(form.prompt.trim());
    }
    if (step === 1) return validation ? !validation.schedule_error : true;
    return true;
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const saved = isEdit
        ? await schedulerApi.updateTask(task.id, payload)
        : await schedulerApi.createTask(payload);
      onSaved(saved);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  // ── Step 0: target ─────────────────────────────────────────────────────────
  const renderTarget = () => (
    <div>
      {!isEdit && (
        <div style={{ marginBottom: 'var(--spacing-4)' }}>
          <div style={sectionLabel}>Quick templates</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 'var(--spacing-2)' }}>
            {TEMPLATES.map((tpl) => (
              <div
                key={tpl.key}
                onClick={() => applyTemplate(tpl)}
                style={{
                  border: '1px solid var(--gray-300)', borderRadius: 'var(--radius-md)', padding: 'var(--spacing-3)',
                  cursor: 'pointer', background: 'var(--bg-card)',
                }}
              >
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600 }}>{tpl.icon} {tpl.title}</div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: '2px' }}>{tpl.desc}</div>
              </div>
            ))}
          </div>
          {hint && <div style={{ marginTop: 'var(--spacing-2)', fontSize: 'var(--text-sm)', color: 'var(--warning)' }}>{hint}</div>}
        </div>
      )}

      <div className="form-group">
        <label className="form-label">Task name *</label>
        <input type="text" className="form-input" value={form.name} placeholder="Morning inbox recap"
          onChange={(e) => set({ name: e.target.value })} />
      </div>
      <div className="form-group">
        <label className="form-label">Description</label>
        <input type="text" className="form-input" value={form.description} placeholder="Optional"
          onChange={(e) => set({ description: e.target.value })} />
      </div>

      <div style={{ display: 'flex', gap: 'var(--spacing-4)', marginBottom: 'var(--spacing-4)' }}>
        {[
          { value: 'agent', label: 'Run an existing agent' },
          { value: 'prompt', label: 'Simple prompt (no agent)' },
        ].map((opt) => (
          <label key={opt.value} style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', fontSize: 'var(--text-sm)', cursor: 'pointer' }}>
            <input type="radio" name="task_type" checked={form.task_type === opt.value}
              onChange={() => set({ task_type: opt.value })} />
            {opt.label}
          </label>
        ))}
      </div>

      {form.task_type === 'agent' ? (
        <div>
          {supportedAgents.length === 0 ? (
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-700)' }}>
              No schedulable agent found.{' '}
              <button onClick={() => navigate('/agents')} style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer' }}>
                Create one in the Agents page
              </button>
            </div>
          ) : (
            <div className="form-group">
              <label className="form-label">Agent *</label>
              <select className="form-input" value={form.agent_id} onChange={(e) => selectAgent(e.target.value)}>
                <option value="">— select an agent —</option>
                {supportedAgents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} — {a.type_label}{!a.is_active ? ' [inactive]' : ''}
                  </option>
                ))}
              </select>
              {selectedAgent && !selectedAgent.is_active && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--warning)', marginTop: '4px' }}>
                  This agent is disabled: scheduled runs will fail until you re-enable it.
                </div>
              )}
            </div>
          )}
          {selectedAgent && (
            <div>
              <div style={sectionLabel}>Agent arguments</div>
              {selectedAgent.fields.filter((f) => isVisible(f, form.input)).map((f) => (
                <DynamicField key={f.name} field={f} value={form.input[f.name]} onChange={setInput} hosts={catalog.hosts} />
              ))}
            </div>
          )}
        </div>
      ) : (
        <div>
          <div className="form-group">
            <label className="form-label">Prompt *</label>
            <textarea className="form-input" rows={5} value={form.prompt}
              placeholder="What should the model do each time?"
              onChange={(e) => set({ prompt: e.target.value })} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 120px', gap: 'var(--spacing-3)' }}>
            <div className="form-group">
              <label className="form-label">Provider</label>
              <select className="form-input" value={form.llm_provider} onChange={(e) => set({ llm_provider: e.target.value })}>
                <option value="">Default (highest priority)</option>
                {catalog.providers.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Model</label>
              <input type="text" className="form-input" value={form.llm_model} placeholder="Provider default"
                onChange={(e) => set({ llm_model: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label">Temperature</label>
              <input type="number" className="form-input" step="0.1" min="0" max="2" value={form.llm_temperature}
                onChange={(e) => set({ llm_temperature: e.target.value })} />
            </div>
          </div>
        </div>
      )}
    </div>
  );

  // ── Step 1: frequency ──────────────────────────────────────────────────────
  const s = form.schedule;
  const showTime = ['daily', 'weekdays', 'weekly', 'monthly'].includes(s.kind);
  const renderFrequency = () => (
    <div>
      <div className="form-group">
        <label className="form-label">Repeat</label>
        <select className="form-input" value={s.kind}
          onChange={(e) => setSchedule({ kind: e.target.value, custom: s.kind === 'custom' ? s.custom : buildCron(s) })}>
          {PRESET_KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
        </select>
      </div>

      <div style={{ display: 'flex', gap: 'var(--spacing-3)', flexWrap: 'wrap' }}>
        {s.kind === 'every_n_minutes' && (
          <div className="form-group" style={{ width: '140px' }}>
            <label className="form-label">Every (minutes)</label>
            <input type="number" className="form-input" min={1} max={59} value={s.n}
              onChange={(e) => setSchedule({ n: e.target.value })} />
          </div>
        )}
        {s.kind === 'weekly' && (
          <div className="form-group" style={{ width: '180px' }}>
            <label className="form-label">Day</label>
            <select className="form-input" value={s.dow} onChange={(e) => setSchedule({ dow: e.target.value })}>
              {DAYS_OF_WEEK.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
            </select>
          </div>
        )}
        {s.kind === 'monthly' && (
          <div className="form-group" style={{ width: '140px' }}>
            <label className="form-label">Day of month (1–28)</label>
            <input type="number" className="form-input" min={1} max={28} value={s.dom}
              onChange={(e) => setSchedule({ dom: e.target.value })} />
          </div>
        )}
        {showTime && (
          <>
            <div className="form-group" style={{ width: '100px' }}>
              <label className="form-label">Hour</label>
              <input type="number" className="form-input" min={0} max={23} value={s.hour}
                onChange={(e) => setSchedule({ hour: e.target.value })} />
            </div>
            <div className="form-group" style={{ width: '100px' }}>
              <label className="form-label">Minute</label>
              <input type="number" className="form-input" min={0} max={59} value={s.minute}
                onChange={(e) => setSchedule({ minute: e.target.value })} />
            </div>
          </>
        )}
        {s.kind === 'hourly' && (
          <div className="form-group" style={{ width: '140px' }}>
            <label className="form-label">At minute</label>
            <input type="number" className="form-input" min={0} max={59} value={s.minute}
              onChange={(e) => setSchedule({ minute: e.target.value })} />
          </div>
        )}
      </div>

      {s.kind === 'custom' && (
        <div className="form-group">
          <label className="form-label">Cron expression (minute hour day month weekday)</label>
          <input type="text" className="form-input" value={s.custom} placeholder="0 8 * * 1-5"
            style={{ fontFamily: 'var(--font-mono, monospace)' }}
            onChange={(e) => setSchedule({ custom: e.target.value })} />
        </div>
      )}

      <div className="form-group">
        <label className="form-label">Timezone</label>
        <input type="text" className="form-input" list="scheduler-timezones" value={form.timezone}
          onChange={(e) => set({ timezone: e.target.value })} />
        <datalist id="scheduler-timezones">
          {timezones.map((tz) => <option key={tz} value={tz} />)}
        </datalist>
      </div>

      <div style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-700)' }}>
        Cron: <code>{payload.cron_expr || '—'}</code>
        {catalog.min_interval_minutes ? ` · minimum interval ${catalog.min_interval_minutes} min` : ''}
      </div>

      <div style={{ marginTop: 'var(--spacing-3)' }}>
        <div style={sectionLabel}>Next occurrences</div>
        {validation && validation.schedule_error ? (
          <div style={{ color: 'var(--danger)', fontSize: 'var(--text-sm)' }}>{validation.schedule_error}</div>
        ) : (
          <ul style={{ fontSize: 'var(--text-sm)', paddingLeft: 'var(--spacing-5)' }}>
            {((validation && validation.next_runs) || []).map((iso) => (
              <li key={iso}>{fmt(iso, form.timezone)}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );

  // ── Step 2: permissions ────────────────────────────────────────────────────
  const MODE_OPTIONS = [
    {
      value: 'manual', title: 'Manual — ask me first',
      desc: 'Before a run that reads external data, sends something or executes remotely, you receive a notification and must approve it. Unapproved runs expire.',
    },
    {
      value: 'auto', title: 'Auto — run to the end, no question',
      desc: 'Runs without asking, inside the perimeter of the agent. Emails to third parties are refused unless their address is in the allowed list below.',
    },
    {
      value: 'skip_all', title: 'Skip all approval — no guardrail',
      desc: 'Everything the agent does is allowed, including actions outside the perimeter (e.g. emailing anyone, committing code). Use with care.',
    },
  ];

  const renderPermissions = () => (
    <div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-4)' }}>
        {MODE_OPTIONS.map((opt) => {
          const active = form.permission_mode === opt.value;
          const accent = opt.value === 'skip_all' ? 'var(--danger)' : 'var(--primary)';
          return (
            <label
              key={opt.value}
              style={{
                display: 'flex', gap: 'var(--spacing-3)', alignItems: 'flex-start', cursor: 'pointer',
                border: `1px solid ${active ? accent : 'var(--gray-300)'}`, borderRadius: 'var(--radius-md)',
                padding: 'var(--spacing-3)', background: 'var(--bg-card)',
              }}
            >
              <input type="radio" name="permission_mode" checked={active}
                onChange={() => set({ permission_mode: opt.value })} style={{ marginTop: '4px' }} />
              <div>
                <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)' }}>{opt.title}</div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: '2px' }}>{opt.desc}</div>
              </div>
            </label>
          );
        })}
      </div>

      {form.permission_mode === 'manual' && (
        <div className="form-group" style={{ maxWidth: '260px' }}>
          <label className="form-label">Approval expires after (minutes)</label>
          <input type="number" className="form-input" min={5} max={10080} value={form.approval_timeout_minutes}
            onChange={(e) => set({ approval_timeout_minutes: e.target.value })} />
        </div>
      )}

      {form.permission_mode === 'auto' && (
        <div className="form-group">
          <label className="form-label">Allowed email recipients (comma-separated)</label>
          <input type="text" className="form-input" value={form.allowed_recipients}
            placeholder={`${user && user.email ? user.email : 'you@example.com'} is always allowed`}
            onChange={(e) => set({ allowed_recipients: e.target.value })} />
        </div>
      )}

      {form.permission_mode === 'skip_all' && (
        <div className="form-group" style={{ border: '1px solid var(--danger)', borderRadius: 'var(--radius-md)', padding: 'var(--spacing-3)' }}>
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--danger)', marginBottom: 'var(--spacing-2)' }}>
            No approval and no perimeter check will be applied to this task. Type SKIP to confirm.
          </div>
          <input type="text" className="form-input" value={form.skipTyped} placeholder="SKIP"
            onChange={(e) => set({ skipTyped: e.target.value })} />
        </div>
      )}

      <div style={sectionLabel}>What this task will do</div>
      {validation && validation.manifest && validation.manifest.length > 0 ? (
        <ul style={{ fontSize: 'var(--text-sm)', paddingLeft: 'var(--spacing-5)' }}>
          {validation.manifest.map((a, i) => (
            <li key={i}>
              {a.label} <span style={{ color: 'var(--gray-600)' }}>({KIND_LABELS[a.kind] || a.kind})</span>
            </li>
          ))}
        </ul>
      ) : (
        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)' }}>Select a valid target first.</div>
      )}
      {validation && validation.policy && (
        <div style={{ fontSize: 'var(--text-sm)', marginTop: 'var(--spacing-2)', color: 'var(--gray-700)' }}>
          Policy: <strong>{validation.policy.outcome}</strong> — {validation.policy.reason}
        </div>
      )}
    </div>
  );

  // ── Step 3: notifications + review ─────────────────────────────────────────
  const renderNotifications = () => (
    <div>
      <div style={sectionLabel}>Send the result via</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-4)' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', fontSize: 'var(--text-sm)' }}>
          <input type="checkbox" checked={form.notify_channels.includes('in_app')} onChange={() => toggleChannel('in_app')} />
          In-app notification
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', fontSize: 'var(--text-sm)', opacity: catalog.smtp_enabled ? 1 : 0.6 }}>
          <input type="checkbox" checked={form.notify_channels.includes('email')} disabled={!catalog.smtp_enabled}
            onChange={() => toggleChannel('email')} />
          Email to {catalog.user_email || (user && user.email) || 'your account address'}
        </label>
        {!catalog.smtp_enabled && (
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--warning)' }}>
            Email is not configured on this platform (SMTP_HOST is empty): ask your administrator to enable it.
          </div>
        )}
      </div>

      <div className="form-group" style={{ maxWidth: '280px' }}>
        <label className="form-label">Notify</label>
        <select className="form-input" value={form.notify_on} onChange={(e) => set({ notify_on: e.target.value })}>
          <option value="always">On success and failure</option>
          <option value="success">Only on success</option>
          <option value="failure">Only on failure</option>
        </select>
      </div>

      <div style={sectionLabel}>Summary</div>
      <div style={{ fontSize: 'var(--text-sm)', lineHeight: 1.8 }}>
        <div><strong>{form.name || '—'}</strong> · {form.task_type === 'agent' ? (selectedAgent ? selectedAgent.name : 'no agent') : 'prompt'}</div>
        <div>Schedule: <code>{payload.cron_expr}</code> ({form.timezone})</div>
        <div>First run: {validation && validation.next_runs && validation.next_runs[0] ? fmt(validation.next_runs[0], form.timezone) : '—'}</div>
        <div>Permission: <ModePill mode={form.permission_mode} /></div>
      </div>
    </div>
  );

  const errors = (validation && validation.errors) || [];
  const isLast = step === STEPS.length - 1;

  return (
    <div style={overlayStyle}>
      <div className="card" style={{ width: '100%', maxWidth: '820px', maxHeight: '92vh', overflow: 'auto' }}>
        <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 600, marginBottom: 'var(--spacing-3)' }}>
          {isEdit ? 'Edit scheduled task' : 'New scheduled task'}
        </h2>

        <div style={{ display: 'flex', gap: 'var(--spacing-1)', marginBottom: 'var(--spacing-4)', borderBottom: '1px solid var(--gray-200)' }}>
          {STEPS.map((label, i) => (
            <button
              key={label}
              onClick={() => setStep(i)}
              style={{
                padding: 'var(--spacing-2) var(--spacing-3)', background: 'none', border: 'none', cursor: 'pointer',
                fontSize: 'var(--text-sm)', fontWeight: step === i ? 600 : 400,
                color: step === i ? 'var(--primary)' : 'var(--gray-600)',
                borderBottom: step === i ? '2px solid var(--primary)' : '2px solid transparent', marginBottom: '-1px',
              }}
            >
              {i + 1}. {label}
            </button>
          ))}
        </div>

        {step === 0 && renderTarget()}
        {step === 1 && renderFrequency()}
        {step === 2 && renderPermissions()}
        {step === 3 && renderNotifications()}

        {errors.length > 0 && (
          <div style={{ marginTop: 'var(--spacing-4)', fontSize: 'var(--text-sm)', color: 'var(--danger)' }}>
            <div style={{ fontWeight: 600 }}>To fix before saving:</div>
            <ul style={{ paddingLeft: 'var(--spacing-5)' }}>
              {errors.map((msg, i) => <li key={i}>{msg}</li>)}
            </ul>
          </div>
        )}
        {error && <div style={{ marginTop: 'var(--spacing-3)', color: 'var(--danger)', fontSize: 'var(--text-sm)' }}>{error}</div>}

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 'var(--spacing-5)' }}>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
            {step > 0 && <Button variant="ghost" onClick={() => setStep(step - 1)}>Back</Button>}
            {!isLast && <Button variant="primary" disabled={!canGoNext()} onClick={() => setStep(step + 1)}>Next</Button>}
            {isLast && (
              <Button variant="primary" loading={saving} disabled={!validation || !validation.valid} onClick={handleSave}>
                {isEdit ? 'Save changes' : 'Create task'}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Tasks tab
// ─────────────────────────────────────────────────────────────────────────────
function TasksTab({ tasks, onNew, onEdit, onRun, onToggle, onDelete }) {
  if (tasks.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 'var(--spacing-12)', color: 'var(--gray-600)' }}>
        <div style={{ fontSize: '3rem', marginBottom: 'var(--spacing-3)' }}>⏰</div>
        <h3 style={{ fontSize: 'var(--text-xl)', fontWeight: 600, marginBottom: 'var(--spacing-2)' }}>No scheduled tasks yet</h3>
        <p style={{ marginBottom: 'var(--spacing-4)', fontSize: 'var(--text-sm)' }}>
          Run your agents automatically, or schedule a simple prompt.
        </p>
        <Button variant="primary" icon={Plus} onClick={onNew}>Create your first task</Button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
      {tasks.map((t) => (
        <div key={t.id} className="card" style={{ opacity: t.is_enabled ? 1 : 0.6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--spacing-3)', flexWrap: 'wrap' }}>
            <div style={{ minWidth: '260px', flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', flexWrap: 'wrap' }}>
                <span style={{ fontWeight: 600 }}>{t.name}</span>
                <ModePill mode={t.permission_mode} />
                {t.last_run_status && <StatusPill status={t.last_run_status} />}
                {!t.is_enabled && <Pill color="var(--gray-700)" bg="rgba(163,163,163,.15)">Disabled</Pill>}
              </div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: '4px' }}>
                {t.task_type === 'agent' ? `Agent: ${t.agent_name || '—'} (${t.agent_type || '—'})` : 'Simple prompt'}
                {t.description ? ` · ${t.description}` : ''}
              </div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: '2px' }}>
                <code>{t.cron_expr}</code> ({t.timezone}) · Next: {t.is_enabled ? fmt(t.next_run_at, t.timezone) : '—'} · Last: {fmt(t.last_run_at)}
              </div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: '2px' }}>
                Notifications: {(t.notify_channels || []).join(' + ') || 'none'} ({t.notify_on})
              </div>
            </div>
            <div style={{ display: 'flex', gap: 'var(--spacing-1)', alignItems: 'flex-start' }}>
              <Button variant="ghost" size="sm" icon={Play} onClick={() => onRun(t)}>Run now</Button>
              <Button variant="ghost" size="sm" icon={Power} onClick={() => onToggle(t)}>{t.is_enabled ? 'Disable' : 'Enable'}</Button>
              <Button variant="ghost" size="sm" icon={Pencil} onClick={() => onEdit(t)}>Edit</Button>
              <Button variant="ghost" size="sm" icon={Trash2} onClick={() => onDelete(t)}>Delete</Button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Runs tab
// ─────────────────────────────────────────────────────────────────────────────
function RunRow({ run, expanded, onToggle, onApprove, onReject }) {
  const navigate = useNavigate();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!expanded) return undefined;
    let cancelled = false;
    setLoading(true);
    schedulerApi.getRun(run.id)
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch(() => { /* the list row stays usable */ })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [expanded, run.id, run.status]);

  const actions = detail && detail.approval_manifest && detail.approval_manifest.actions;

  return (
    <div className="card" style={{ padding: 'var(--spacing-3)' }}>
      <div onClick={onToggle} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', gap: 'var(--spacing-3)', flexWrap: 'wrap' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)' }}>{run.task_name || 'Task'}</span>
            <StatusPill status={run.status} />
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)' }}>{run.triggered_by}</span>
          </div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: '2px' }}>
            {fmt(run.started_at || run.created_at)} {duration(run) ? `· ${duration(run)}` : ''}
            {run.status === 'awaiting_approval' && run.approval_expires_at ? ` · expires ${fmt(run.approval_expires_at)}` : ''}
          </div>
        </div>
        {run.status === 'awaiting_approval' && (
          <div style={{ display: 'flex', gap: 'var(--spacing-2)' }} onClick={(e) => e.stopPropagation()}>
            <Button variant="success" size="sm" icon={Check} onClick={() => onApprove(run)}>Approve</Button>
            <Button variant="danger" size="sm" icon={X} onClick={() => onReject(run)}>Reject</Button>
          </div>
        )}
      </div>

      {expanded && (
        <div style={{ marginTop: 'var(--spacing-3)', borderTop: '1px solid var(--gray-200)', paddingTop: 'var(--spacing-3)' }}>
          {loading && !detail && <Loading size="sm" message="Loading run..." />}
          {run.error && <div style={{ color: 'var(--danger)', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-2)' }}>{run.error}</div>}
          {actions && actions.length > 0 && (
            <div style={{ marginBottom: 'var(--spacing-3)' }}>
              <div style={sectionLabel}>Actions awaiting your approval</div>
              <ul style={{ fontSize: 'var(--text-sm)', paddingLeft: 'var(--spacing-5)' }}>
                {actions.map((a, i) => <li key={i}>{a.label}</li>)}
              </ul>
            </div>
          )}
          {detail && detail.result_text && (
            <div style={{ maxHeight: '420px', overflow: 'auto' }}>
              <MarkdownMessage content={detail.result_text} />
            </div>
          )}
          {detail && detail.conversation_id && (
            <div style={{ marginTop: 'var(--spacing-2)' }}>
              <Button variant="ghost" size="sm" icon={MessageCircle} onClick={() => navigate(`/chat/${detail.conversation_id}`)}>
                Open conversation
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function RunsTab({ runs, tasks, filter, setFilter, expandedId, setExpandedId, onApprove, onReject }) {
  return (
    <div>
      <div style={{ display: 'flex', gap: 'var(--spacing-3)', marginBottom: 'var(--spacing-4)', flexWrap: 'wrap' }}>
        <select className="form-input" style={{ maxWidth: '260px' }} value={filter.task_id}
          onChange={(e) => setFilter({ ...filter, task_id: e.target.value })}>
          <option value="">All tasks</option>
          {tasks.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <select className="form-input" style={{ maxWidth: '220px' }} value={filter.status}
          onChange={(e) => setFilter({ ...filter, status: e.target.value })}>
          <option value="">All statuses</option>
          {Object.entries(STATUS_STYLES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </div>
      {runs.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 'var(--spacing-8)', color: 'var(--gray-600)', fontSize: 'var(--text-sm)' }}>
          No runs yet.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
          {runs.map((r) => (
            <RunRow
              key={r.id}
              run={r}
              expanded={expandedId === r.id}
              onToggle={() => setExpandedId(expandedId === r.id ? null : r.id)}
              onApprove={onApprove}
              onReject={onReject}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Inbox tab
// ─────────────────────────────────────────────────────────────────────────────
function InboxTab({ notifications, onRead, onReadAll, onDelete, onOpenRun }) {
  const [openId, setOpenId] = useState(null);
  const unread = notifications.filter((n) => !n.is_read).length;

  if (notifications.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 'var(--spacing-8)', color: 'var(--gray-600)', fontSize: 'var(--text-sm)' }}>
        No notifications.
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-3)' }}>
        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)' }}>{unread} unread</span>
        {unread > 0 && <Button variant="ghost" size="sm" icon={Check} onClick={onReadAll}>Mark all as read</Button>}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
        {notifications.map((n) => {
          const open = openId === n.id;
          return (
            <div key={n.id} className="card" style={{ padding: 'var(--spacing-3)', borderLeft: n.is_read ? '3px solid transparent' : '3px solid var(--primary)' }}>
              <div
                onClick={() => { setOpenId(open ? null : n.id); if (!n.is_read) onRead(n); }}
                style={{ display: 'flex', justifyContent: 'space-between', cursor: 'pointer', gap: 'var(--spacing-3)', flexWrap: 'wrap' }}
              >
                <div>
                  <div style={{ fontWeight: n.is_read ? 400 : 600, fontSize: 'var(--text-sm)' }}>{n.title}</div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)' }}>
                    {fmt(n.created_at)}
                    {n.email_status ? ` · email ${n.email_status}${n.email_error ? ` (${n.email_error})` : ''}` : ''}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 'var(--spacing-1)' }} onClick={(e) => e.stopPropagation()}>
                  {n.run_id && <Button variant="ghost" size="sm" onClick={() => onOpenRun(n)}>Open run</Button>}
                  <Button variant="ghost" size="sm" icon={Trash2} onClick={() => onDelete(n)}>Delete</Button>
                </div>
              </div>
              {open && n.body && (
                <div style={{ marginTop: 'var(--spacing-3)', borderTop: '1px solid var(--gray-200)', paddingTop: 'var(--spacing-3)', maxHeight: '360px', overflow: 'auto' }}>
                  <MarkdownMessage content={n.body} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────────────────────────────
export default function Scheduler() {
  const { user } = useAuthStore();
  const [searchParams] = useSearchParams();

  const [tab, setTab] = useState('tasks');
  const [catalog, setCatalog] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [runs, setRuns] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  // undefined: modal closed · null: creating · object: editing
  const [modalTask, setModalTask] = useState(undefined);
  const [expandedRun, setExpandedRun] = useState(null);
  const [runFilter, setRunFilter] = useState({ task_id: '', status: '' });

  const loadAll = useCallback(async (silent = false) => {
    try {
      const [t, r, n] = await Promise.all([
        schedulerApi.listTasks(),
        schedulerApi.listRuns(cleanParams({ ...runFilter, limit: 100 })),
        schedulerApi.listNotifications({ limit: 100 }),
      ]);
      setTasks(t);
      setRuns(r);
      setNotifications(n);
    } catch (e) {
      if (!silent) setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [runFilter]);

  useEffect(() => { loadAll(); }, [loadAll]);

  // Keep the Sidebar badge in sync with what this page knows
  useEffect(() => {
    window.dispatchEvent(new Event('notifications-changed'));
  }, [notifications]);

  // Light polling (no websocket): refresh while the page is visible and no modal is open
  useEffect(() => {
    const id = setInterval(() => {
      if (document.visibilityState === 'visible' && modalTask === undefined) loadAll(true);
    }, 15000);
    return () => clearInterval(id);
  }, [loadAll, modalTask]);

  // Deep link from notification emails: /scheduler?run=<id>
  useEffect(() => {
    const runId = searchParams.get('run');
    if (runId) {
      setTab('runs');
      setExpandedRun(runId);
    }
    // only on first mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openModal = async (task) => {
    try {
      setCatalog(await schedulerApi.catalog()); // fresh list of agents / hosts every time
      setModalTask(task || null);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const handleSaved = (saved) => {
    setModalTask(undefined);
    setSuccess(`Task "${saved.name}" saved`);
    loadAll(true);
  };

  const handleRun = async (task) => {
    try {
      await schedulerApi.runTask(task.id, false);
      setSuccess(`"${task.name}" queued: the worker will pick it up within a few seconds`);
      loadAll(true);
    } catch (e) {
      const status = e && e.response && e.response.status;
      const detail = e && e.response && e.response.data && e.response.data.detail;
      if (status === 409 && detail && detail.code === 'confirmation_required') {
        const lines = (detail.manifest || []).map((a) => `• ${a.label}`).join('\n');
        if (window.confirm(`This run will:\n${lines}\n\nProceed?`)) {
          try {
            await schedulerApi.runTask(task.id, true);
            setSuccess(`"${task.name}" queued`);
            loadAll(true);
          } catch (e2) {
            setError(errorMessage(e2));
          }
        }
      } else {
        setError(errorMessage(e));
      }
    }
  };

  const handleToggle = async (task) => {
    try {
      await schedulerApi.toggleTask(task.id);
      loadAll(true);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const handleDelete = async (task) => {
    if (!window.confirm(`Delete "${task.name}" and its run history?`)) return;
    try {
      await schedulerApi.deleteTask(task.id);
      setSuccess(`Task "${task.name}" deleted`);
      loadAll(true);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const handleApprove = async (run) => {
    try {
      await schedulerApi.approveRun(run.id);
      setSuccess('Run approved: it will start within a few seconds');
      loadAll(true);
    } catch (e) {
      setError(errorMessage(e));
      loadAll(true);
    }
  };

  const handleReject = async (run) => {
    try {
      await schedulerApi.rejectRun(run.id);
      loadAll(true);
    } catch (e) {
      setError(errorMessage(e));
      loadAll(true);
    }
  };

  const handleRead = async (n) => {
    try {
      await schedulerApi.markRead(n.id);
      setNotifications((prev) => prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)));
    } catch (_) { /* non blocking */ }
  };

  const handleReadAll = async () => {
    try {
      await schedulerApi.markAllRead();
      setNotifications((prev) => prev.map((x) => ({ ...x, is_read: true })));
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const handleDeleteNotification = async (n) => {
    try {
      await schedulerApi.deleteNotification(n.id);
      setNotifications((prev) => prev.filter((x) => x.id !== n.id));
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const handleOpenRun = (n) => {
    if (!n.is_read) handleRead(n);
    setTab('runs');
    setExpandedRun(n.run_id);
  };

  if (loading) return <Layout><Loading /></Layout>;

  const enabledCount = tasks.filter((t) => t.is_enabled).length;
  const pendingApprovals = runs.filter((r) => r.status === 'awaiting_approval').length;
  const unreadCount = notifications.filter((n) => !n.is_read).length;

  const TABS = [
    { key: 'tasks', label: 'Tasks' },
    { key: 'runs', label: pendingApprovals ? `Runs (${pendingApprovals} to approve)` : 'Runs' },
    { key: 'inbox', label: unreadCount ? `Inbox (${unreadCount})` : 'Inbox' },
  ];

  return (
    <Layout>
      <div style={{ padding: 'var(--spacing-6)', maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--spacing-5)' }}>
          <div>
            <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, marginBottom: 'var(--spacing-1)' }}>Scheduler</h1>
            <p style={{ color: 'var(--gray-600)', fontSize: 'var(--text-sm)' }}>
              Run your agents or simple prompts on a schedule, with approval rules and notifications
            </p>
          </div>
          <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
            <Button variant="ghost" icon={RefreshCw} onClick={() => loadAll()}>Refresh</Button>
            <Button variant="primary" icon={Plus} onClick={() => openModal(null)}>New task</Button>
          </div>
        </div>

        {error && <Alert type="error" message={error} onClose={() => setError(null)} />}
        {success && <Alert type="success" message={success} onClose={() => setSuccess(null)} />}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--spacing-3)', margin: 'var(--spacing-4) 0 var(--spacing-5)' }}>
          {[
            { label: 'Tasks', value: tasks.length, color: 'var(--gray-800)' },
            { label: 'Enabled', value: enabledCount, color: 'var(--success)' },
            { label: 'Awaiting approval', value: pendingApprovals, color: 'var(--warning)' },
            { label: 'Unread', value: unreadCount, color: 'var(--primary)' },
          ].map((stat) => (
            <div key={stat.label} style={{ background: 'var(--gray-100)', border: '1px solid var(--gray-200)', borderRadius: 'var(--radius)', padding: 'var(--spacing-3)', textAlign: 'center' }}>
              <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: stat.color }}>{stat.value}</div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: '2px' }}>{stat.label}</div>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', borderBottom: '1px solid var(--gray-200)', marginBottom: 'var(--spacing-5)', gap: 'var(--spacing-1)' }}>
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              style={{
                padding: 'var(--spacing-2) var(--spacing-4)', background: 'none', border: 'none', cursor: 'pointer',
                fontSize: 'var(--text-sm)', fontWeight: tab === t.key ? 600 : 400,
                color: tab === t.key ? 'var(--primary)' : 'var(--gray-600)',
                borderBottom: tab === t.key ? '2px solid var(--primary)' : '2px solid transparent', marginBottom: '-1px',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'tasks' && (
          <TasksTab
            tasks={tasks}
            onNew={() => openModal(null)}
            onEdit={(t) => openModal(t)}
            onRun={handleRun}
            onToggle={handleToggle}
            onDelete={handleDelete}
          />
        )}
        {tab === 'runs' && (
          <RunsTab
            runs={runs}
            tasks={tasks}
            filter={runFilter}
            setFilter={setRunFilter}
            expandedId={expandedRun}
            setExpandedId={setExpandedRun}
            onApprove={handleApprove}
            onReject={handleReject}
          />
        )}
        {tab === 'inbox' && (
          <InboxTab
            notifications={notifications}
            onRead={handleRead}
            onReadAll={handleReadAll}
            onDelete={handleDeleteNotification}
            onOpenRun={handleOpenRun}
          />
        )}

        {modalTask !== undefined && catalog && (
          <TaskModal
            catalog={catalog}
            task={modalTask}
            user={user}
            onClose={() => setModalTask(undefined)}
            onSaved={handleSaved}
          />
        )}
      </div>
    </Layout>
  );
}
