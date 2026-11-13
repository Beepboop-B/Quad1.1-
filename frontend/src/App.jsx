import {useEffect, useMemo, useState} from 'react';
import {NavLink, Route, Routes, useLocation} from 'react-router-dom';
import axios from 'axios';
import {
  Activity, AlertTriangle, BarChart3, Bell, Building2, CheckCircle2,
  ChevronDown, CircleHelp, Clock3, Command, Cpu, Filter, LayoutDashboard,
  LifeBuoy, Menu, Plus, Search, Settings, Shield, SlidersHorizontal, Users, Wifi, X, ArrowRight
} from 'lucide-react';
import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie,
  PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis
} from 'recharts';

const api = axios.create({baseURL: import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000/api'});

const nav = [
  ['Overview', '/', 'grid'],
  ['Submit a report', '/submit', 'plus'],
  ['My reports', '/my-reports', 'activity'],
  ['Handler console', '/handlers', 'users'],
  ['Routing management', '/routing', 'route'],
  ['Analytics', '/analytics', 'chart'],
  ['DFA Simulator', '/dfa-simulator', 'cpu'],
];

const icons = {
  grid: LayoutDashboard,
  plus: Plus,
  activity: Activity,
  users: Users,
  route: Building2,
  chart: BarChart3,
  cpu: Cpu,
};

const colors = ['#6ea8fe', '#64c8a1', '#ffbd69', '#be9cff', '#ff7b85', '#9ca3af'];
const fmt = (s) => (s ? new Date(s).toLocaleString([], {dateStyle: 'medium', timeStyle: 'short'}) : '—');

function Badge({children}) {
  return <span className={'badge ' + String(children || '').toLowerCase().replaceAll(' ', '-')}>{children}</span>;
}

function useData(url, interval = 0) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const load = () =>
    api.get(url)
      .then((r) => {
        setData(r.data);
        setError('');
      })
      .catch(() => setError('Could not connect to the service. Check that the backend is running.'));

  useEffect(() => {
    load();
    if (interval) {
      const t = setInterval(load, interval);
      return () => clearInterval(t);
    }
  }, [url]);

  return {data, error, refresh: load};
}

function Shell({children}) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const title = nav.find((n) => n[1] === location.pathname)?.[0] || 'Operations';

  return (
    <div className="app-shell">
      <aside className={'sidebar ' + (open ? 'open' : '')}>
        <div className="brand">
          <div className="brand-icon">
            <Shield size={20} />
          </div>
          <div>
            <strong>Sentinel</strong>
            <small>ATM LOGGER & DISPATCHER</small>
          </div>
          <button className="icon-button close-nav" onClick={() => setOpen(false)}>
            <X size={18} />
          </button>
        </div>
        <div className="side-label">WORKSPACE</div>
        <nav>
          {nav.map(([label, path, icon]) => {
            const Icon = icons[icon];
            return (
              <NavLink end={path === '/'} key={path} to={path} onClick={() => setOpen(false)}>
                <Icon size={17} />
                <span>{label}</span>
                {path === '/handlers' && <b className="nav-dot" />}
              </NavLink>
            );
          })}
        </nav>
        <div className="side-bottom">
          <div className="side-label">SYSTEM</div>
          <NavLink to="/settings">
            <Settings size={17} />
            <span>Settings</span>
          </NavLink>
          <div className="user-card">
            <div className="avatar">OP</div>
            <div>
              <strong>Operations Team</strong>
              <small>Administrator</small>
            </div>
            <ChevronDown size={15} />
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="top-left">
            <button className="icon-button mobile-menu" onClick={() => setOpen(true)}>
              <Menu size={20} />
            </button>
            <div className="crumb">
              Workspace <span>/</span> <b>{title}</b>
            </div>
          </div>
          <div className="top-actions">
            <div className="system-state">
              <i />
              BCS503 (DFA) & BCS502 (Networks) Active
            </div>
            <button className="icon-button">
              <Search size={18} />
            </button>
            <button className="icon-button notification">
              <Bell size={18} />
              <i />
            </button>
            <div className="avatar small-avatar">OP</div>
          </div>
        </header>
        <section className="page">{children}</section>
      </main>
    </div>
  );
}

function PageHeading({eyebrow, title, description, action}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}

function ErrorBox({children}) {
  return children ? (
    <div className="error-box">
      <AlertTriangle size={16} />
      {children}
    </div>
  ) : null;
}

function Stat({label, value, sub, icon: Icon, tint = 'blue'}) {
  return (
    <div className="stat-card">
      <div className={'stat-icon ' + tint}>
        <Icon size={18} />
      </div>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value ?? '—'}</div>
      <div className="stat-sub">{sub}</div>
    </div>
  );
}

function ReportsTable({rows = [], compact = false}) {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('All statuses');
  const [sort, setSort] = useState('newest');

  const filtered = useMemo(
    () =>
      rows
        .filter(
          (r) =>
            `${r.id} ${r.atm_id} ${r.category} ${r.zone} ${r.handler || ''}`
              .toLowerCase()
              .includes(query.toLowerCase()) &&
            (status === 'All statuses' || r.status === status)
        )
        .sort((a, b) =>
          sort === 'newest'
            ? b.created_at.localeCompare(a.created_at)
            : a.created_at.localeCompare(b.created_at)
        ),
    [rows, query, status, sort]
  );

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <h3>Recent reports</h3>
          <p>Live incidents from across the network</p>
        </div>
        <div className="table-tools">
          <label className="search-field">
            <Search size={15} />
            <input
              placeholder="Search reports"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option>All statuses</option>
            {['Pending', 'Assigned', 'In Progress', 'Resolved'].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
          <button className="icon-button filter-btn">
            <SlidersHorizontal size={16} />
          </button>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>REPORT ID</th>
              <th>ATM / ZONE</th>
              <th>CATEGORY</th>
              <th>PRIORITY</th>
              <th>STATUS</th>
              <th>ASSIGNED TO</th>
              <th>
                <button
                  className="sort-button"
                  onClick={() => setSort(sort === 'newest' ? 'oldest' : 'newest')}
                >
                  SUBMITTED ↕
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, compact ? 6 : 100).map((r) => (
              <tr key={r.id}>
                <td>
                  <a href={'/my-reports?id=' + r.id} className="report-link">
                    {r.id}
                  </a>
                </td>
                <td>
                  <strong>{r.atm_id}</strong>
                  <small>{r.zone} Zone</small>
                </td>
                <td>{r.category}</td>
                <td>
                  <Badge>{r.priority}</Badge>
                </td>
                <td>
                  <Badge>{r.status}</Badge>
                </td>
                <td>{r.handler || <span className="muted">Queue</span>}</td>
                <td>{fmt(r.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!filtered.length && (
          <div className="empty-state">
            <Search size={22} />
            <strong>No matching reports</strong>
            <span>Try changing the search or status filter.</span>
          </div>
        )}
      </div>
      {compact && (
        <a href="/my-reports" className="table-footer">
          View all reports <span>→</span>
        </a>
      )}
    </div>
  );
}

function Overview() {
  const {data: stats, error} = useData('/analytics', 30000);
  const {data: reports} = useData('/reports', 30000);
  const {data: handlers} = useData('/handlers', 30000);

  return (
    <>
      <PageHeading
        eyebrow={new Date().toLocaleDateString(undefined, {
          weekday: 'long',
          year: 'numeric',
          month: 'long',
          day: 'numeric',
        }).toUpperCase()}
        title="Good morning, Operations"
        description="Automata-validated and network-routed ATM incident management."
        action={
          <a href="/submit" className="button primary">
            <Plus size={16} /> New report
          </a>
        }
      />
      <ErrorBox>{error}</ErrorBox>
      <div className="stat-grid">
        <Stat label="Total reports" value={stats?.total ?? '—'} sub="All submitted incidents" icon={Activity} />
        <Stat label="Pending" value={stats?.pending ?? '—'} sub="Awaiting dispatch / queue" icon={Clock3} tint="amber" />
        <Stat label="In progress" value={stats?.in_progress ?? '—'} sub="Being investigated" icon={Wifi} tint="purple" />
        <Stat label="Resolved" value={stats?.resolved ?? '—'} sub="Successfully closed" icon={CheckCircle2} tint="green" />
      </div>

      <div className="overview-grid">
        <div className="panel chart-panel">
          <div className="panel-head">
            <div>
              <h3>Incident activity</h3>
              <p>Reports received by day</p>
            </div>
            <span className="period-chip">
              Last 14 days <ChevronDown size={13} />
            </span>
          </div>
          <div className="chart-area">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={[...(stats?.daily || [])].reverse()} margin={{top: 12, right: 12, left: -22, bottom: 0}}>
                <CartesianGrid stroke="#edf0f4" vertical={false} />
                <XAxis dataKey="name" tickFormatter={(x) => x.slice(5)} tickLine={false} axisLine={false} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#3579e8" strokeWidth={2.5} dot={{r: 3, fill: '#3579e8'}} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel zone-panel">
          <div className="panel-head">
            <div>
              <h3>Zone & Desk distribution</h3>
              <p>Active handler capacity</p>
            </div>
            <button className="icon-button">
              <Filter size={16} />
            </button>
          </div>
          <div className="zone-list">
            {(handlers || []).map((h, i) => (
              <div className="zone-row" key={h.id}>
                <div className="zone-name">
                  <i style={{background: colors[i % colors.length]}} />
                  {h.zone}
                </div>
                <div className="zone-load">
                  <span>{h.load} / {h.capacity}</span>
                  <div className="progress">
                    <i
                      style={{
                        width: `${Math.min(100, (h.load / h.capacity) * 100)}%`,
                        background: colors[i % colors.length],
                      }}
                    />
                  </div>
                </div>
                <Badge>{h.available ? 'Available' : 'Unavailable'}</Badge>
              </div>
            ))}
          </div>
          <a href="/routing" className="table-footer">
            Manage routing <span>→</span>
          </a>
        </div>
      </div>

      <ReportsTable rows={reports || []} compact />
    </>
  );
}

function Field({label, error, hint, ...props}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input {...props} />
      {error && <small className="field-error">{error}</small>}
      {hint && !error && <small className="field-hint">{hint}</small>}
    </label>
  );
}

function Submit() {
  const [form, setForm] = useState({
    reporter_name: '',
    reporter_contact: '',
    atm_id: '',
    error_code: '',
    urgency: 'Low',
    description: '',
  });
  const [validation, setValidation] = useState(null);
  const [fields, setFields] = useState({});
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => {
      if (form.atm_id || form.error_code || form.description) {
        api.post('/validate', form)
          .then((r) => setValidation(r.data))
          .catch(() => {});
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [form]);

  const change = (e) => {
    setForm({...form, [e.target.name]: e.target.value});
    setFields({...fields, [e.target.name]: ''});
    setError('');
  };

  async function submit(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const r = await api.post('/reports', form);
      setResult(r.data);
      setFields({});
      setForm({
        reporter_name: '',
        reporter_contact: '',
        atm_id: '',
        error_code: '',
        urgency: 'Low',
        description: '',
      });
    } catch (e) {
      if (e.response?.data?.fields) setFields(e.response.data.fields);
      setError(e.response?.data?.error || 'Report submission failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageHeading
        eyebrow="INCIDENT MANAGEMENT (PART C)"
        title="Submit a report"
        description="Log an ATM incident with dual DFA & Regex validation and automatic regional dispatch."
      />
      <ErrorBox>{error}</ErrorBox>
      {result && (
        <div className="success-box">
          <CheckCircle2 size={19} />
          <div>
            <strong>Report submitted successfully!</strong>
            <span>
              Unique Report ID: <b>{result.id}</b>. Status: <b>{result.status}</b>.
              {result.handler ? ` Assigned to: ${result.handler}.` : ' Placed in waiting/triage queue.'}
            </span>
          </div>
          <button className="icon-button" onClick={() => setResult(null)}>
            <X size={16} />
          </button>
        </div>
      )}

      <div className="form-layout">
        <form className="panel report-form" onSubmit={submit}>
          {/* Section 1: Reporter Details */}
          <div className="form-section">
            <div className="section-number">01</div>
            <div className="section-content">
              <h3>Reporter details</h3>
              <p>Branch personnel identification and contact info</p>
              <div className="form-row">
                <Field
                  label="Reporter name *"
                  name="reporter_name"
                  value={form.reporter_name}
                  onChange={change}
                  error={fields.reporter_name}
                  placeholder="e.g. Officer Alex Morgan"
                />
                <Field
                  label="Contact details *"
                  name="reporter_contact"
                  value={form.reporter_contact}
                  onChange={change}
                  error={fields.reporter_contact}
                  placeholder="Email or phone number"
                />
              </div>
            </div>
          </div>

          {/* Section 2: Structured Identifiers (Part A) */}
          <div className="form-section">
            <div className="section-number">02</div>
            <div className="section-content">
              <h3>Structured identifiers & error codes</h3>
              <p>Validated via Automata Theory (DFA) and regular expressions</p>
              <div className="form-row">
                <Field
                  label="ATM ID * (ATM[3-alpha][4-digit])"
                  name="atm_id"
                  value={form.atm_id}
                  onChange={change}
                  error={fields.atm_id}
                  placeholder="e.g. ATMNOR1001 or ATM-NOR-1001"
                  hint={
                    validation?.atm?.valid
                      ? `✓ DFA & Regex Valid · ${validation.atm.zone} Zone`
                      : validation?.atm?.dfa === false
                      ? 'DFA State: Incomplete/Rejected'
                      : null
                  }
                />
                <Field
                  label="Error Code * (E[2-digit][1-alpha])"
                  name="error_code"
                  value={form.error_code}
                  onChange={change}
                  error={fields.error_code}
                  placeholder="e.g. E01H (or legacy HW-104)"
                  hint={
                    validation?.error_code?.valid
                      ? `✓ DFA & Regex Valid`
                      : null
                  }
                />
              </div>

              {/* Urgency Field (Required by Part C.9.a) */}
              <div className="form-row">
                <label className="field">
                  <span>Urgency level *</span>
                  <select name="urgency" value={form.urgency} onChange={change} style={{height: 35}}>
                    <option value="Low">Low - Minor cosmetic or non-blocking</option>
                    <option value="Medium">Medium - Degraded performance / sensor issue</option>
                    <option value="High">High - Out of cash / branch critical</option>
                    <option value="Critical">Critical - Security alert / physical breach</option>
                  </select>
                </label>
              </div>

              <label className="field">
                <span>Incident description *</span>
                <textarea
                  name="description"
                  rows="4"
                  value={form.description}
                  onChange={change}
                  placeholder="Describe the failure (e.g. Cash dispenser jam, card reader broken, network timeout, unauthorized tamper...)"
                />
                {fields.description && <small className="field-error">{fields.description}</small>}
                <small className="field-note">
                  Classifies automatically into: Hardware, Network, Cash-Handling, Software, or Security.
                </small>
              </label>
            </div>
          </div>

          <div className="form-footer">
            <span>
              <Shield size={15} /> Validated with BCS503 DFA State Machine Simulator
            </span>
            <button disabled={loading} className="button primary" type="submit">
              {loading ? 'Submitting…' : 'Submit report'} <span>→</span>
            </button>
          </div>
        </form>

        {/* Aside: Automatic Classification & Routing Preview */}
        <div className="form-aside">
          <div className="panel detect-panel">
            <div className="detect-title">
              <div className="detect-icon">
                <Command size={17} />
              </div>
              <div>
                <strong>Real-Time Classifier</strong>
                <small>BCS503 Automata & BCS502 Network</small>
              </div>
              <i />
            </div>

            <div className="detect-item">
              <span>Detected Category</span>
              <strong>{validation?.category || 'Waiting for description'}</strong>
              {validation?.classification_reason && (
                <small style={{fontSize: 9, color: '#8898aa', marginTop: 2}}>
                  {validation.classification_reason}
                </small>
              )}
            </div>

            <div className="detect-item">
              <span>Calculated Priority</span>
              <strong>
                {validation?.priority || 'Waiting for input'}{' '}
                {validation?.priority && <Badge>{validation.priority}</Badge>}
              </strong>
            </div>

            <div className="detect-item">
              <span>Target Support Zone</span>
              <strong>{validation?.atm?.zone || 'Detected from prefix'}</strong>
            </div>

            <div className="detect-item">
              <span>Routing Destination</span>
              <strong>{validation?.routing_preview || 'Determined upon input'}</strong>
            </div>

            <div className="detect-item">
              <span>DFA & Regex Agreement</span>
              <strong>
                {validation?.atm?.agree ? (
                  <span style={{color: '#2e7d32', fontSize: 10}}>✓ DFA & Regex Agree</span>
                ) : (
                  <span style={{color: '#d32f2f', fontSize: 10}}>Pending / Disagree</span>
                )}
              </strong>
            </div>
          </div>

          <div className="aside-help">
            <CircleHelp size={17} />
            <div>
              <strong>Security Protocol Notice</strong>
              <p>
                Security incidents bypass all regional teams and dispatch directly to the{' '}
                <b>Central Security Desk</b> with emergency escalation.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function MyReports() {
  const {data: reports, error, refresh} = useData('/reports', 15000);
  const [id, setId] = useState(new URLSearchParams(location.search).get('id') || '');
  const [found, setFound] = useState(null);
  const [lookupError, setLookupError] = useState('');

  const counts = useMemo(
    () => ({
      total: reports?.length || 0,
      pending: reports?.filter((r) => r.status === 'Pending').length || 0,
      assigned: reports?.filter((r) => r.status === 'Assigned').length || 0,
      progress: reports?.filter((r) => r.status === 'In Progress').length || 0,
      resolved: reports?.filter((r) => r.status === 'Resolved').length || 0,
    }),
    [reports]
  );

  async function lookup(e) {
    e.preventDefault();
    setLookupError('');
    try {
      const res = await api.get('/reports/' + id.trim());
      setFound(res.data);
    } catch (e) {
      setFound(null);
      setLookupError(e.response?.data?.error || 'Could not find any report with that ID.');
    }
  }

  return (
    <>
      <PageHeading
        eyebrow="USER DASHBOARD (PART C.9.b)"
        title="My reports"
        description="Search by Report ID, check live assignment status, and track incident resolution progress."
      />
      <ErrorBox>{error}</ErrorBox>
      <div className="stat-grid five">
        <Stat label="Total" value={counts.total} sub="Reports submitted" icon={Activity} />
        <Stat label="Pending" value={counts.pending} sub="Awaiting dispatch" icon={Clock3} tint="amber" />
        <Stat label="Assigned" value={counts.assigned} sub="Support assigned" icon={Users} />
        <Stat label="In progress" value={counts.progress} sub="Under investigation" icon={Wifi} tint="purple" />
        <Stat label="Resolved" value={counts.resolved} sub="Completed" icon={CheckCircle2} tint="green" />
      </div>

      <div className="panel lookup-panel">
        <div>
          <h3>Look up a report</h3>
          <p>Enter the unique report ID (e.g. ATM-A1B2C3D4E5) to track status.</p>
        </div>
        <form onSubmit={lookup}>
          <label className="search-field">
            <Search size={16} />
            <input
              value={id}
              onChange={(e) => setId(e.target.value)}
              placeholder="e.g. ATM-A1B2C3D4E5"
              required
            />
          </label>
          <button className="button dark-button">Search report</button>
        </form>

        {lookupError && <ErrorBox>{lookupError}</ErrorBox>}

        {found && (
          <div className="lookup-result">
            <div>
              <small>REPORT ID</small>
              <strong>{found.id}</strong>
            </div>
            <div>
              <small>STATUS</small>
              <Badge>{found.status}</Badge>
            </div>
            <div>
              <small>ASSIGNED HANDLER</small>
              <strong>{found.handler || 'Waiting in Queue'}</strong>
            </div>
            <div>
              <small>ZONE & CATEGORY</small>
              <strong>
                {found.zone} Zone · {found.category}
              </strong>
            </div>
            {found.backup_handler && (
              <div>
                <small>BACKUP HANDLER</small>
                <strong>{found.backup_handler}</strong>
              </div>
            )}
            {found.escalation && (
              <div style={{gridColumn: '1 / -1', background: '#fff9e6', padding: '8px 10px', borderRadius: 4}}>
                <small style={{color: '#997300', fontWeight: 700}}>ESCALATION PATH</small>
                <p style={{margin: '3px 0 0', color: '#664d00', border: 'none', padding: 0}}>{found.escalation}</p>
              </div>
            )}
            <p>{found.description}</p>
          </div>
        )}
      </div>

      <div className="table-actions">
        <h3>All network reports</h3>
        <button className="icon-button" onClick={refresh}>
          <Activity size={16} />
        </button>
      </div>
      <ReportsTable rows={reports || []} />
    </>
  );
}

function Handlers() {
  const {data: reports, error, refresh: refreshReports} = useData('/reports', 15000);
  const {data: handlers, refresh} = useData('/handlers', 15000);
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');

  async function updateStatus(id, status) {
    setBusy(id);
    setMessage('');
    try {
      await api.patch(`/reports/${id}/status`, {status});
      await refreshReports();
      refresh();
    } catch (e) {
      setMessage(e.response?.data?.error || 'Status update failed.');
    } finally {
      setBusy('');
    }
  }

  async function updateHandler(h, patch) {
    try {
      await api.patch(`/handlers/${h.id}`, patch);
      refresh();
    } catch (e) {
      setMessage(e.response?.data?.error || 'Handler update failed.');
    }
  }

  const assigned = (reports || []).filter((r) => r.handler && r.status !== 'Resolved');

  return (
    <>
      <PageHeading
        eyebrow="HANDLER DASHBOARD (PART C.9.c)"
        title="Handler console"
        description="Review assigned incidents, update handler availability & capacity, and advance incident status."
      />
      <ErrorBox>{error || message}</ErrorBox>

      <div className="handler-cards">
        {(handlers || []).map((h) => (
          <div className="panel handler-card" key={h.id}>
            <div className="handler-top">
              <div className="avatar handler-avatar">
                {h.name
                  .split(' ')
                  .map((x) => x[0])
                  .slice(0, 2)
                  .join('')}
              </div>
              <div>
                <strong>{h.name}</strong>
                <span>
                  {h.zone} · {h.zone === 'Central Security' ? 'Central Desk' : 'Regional Handler'}
                </span>
              </div>
              <Badge>{h.available ? 'Available' : 'Unavailable'}</Badge>
            </div>
            <div className="capacity-line">
              <span>Current workload</span>
              <b>
                {h.load} <i>/ {h.capacity}</i>
              </b>
            </div>
            <div className="progress">
              <i
                style={{
                  width: `${Math.min(100, (h.load / h.capacity) * 100)}%`,
                  background: h.load >= h.capacity ? '#ef4444' : '#3579e8',
                }}
              />
            </div>
            <div className="handler-controls">
              <label className="toggle-row">
                <span>Available for dispatch</span>
                <input
                  type="checkbox"
                  checked={!!h.available}
                  onChange={(e) => updateHandler(h, {available: e.target.checked})}
                />
              </label>
              <label className="capacity-select">
                Capacity{' '}
                <select
                  value={h.capacity}
                  onChange={(e) => updateHandler(h, {capacity: e.target.value})}
                >
                  {[2, 4, 6, 8, 10, 12, 16, 20].map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              </label>
            </div>
          </div>
        ))}
      </div>

      <div className="table-actions">
        <h3>
          Active Assignments <span className="count-tag">{assigned.length}</span>
        </h3>
      </div>
      <div className="panel">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>REPORT ID</th>
                <th>ZONE</th>
                <th>CATEGORY</th>
                <th>PRIORITY</th>
                <th>STATUS</th>
                <th>SUBMITTED</th>
                <th>UPDATE STATUS</th>
              </tr>
            </thead>
            <tbody>
              {assigned.map((r) => (
                <tr key={r.id}>
                  <td>
                    <strong>{r.id}</strong>
                    <small>{r.atm_id}</small>
                  </td>
                  <td>{r.zone}</td>
                  <td>{r.category}</td>
                  <td>
                    <Badge>{r.priority}</Badge>
                  </td>
                  <td>
                    <Badge>{r.status}</Badge>
                  </td>
                  <td>{fmt(r.created_at)}</td>
                  <td>
                    <select
                      disabled={busy === r.id}
                      value={r.status}
                      onChange={(e) => updateStatus(r.id, e.target.value)}
                    >
                      {['Pending', 'Assigned', 'In Progress', 'Resolved'].map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!assigned.length && (
            <div className="empty-state">
              <LifeBuoy size={22} />
              <strong>No open assignments</strong>
              <span>All incidents have been resolved or are awaiting dispatch.</span>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function Routing() {
  const {data, error} = useData('/routing', 15000);
  const reportRows = data?.reports || [];

  return (
    <>
      <PageHeading
        eyebrow="ROUTING MANAGEMENT DASHBOARD (PART C.9.d / BCS502)"
        title="Routing & dispatch management"
        description="Explicit routing table, Central Security Desk bypass, handler loads, and escalation decisions."
      />
      <ErrorBox>{error}</ErrorBox>

      <div className="routing-metrics">
        <Stat label="Routing paths" value={data?.mappings?.length ?? '—'} sub="Zones & bypasses" icon={Building2} />
        <Stat
          label="Available handlers"
          value={data?.handlers?.filter((h) => h.available).length ?? '—'}
          sub="Ready for dispatch"
          icon={Users}
          tint="green"
        />
        <Stat
          label="Queued reports"
          value={data?.queued?.length ?? '—'}
          sub="Waiting for capacity"
          icon={Clock3}
          tint="amber"
        />
        <Stat
          label="Security / Emergency"
          value={reportRows.filter((r) => r.priority === 'Critical').length}
          sub="Critical priority reports"
          icon={AlertTriangle}
          tint="purple"
        />
      </div>

      {/* Security Bypass Rule Banner */}
      <div style={{background: '#f8fafc', border: '1px solid #cbd5e1', padding: '14px 18px', borderRadius: 7, marginBottom: 15}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 10}}>
          <Shield size={20} color="#dc2626" />
          <div>
            <strong style={{fontSize: 12, color: '#0f172a'}}>Part B Rule: Security Incident Bypass</strong>
            <p style={{fontSize: 10, color: '#475569', margin: '3px 0 0'}}>
              Security incidents bypass regional support teams completely and dispatch directly to the <b>Central Security Desk</b> with emergency on-call notification.
            </p>
          </div>
        </div>
      </div>

      {/* Explicit Routing Table */}
      <div className="panel">
        <div className="panel-head">
          <div>
            <h3>Explicit Routing / Dispatch Table (BCS502)</h3>
            <p>Prefix mapping to regional zones, security desk, and fallback queue</p>
          </div>
          <span className="live-chip">
            <i /> Live dispatch
          </span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ATM PREFIX</th>
                <th>TARGET REGION / DESK</th>
                <th>ASSIGNED HANDLER / AUTHORITY</th>
                <th>LOAD</th>
                <th>CAPACITY</th>
                <th>AVAILABILITY</th>
              </tr>
            </thead>
            <tbody>
              {(data?.mappings || []).map((m) => {
                const h = data.handlers?.find((x) => x.zone === m.zone);
                return (
                  <tr key={m.prefix}>
                    <td>
                      <code>{m.prefix}</code>
                    </td>
                    <td>
                      <strong>{m.target}</strong>
                    </td>
                    <td>{m.handler || 'Unassigned'}</td>
                    <td>{h?.load ?? 0}</td>
                    <td>{h?.capacity ?? 0}</td>
                    <td>
                      <Badge>{h?.available ? 'Available' : 'Unavailable'}</Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent Dispatch Decisions */}
      <div className="panel decision-panel">
        <div className="panel-head">
          <div>
            <h3>Recent dispatch & escalation decisions</h3>
            <p>Recorded routing keys, priority overrides, and backup failovers</p>
          </div>
        </div>
        <div className="decision-list">
          {reportRows.slice(0, 8).map((r) => (
            <div className="decision-row" key={r.id}>
              <div className={'decision-symbol ' + (r.priority === 'Critical' ? 'critical' : '')}>
                <Activity size={16} />
              </div>
              <div className="decision-copy">
                <strong>
                  {r.id} <span>·</span> {r.atm_id} ({r.zone} Zone)
                </strong>
                <p>
                  {r.escalation || `Routed to ${r.handler || 'dispatch queue'} (${r.category})`}
                  {r.backup_handler ? ` · Backup: ${r.backup_handler}` : ''}
                </p>
              </div>
              <Badge>{r.priority}</Badge>
              <time>{fmt(r.created_at)}</time>
            </div>
          ))}
          {!reportRows.length && (
            <div className="empty-state">
              <Activity size={22} />
              <strong>No routing events yet</strong>
              <span>Submitted reports will appear here with live dispatch notes.</span>
            </div>
          )}
        </div>
      </div>

      {data?.queued?.length > 0 && (
        <div className="queue-notice">
          <Clock3 size={18} />
          <div>
            <strong>
              {data.queued.length} report{data.queued.length > 1 ? 's' : ''} waiting in queue
            </strong>
            <span>Handlers are currently at capacity or unavailable; automatic failover is active.</span>
          </div>
        </div>
      )}
    </>
  );
}

function Analytics() {
  const {data, error} = useData('/analytics', 30000);

  return (
    <>
      <PageHeading
        eyebrow="ANALYTICS DASHBOARD (PART C.9.e)"
        title="Analytics & operational intelligence"
        description="Zone-wise and category-wise report distributions, resolved/unresolved counts, and trend visualizations."
        action={<span className="live-chip"><i /> Live database</span>}
      />
      <ErrorBox>{error}</ErrorBox>
      <div className="stat-grid">
        <Stat label="Total reports" value={data?.total ?? '—'} sub="Across all regions" icon={Activity} />
        <Stat label="Resolved" value={data?.resolved ?? '—'} sub="Closed incidents" icon={CheckCircle2} tint="green" />
        <Stat
          label="Unresolved"
          value={data ? data.unresolved : '—'}
          sub="Open or in progress"
          icon={Clock3}
          tint="amber"
        />
        <Stat
          label="Critical priority"
          value={data?.priorities?.find((x) => x.name === 'Critical')?.value ?? 0}
          sub="Security / emergency"
          icon={AlertTriangle}
          tint="purple"
        />
      </div>

      <div className="analytics-grid">
        {/* Zone Distribution */}
        <div className="panel analytics-panel">
          <div className="panel-head">
            <div>
              <h3>Reports by zone</h3>
              <p>Regional distribution across North, South, East, West & Central</p>
            </div>
          </div>
          <div className="chart-area">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data?.zones || []} margin={{top: 10, right: 10, left: -20, bottom: 0}}>
                <CartesianGrid stroke="#edf0f4" vertical={false} />
                <XAxis dataKey="name" tickLine={false} axisLine={false} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
                <Tooltip />
                <Bar dataKey="value" fill="#4e88ed" radius={[5, 5, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Category Distribution */}
        <div className="panel analytics-panel">
          <div className="panel-head">
            <div>
              <h3>Reports by category (5 Predefined Categories)</h3>
              <p>Hardware, Network, Cash-Handling, Software, Security</p>
            </div>
          </div>
          <div className="pie-wrap">
            <ResponsiveContainer width="55%" height="100%">
              <PieChart>
                <Pie
                  data={data?.categories || []}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={48}
                  outerRadius={74}
                  paddingAngle={3}
                >
                  {(data?.categories || []).map((x, i) => (
                    <Cell key={x.name} fill={colors[i % colors.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            <div className="legend">
              {(data?.categories || []).map((x, i) => (
                <div key={x.name}>
                  <i style={{background: colors[i % colors.length]}} />
                  {x.name}
                  <b>{x.value}</b>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Status Overview */}
        <div className="panel analytics-panel">
          <div className="panel-head">
            <div>
              <h3>Status overview</h3>
              <p>Pending, Assigned, In Progress, Resolved</p>
            </div>
          </div>
          <div className="chart-area">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data?.statuses || []}
                layout="vertical"
                margin={{top: 8, right: 24, left: 16, bottom: 0}}
              >
                <CartesianGrid stroke="#edf0f4" horizontal={false} />
                <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" tickLine={false} axisLine={false} width={85} />
                <Tooltip />
                <Bar dataKey="value" fill="#55b99a" radius={[0, 5, 5, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Priority Distribution */}
        <div className="panel analytics-panel">
          <div className="panel-head">
            <div>
              <h3>Priority distribution</h3>
              <p>Critical, High, Medium, Low breakdown</p>
            </div>
          </div>
          <div className="chart-area">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data?.priorities || []} margin={{top: 8, right: 12, left: -18, bottom: 0}}>
                <CartesianGrid stroke="#edf0f4" vertical={false} />
                <XAxis dataKey="name" tickLine={false} axisLine={false} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
                <Tooltip />
                <Bar dataKey="value" fill="#ad8bea" radius={[5, 5, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="category-note">
        <span>
          <Shield size={16} />
        </span>
        <div>
          <strong>Five predefined classifications:</strong>
          <p>Hardware · Network · Cash-Handling · Software · Security</p>
        </div>
      </div>
    </>
  );
}

function DFASimulatorPage() {
  const [type, setType] = useState('atm');
  const [inputVal, setInputVal] = useState('ATMNOR1001');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const runSimulation = (simType, val) => {
    setLoading(true);
    api.post('/dfa-simulate', {type: simType, input: val})
      .then((r) => setResult(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    runSimulation(type, inputVal);
  }, []);

  const presets = [
    {label: 'Valid ATM (Standard)', type: 'atm', value: 'ATMNOR1001'},
    {label: 'Valid ATM (Hyphenated)', type: 'atm', value: 'ATM-SOU-2002'},
    {label: 'Invalid ATM (Wrong Prefix)', type: 'atm', value: 'ATMXYZ9999'},
    {label: 'Invalid ATM (Short)', type: 'atm', value: 'ATMNOR1'},
    {label: 'Valid Error Code (Hardware)', type: 'error_code', value: 'E01H'},
    {label: 'Valid Error Code (Security)', type: 'error_code', value: 'E05X'},
    {label: 'Invalid Error Code', type: 'error_code', value: '123-INVALID'},
  ];

  return (
    <>
      <PageHeading
        eyebrow="AUTOMATA THEORY & COMPUTABILITY (BCS503)"
        title="DFA state machine simulator & regex comparison"
        description="Formal DFA simulation tracing state transitions and verifying equivalence with regular expressions."
      />

      <div className="panel" style={{padding: 20, marginBottom: 20}}>
        <h3>Interactive DFA Test Bench</h3>
        <p style={{color: '#64748b', fontSize: 11, margin: '4px 0 15px'}}>
          Select the DFA validator type and enter an input string to view step-by-step state transitions.
        </p>

        <div style={{display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 15}}>
          {presets.map((p) => (
            <button
              key={p.label}
              className="button"
              style={{background: '#f1f5f9', color: '#334155', fontSize: 10, height: 30}}
              onClick={() => {
                setType(p.type);
                setInputVal(p.value);
                runSimulation(p.type, p.value);
              }}
            >
              {p.label}
            </button>
          ))}
        </div>

        <div style={{display: 'flex', gap: 10, alignItems: 'center'}}>
          <select
            value={type}
            onChange={(e) => {
              setType(e.target.value);
              const defaultVal = e.target.value === 'atm' ? 'ATMNOR1001' : 'E01H';
              setInputVal(defaultVal);
              runSimulation(e.target.value, defaultVal);
            }}
            style={{height: 36, padding: '0 10px', borderRadius: 4, border: '1px solid #cbd5e1'}}
          >
            <option value="atm">ATM ID DFA (ATM[3-alpha][4-digit])</option>
            <option value="error_code">Error Code DFA (E[2-digit][1-alpha])</option>
          </select>
          <input
            style={{
              flex: 1,
              height: 36,
              padding: '0 12px',
              borderRadius: 4,
              border: '1px solid #cbd5e1',
              fontFamily: 'monospace',
            }}
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            placeholder="Type string to simulate..."
          />
          <button
            className="button primary"
            disabled={loading}
            onClick={() => runSimulation(type, inputVal)}
          >
            {loading ? 'Simulating…' : 'Simulate DFA'}
          </button>
        </div>
      </div>

      {result && (
        <div style={{display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 16}}>
          {/* DFA Summary Card */}
          <div className="panel" style={{padding: 20}}>
            <h3>Automata Simulation Result</h3>
            <div style={{marginTop: 15, display: 'grid', gap: 12}}>
              <div>
                <small style={{color: '#64748b', fontSize: 9}}>FORMAL LANGUAGE</small>
                <div style={{fontFamily: 'monospace', fontSize: 11, marginTop: 3}}>
                  {result.formal_language}
                </div>
              </div>
              <div>
                <small style={{color: '#64748b', fontSize: 9}}>DFA STATUS</small>
                <div>
                  <span
                    className={
                      'badge ' + (result.dfa_accepted ? 'available' : 'unavailable')
                    }
                  >
                    {result.dfa_accepted ? 'ACCEPTED' : 'REJECTED'}
                  </span>
                </div>
              </div>
              <div>
                <small style={{color: '#64748b', fontSize: 9}}>REGEX STATUS</small>
                <div>
                  <span
                    className={
                      'badge ' + (result.regex_accepted ? 'available' : 'unavailable')
                    }
                  >
                    {result.regex_accepted ? 'MATCHED' : 'UNMATCHED'}
                  </span>
                </div>
              </div>
              <div>
                <small style={{color: '#64748b', fontSize: 9}}>DFA & REGEX AGREEMENT</small>
                <div>
                  <span
                    className={
                      'badge ' + (result.agree ? 'available' : 'unavailable')
                    }
                  >
                    {result.agree ? '✓ PERFECT AGREEMENT' : '⚠ DISCREPANCY'}
                  </span>
                </div>
              </div>
              <div>
                <small style={{color: '#64748b', fontSize: 9}}>FINAL STATE REACHED</small>
                <div style={{fontFamily: 'monospace', fontWeight: 700, fontSize: 13}}>
                  {result.final_state}
                </div>
              </div>
            </div>
          </div>

          {/* Step-by-Step Transition Trace */}
          <div className="panel" style={{padding: 20}}>
            <h3>Step-by-Step State Transition Trace (δ)</h3>
            <p style={{color: '#64748b', fontSize: 10, margin: '4px 0 12px'}}>
              State transitions executed for each character token in the input string.
            </p>
            <div className="table-wrap" style={{maxHeight: 340}}>
              <table>
                <thead>
                  <tr>
                    <th>STEP</th>
                    <th>CHAR INPUT</th>
                    <th>CURRENT STATE</th>
                    <th>NEXT STATE δ(q, c)</th>
                  </tr>
                </thead>
                <tbody>
                  {(result.trace || []).map((t, idx) => (
                    <tr key={idx}>
                      <td>{t.step}</td>
                      <td>
                        <code>{t.char}</code>
                      </td>
                      <td>
                        <code>{t.from_state || '—'}</code>
                      </td>
                      <td>
                        <strong
                          style={{
                            color:
                              t.state === 'REJECT'
                                ? '#ef4444'
                                : t.state === result.final_state && result.dfa_accepted
                                ? '#10b981'
                                : '#2563eb',
                          }}
                        >
                          {t.state}
                        </strong>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function SettingsPage() {
  const {data} = useData('/health');

  return (
    <>
      <PageHeading eyebrow="SYSTEM" title="Settings" description="Service status and application configuration." />
      <div className="panel settings-panel">
        <h3>Service connectivity & academic compliance</h3>
        <p>Frontend API connection and backend status.</p>
        <div className="system-state">
          <i /> {data?.status === 'ok' ? 'Backend and SQLite database connected' : 'Connecting to backend…'}
        </div>
        <div style={{marginTop: 15}}>
          <small style={{fontSize: 10, color: '#64748b'}}>STANDARDS INTEGRATED:</small>
          <div style={{display: 'flex', gap: 8, marginTop: 5}}>
            {(data?.standards || []).map((s) => (
              <span key={s} className="badge medium">
                {s}
              </span>
            ))}
          </div>
        </div>
        <code style={{marginTop: 15}}>{import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000/api'}</code>
      </div>
    </>
  );
}

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/submit" element={<Submit />} />
        <Route path="/my-reports" element={<MyReports />} />
        <Route path="/handlers" element={<Handlers />} />
        <Route path="/routing" element={<Routing />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/dfa-simulator" element={<DFASimulatorPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Overview />} />
      </Routes>
    </Shell>
  );
}
