import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { get, post, put } from '../api/client';
import {
  GitMerge,
  AlertTriangle,
  CheckCircle,
  Clock,
  Search,
  ChevronDown,
  ChevronRight,
  Layers,
  Activity,
  Eye,
} from 'lucide-react';
import clsx from 'clsx';
import LoadingSpinner from '../components/LoadingSpinner';

interface CorrelatedIncident {
  id: string;
  title: string;
  severity: string;
  status: string;
  investigation_ids: string[];
  correlation_score: number;
  correlation_reasons: string[];
  service: string;
  environment: string;
  first_seen: string;
  last_seen: string;
  merged_into: string | null;
  metadata: Record<string, unknown>;
  investigations?: Investigation[];
}

interface Investigation {
  investigation_id: string;
  alert_id: string;
  alert_name: string;
  severity: string;
  status: string;
  confidence: number;
  created_at: string;
}

interface IncidentsResponse {
  incidents: CorrelatedIncident[];
  total: number;
}

const severityColors: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  warning: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  info: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
};

const statusIcons: Record<string, React.ReactNode> = {
  open: <AlertTriangle className="w-4 h-4 text-yellow-400" />,
  investigating: <Activity className="w-4 h-4 text-blue-400" />,
  resolved: <CheckCircle className="w-4 h-4 text-green-400" />,
  merged: <GitMerge className="w-4 h-4 text-purple-400" />,
};

export default function IncidentCorrelation() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [mergeSource, setMergeSource] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery<IncidentsResponse>({
    queryKey: ['incidents', statusFilter],
    queryFn: () =>
      get<IncidentsResponse>(
        `/incidents${statusFilter ? `?status=${statusFilter}` : ''}`
      ),
  });

  const mergeMutation = useMutation({
    mutationFn: (body: { source_id: string; target_id: string }) =>
      post('/incidents/merge', body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      setMergeSource(null);
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      put(`/incidents/${id}/status`, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['incidents'] }),
  });

  const filteredIncidents = useMemo(() => {
    if (!data?.incidents) return [];
    if (!searchQuery) return data.incidents;
    const q = searchQuery.toLowerCase();
    return data.incidents.filter(
      (i) =>
        i.title.toLowerCase().includes(q) ||
        i.service.toLowerCase().includes(q) ||
        i.id.toLowerCase().includes(q)
    );
  }, [data, searchQuery]);

  if (isLoading) return <LoadingSpinner size="lg" />;
  if (error)
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-6">
        <p className="text-red-400">Failed to load incidents</p>
      </div>
    );

  const stats = {
    total: data?.incidents.length ?? 0,
    open: data?.incidents.filter((i) => i.status === 'open').length ?? 0,
    investigating: data?.incidents.filter((i) => i.status === 'investigating').length ?? 0,
    resolved: data?.incidents.filter((i) => i.status === 'resolved').length ?? 0,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Incident Correlation</h1>
          <p className="text-sm text-gray-400 mt-1">
            Related alerts grouped into unified incidents
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-brand-400" />
          <span className="text-sm text-gray-300">{stats.total} incidents</span>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total', value: stats.total, color: 'text-gray-100' },
          { label: 'Open', value: stats.open, color: 'text-yellow-400' },
          { label: 'Investigating', value: stats.investigating, color: 'text-blue-400' },
          { label: 'Resolved', value: stats.resolved, color: 'text-green-400' },
        ].map((s) => (
          <div key={s.label} className="rounded-xl border border-gray-700 bg-gray-800/50 p-4">
            <p className="text-xs text-gray-400">{s.label}</p>
            <p className={clsx('text-2xl font-bold mt-1', s.color)}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search incidents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-lg bg-gray-800 border border-gray-700 text-gray-100 text-sm focus:outline-none focus:border-brand-400"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-gray-100 text-sm"
        >
          <option value="">All Statuses</option>
          <option value="open">Open</option>
          <option value="investigating">Investigating</option>
          <option value="resolved">Resolved</option>
        </select>
      </div>

      {mergeSource && (
        <div className="rounded-lg border border-purple-500/30 bg-purple-500/10 p-3 flex items-center justify-between">
          <span className="text-sm text-purple-300">
            <GitMerge className="w-4 h-4 inline mr-2" />
            Select target incident to merge <strong>{mergeSource}</strong> into
          </span>
          <button
            onClick={() => setMergeSource(null)}
            className="text-xs text-gray-400 hover:text-gray-200"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Incident List */}
      <div className="space-y-3">
        {filteredIncidents.map((incident) => (
          <div
            key={incident.id}
            className={clsx(
              'rounded-xl border bg-gray-800/50 overflow-hidden transition-all',
              mergeSource && mergeSource !== incident.id
                ? 'border-purple-500/30 cursor-pointer hover:bg-purple-500/5'
                : 'border-gray-700'
            )}
            onClick={() => {
              if (mergeSource && mergeSource !== incident.id) {
                mergeMutation.mutate({ source_id: mergeSource, target_id: incident.id });
              }
            }}
          >
            <div className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setExpandedId(expandedId === incident.id ? null : incident.id);
                    }}
                  >
                    {expandedId === incident.id ? (
                      <ChevronDown className="w-4 h-4 text-gray-400" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-gray-400" />
                    )}
                  </button>
                  {statusIcons[incident.status]}
                  <div>
                    <h3 className="text-sm font-medium text-gray-100">{incident.title}</h3>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {incident.id} · {incident.service || 'unknown service'} · {incident.environment || 'unknown env'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-400">
                    {incident.investigation_ids.length} alert{incident.investigation_ids.length !== 1 ? 's' : ''}
                  </span>
                  <span
                    className={clsx(
                      'px-2 py-0.5 rounded-full text-xs border',
                      severityColors[incident.severity] || severityColors.info
                    )}
                  >
                    {incident.severity}
                  </span>
                  <span className="text-xs text-gray-500">
                    Score: {(incident.correlation_score * 100).toFixed(0)}%
                  </span>
                  {incident.status !== 'resolved' && incident.status !== 'merged' && (
                    <div className="flex gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setMergeSource(incident.id);
                        }}
                        className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-purple-400"
                        title="Merge into another incident"
                      >
                        <GitMerge className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          statusMutation.mutate({
                            id: incident.id,
                            status: incident.status === 'open' ? 'investigating' : 'resolved',
                          });
                        }}
                        className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-green-400"
                        title={incident.status === 'open' ? 'Start investigating' : 'Resolve'}
                      >
                        {incident.status === 'open' ? (
                          <Eye className="w-3.5 h-3.5" />
                        ) : (
                          <CheckCircle className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Correlation reasons */}
              <div className="flex gap-1 mt-2 ml-7">
                {incident.correlation_reasons.map((reason, idx) => (
                  <span key={idx} className="px-1.5 py-0.5 rounded bg-gray-700/50 text-xs text-gray-400">
                    {reason}
                  </span>
                ))}
              </div>

              {/* Time info */}
              <div className="flex gap-4 mt-2 ml-7 text-xs text-gray-500">
                <span>
                  <Clock className="w-3 h-3 inline mr-1" />
                  First: {new Date(incident.first_seen).toLocaleString()}
                </span>
                <span>Last: {new Date(incident.last_seen).toLocaleString()}</span>
              </div>
            </div>

            {/* Expanded: investigation list */}
            {expandedId === incident.id && (
              <div className="border-t border-gray-700 bg-gray-900/30 p-4">
                <h4 className="text-xs font-medium text-gray-400 mb-2">
                  Correlated Investigations ({incident.investigation_ids.length})
                </h4>
                <div className="space-y-2">
                  {incident.investigation_ids.map((invId) => (
                    <div
                      key={invId}
                      className="flex items-center justify-between p-2 rounded-lg bg-gray-800/50 border border-gray-700"
                    >
                      <span className="text-sm text-gray-300 font-mono">{invId}</span>
                      <a
                        href={`/investigations/${invId}`}
                        className="text-xs text-brand-400 hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        View
                      </a>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}

        {filteredIncidents.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            <Layers className="w-8 h-8 mx-auto mb-3 opacity-50" />
            <p>No correlated incidents found</p>
          </div>
        )}
      </div>
    </div>
  );
}
