import React, { useState } from 'react';
import { X, CheckCircle, Clock, AlertTriangle, ShieldCheck } from 'lucide-react';

export default function DecisionModal({
  isOpen,
  onClose,
  invoiceNumber,
  initialDecision = 'APPROVE',
  onSubmitDecision,
  isSubmitting
}) {
  const [decision, setDecision] = useState(initialDecision);
  const [reason, setReason] = useState('Auditor verified and confirmed within authorized risk tolerance.');
  const [analystName, setAnalystName] = useState('senior.auditor@enterprise.corp');
  const [notes, setNotes] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!reason.trim()) return;
    onSubmitDecision({
      decision,
      analyst_name: analystName,
      reason,
      notes: notes || undefined
    });
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(6, 8, 15, 0.75)',
      backdropFilter: 'blur(16px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 50,
      padding: '16px'
    }}>
      <div className="stitch-card-elevated" style={{
        width: '100%',
        maxWidth: '520px',
        padding: '24px',
        border: '1px solid rgba(255, 255, 255, 0.15)',
        boxShadow: '0 24px 60px -8px rgba(0, 0, 0, 0.7)',
        borderRadius: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '18px'
      }}>
        {/* Modal Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '800', letterSpacing: '-0.02em', color: '#F8FAFC' }}>
              Human Auditor Decision Override
            </h3>
            <p style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
              Record official auditor action for <strong className="font-mono" style={{ color: '#818CF8' }}>{invoiceNumber}</strong>
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              padding: '6px',
              color: 'var(--text-muted)',
              cursor: 'pointer'
            }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          
          {/* Decision Selection Pills */}
          <div>
            <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: '800', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '8px' }}>
              Target Decision Status
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
              {[
                { id: 'APPROVE', label: 'Approve', color: '#10B981', border: 'rgba(16, 185, 129, 0.4)' },
                { id: 'ON_HOLD', label: 'On Hold', color: '#F59E0B', border: 'rgba(245, 158, 11, 0.4)' },
                { id: 'ESCALATE', label: 'Escalate', color: '#F43F5E', border: 'rgba(244, 63, 94, 0.4)' }
              ].map((btn) => {
                const isSelected = decision === btn.id;
                return (
                  <button
                    key={btn.id}
                    type="button"
                    onClick={() => setDecision(btn.id)}
                    style={{
                      padding: '8px',
                      borderRadius: '8px',
                      fontSize: '0.78rem',
                      fontWeight: '700',
                      cursor: 'pointer',
                      border: '1px solid',
                      borderColor: isSelected ? btn.border : 'rgba(255, 255, 255, 0.08)',
                      background: isSelected ? 'rgba(255, 255, 255, 0.08)' : 'rgba(255, 255, 255, 0.02)',
                      color: isSelected ? btn.color : 'var(--text-muted)',
                      boxShadow: isSelected ? `0 0 12px ${btn.border}` : 'none',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    {btn.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Justification Reason */}
          <div>
            <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: '800', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Auditor Justification (Mandatory Audit Trail)
            </label>
            <textarea
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required
              placeholder="State rationale for approving, holding, or escalating this record..."
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: '8px',
                background: 'rgba(15, 23, 42, 0.7)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-primary)',
                fontSize: '0.8rem',
                fontFamily: 'var(--font-sans)',
                outline: 'none',
                resize: 'none'
              }}
            />
          </div>

          {/* Auditor Identifier */}
          <div>
            <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: '800', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Auditor Identity / SSO ID
            </label>
            <input
              type="text"
              value={analystName}
              onChange={(e) => setAnalystName(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: '8px',
                background: 'rgba(15, 23, 42, 0.7)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-primary)',
                fontSize: '0.8rem',
                outline: 'none'
              }}
            />
          </div>

          {/* Footer Submit Buttons */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '8px' }}>
            <button
              type="button"
              className="btn-stitch btn-stitch-ghost"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={`btn-stitch ${
                decision === 'APPROVE'
                  ? 'btn-stitch-success'
                  : decision === 'ON_HOLD'
                  ? 'btn-stitch-warning'
                  : 'btn-stitch-danger'
              }`}
              disabled={isSubmitting || !reason.trim()}
            >
              {isSubmitting ? 'Logging Action...' : `Confirm ${decision}`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
