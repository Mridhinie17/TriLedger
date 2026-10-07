import React from 'react';
import { Layers, Database, Sparkles } from 'lucide-react';

export default function Header({ stats, onExportMarts, isExporting, apiHealthy }) {
  return (
    <header className="header-bar">
      {/* Brand & Clean Title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{
          position: 'relative',
          width: '34px',
          height: '34px',
          borderRadius: '8px',
          background: 'linear-gradient(135deg, #6366F1 0%, #06B6D4 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 16px rgba(99, 102, 241, 0.35)',
          border: '1px solid rgba(255, 255, 255, 0.15)'
        }}>
          <Layers size={18} color="#FFFFFF" />
        </div>

        <div>
          <span style={{
            fontSize: '1.05rem',
            fontWeight: '700',
            letterSpacing: '-0.02em',
            color: '#F8FAFC'
          }}>
            TriLedger
          </span>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginLeft: '10px' }}>
            AP Reconciliation & Audit
          </span>
        </div>
      </div>

      {/* Clean KPI Metrics */}
      {stats && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* STP Rate */}
          <div className="stitch-card" style={{
            padding: '5px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: 'rgba(255, 255, 255, 0.02)'
          }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>STP Rate</span>
            <span className="font-mono" style={{
              fontSize: '0.82rem',
              fontWeight: '700',
              color: '#34D399'
            }}>
              {stats.straight_through_processing_pct}%
            </span>
          </div>

          {/* Exceptions */}
          <div className="stitch-card" style={{
            padding: '5px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: 'rgba(255, 255, 255, 0.02)'
          }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Exceptions</span>
            <span className="font-mono" style={{
              fontSize: '0.82rem',
              fontWeight: '700',
              color: '#FB7185'
            }}>
              {stats.exception_count}
            </span>
          </div>

          {/* Total Spend */}
          <div className="stitch-card" style={{
            padding: '5px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: 'rgba(255, 255, 255, 0.02)'
          }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Total Spend</span>
            <span className="font-mono" style={{
              fontSize: '0.82rem',
              fontWeight: '700',
              color: '#F8FAFC'
            }}>
              ₹{stats.total_spend_inr?.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
            </span>
          </div>

          {/* Anomalies */}
          <div className="stitch-card" style={{
            padding: '5px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: 'rgba(255, 255, 255, 0.02)'
          }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Anomalies</span>
            <span className="font-mono" style={{
              fontSize: '0.82rem',
              fontWeight: '700',
              color: '#FBBF24'
            }}>
              {stats.high_risk_anomalies}
            </span>
          </div>
        </div>
      )}

      {/* Action Controls & Realtime Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <button
          className="btn-stitch btn-stitch-ghost"
          onClick={onExportMarts}
          disabled={isExporting}
          style={{
            fontSize: '0.76rem',
            padding: '6px 12px',
            borderRadius: '6px'
          }}
          title="Export CSV and Parquet analytical data marts"
        >
          <Database size={13} className={isExporting ? 'spin-icon' : ''} />
          <span>{isExporting ? 'Exporting...' : 'Export Marts'}</span>
        </button>

        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '5px 10px',
          borderRadius: '6px',
          background: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid var(--border-subtle)'
        }}>
          <div className={`status-dot ${apiHealthy ? 'dot-green' : 'dot-red'}`} style={{ width: '6px', height: '6px' }} />
          <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
            {apiHealthy ? 'Connected' : 'Offline'}
          </span>
        </div>
      </div>
    </header>
  );
}
