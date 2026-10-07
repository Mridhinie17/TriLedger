import React from 'react';
import { Bot, Sparkles, ShieldAlert, CheckCircle, Check } from 'lucide-react';

export default function AgentDrawer({
  invoiceNumber,
  agentReport,
  isInvestigating,
  onRunInvestigation,
  onOpenDecisionModal
}) {
  const steps = [
    { id: 'sanitize_and_scan', label: '1. Sanitize' },
    { id: 'gather_evidence', label: '2. Gather Evidence' },
    { id: 'reason_and_analyze', label: '3. Analyze' },
    { id: 'enforce_guardrails', label: '4. Guardrails' },
    { id: 'log_audit_trail', label: '5. Audit Log' },
  ];

  return (
    <div className="stitch-card-elevated" style={{
      borderTop: '1px solid var(--border-subtle)',
      background: 'rgba(8, 12, 22, 0.95)',
      padding: '14px 20px',
      display: 'flex',
      flexDirection: 'column',
      gap: '10px'
    }}>
      {/* Drawer Header & Actions */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '30px',
            height: '30px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 12px rgba(99, 102, 241, 0.35)'
          }}>
            <Bot size={16} color="#FFFFFF" />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '0.88rem', fontWeight: '700', color: '#F8FAFC' }}>
                Investigation Agent
              </span>
            </div>
            <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
              Automated root-cause analysis and evidence gathering
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            className="btn-stitch btn-stitch-primary"
            onClick={onRunInvestigation}
            disabled={isInvestigating}
            style={{ fontSize: '0.78rem', padding: '6px 14px' }}
          >
            <Sparkles size={13} className={isInvestigating ? 'spin-icon' : ''} />
            <span>{isInvestigating ? 'Investigating...' : 'Run Investigation'}</span>
          </button>

          <button
            className="btn-stitch btn-stitch-success"
            onClick={() => onOpenDecisionModal('APPROVE')}
            style={{ fontSize: '0.76rem', padding: '6px 12px' }}
          >
            Approve
          </button>

          <button
            className="btn-stitch btn-stitch-warning"
            onClick={() => onOpenDecisionModal('ON_HOLD')}
            style={{ fontSize: '0.76rem', padding: '6px 12px' }}
          >
            Hold
          </button>

          <button
            className="btn-stitch btn-stitch-danger"
            onClick={() => onOpenDecisionModal('ESCALATE')}
            style={{ fontSize: '0.76rem', padding: '6px 12px' }}
          >
            Escalate
          </button>
        </div>
      </div>

      {/* Clean Step Flow */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 12px',
        borderRadius: '8px',
        background: 'rgba(255, 255, 255, 0.02)',
        border: '1px solid var(--border-subtle)'
      }}>
        {steps.map((step, idx) => {
          const isDone = agentReport != null;
          return (
            <React.Fragment key={step.id}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{
                  width: '15px',
                  height: '15px',
                  borderRadius: '50%',
                  background: isDone ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.06)',
                  border: isDone ? '1px solid #10B981' : '1px solid rgba(255, 255, 255, 0.12)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.58rem',
                  color: isDone ? '#34D399' : 'var(--text-muted)'
                }}>
                  {isDone ? <Check size={9} /> : idx + 1}
                </div>
                <span style={{
                  fontSize: '0.7rem',
                  fontWeight: '600',
                  color: isDone ? '#F1F5F9' : 'var(--text-muted)'
                }}>
                  {step.label}
                </span>
              </div>
              {idx < steps.length - 1 && (
                <span style={{ color: 'rgba(255, 255, 255, 0.12)', fontSize: '0.75rem' }}>→</span>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Investigation Report */}
      {agentReport && (
        <div style={{
          padding: '10px 14px',
          borderRadius: '8px',
          background: 'rgba(99, 102, 241, 0.06)',
          border: '1px solid rgba(99, 102, 241, 0.2)',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: '700' }}>
                Recommendation:
              </span>
              <span className={`badge ${
                agentReport.recommended_action === 'APPROVE'
                  ? 'badge-approved'
                  : agentReport.recommended_action === 'HOLD'
                  ? 'badge-hold'
                  : 'badge-escalated'
              }`} style={{ fontSize: '0.7rem', padding: '2px 8px' }}>
                {agentReport.recommended_action}
              </span>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                Confidence: <strong style={{ color: '#F8FAFC' }}>{(agentReport.confidence * 100).toFixed(1)}%</strong>
              </span>
            </div>

            {agentReport.is_adversarial_injection_detected && (
              <div className="badge badge-escalated" style={{ fontSize: '0.68rem' }}>
                <ShieldAlert size={11} />
                Adversarial Input Detected
              </div>
            )}
          </div>

          <div style={{ fontSize: '0.78rem', color: '#E2E8F0', lineHeight: '1.4' }}>
            {agentReport.case_summary}
          </div>

          {/* Cited records */}
          {agentReport.cited_records && agentReport.cited_records.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
              <span style={{ fontSize: '0.66rem', color: 'var(--text-muted)', fontWeight: '700' }}>
                Cited Records:
              </span>
              <div style={{ display: 'flex', gap: '4px' }}>
                {agentReport.cited_records.map((rec) => (
                  <span
                    key={rec}
                    className="font-mono"
                    style={{
                      fontSize: '0.66rem',
                      padding: '1px 6px',
                      borderRadius: '4px',
                      background: 'rgba(255, 255, 255, 0.05)',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      color: '#38BDF8'
                    }}
                  >
                    {rec}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
