import { useEffect } from 'react'
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react'
import { AlertTriangle, Check, CircleDashed, Minus, X } from 'lucide-react'
import { localizeEnumKey } from '../i18n'
import { useLocale } from '../i18n/LocaleProvider'

export function Button({ className = '', variant = 'secondary', children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'quiet' }) {
  return <button className={`button button--${variant} ${className}`.trim()} {...props}>{children}</button>
}

export function IconButton({ className = '', label, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return <button className={`icon-button ${className}`.trim()} aria-label={label} title={label} {...props}>{children}</button>
}

export function SegmentedControl<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: Array<{ value: T; label: string }>; onChange: (value: T) => void }) {
  return <div className="segmented-control" aria-label={label} role="group">
    {options.map((option) => <button key={option.value} type="button" className={value === option.value ? 'segmented-control__item segmented-control__item--active' : 'segmented-control__item'} aria-pressed={value === option.value} onClick={() => onChange(option.value)}>{option.label}</button>)}
  </div>
}

type StatusTone = 'success' | 'warning' | 'error' | 'review' | 'unavailable' | 'neutral'

const toneForStatus = (value: string): StatusTone => {
  const normalized = value.toLowerCase()
  if (['completed', 'observed', 'ok', 'passed', 'healthy', 'comparable', 'complete', 'reachable', 'approved', 'reviewed', 'frozen'].includes(normalized)) return 'success'
  if (['timeout', 'interrupted', 'cancelling', 'not_tested', 'not_checked', 'partial', 'draft', 'proposed'].includes(normalized)) return 'warning'
  if (['failed', 'connection_error', 'error', 'system_error', 'unreachable', 'rejected', 'invalidated', 'invalid'].includes(normalized)) return 'error'
  if (normalized === 'needs_review') return 'review'
  if (['unavailable', 'not_applicable', 'unsupported', 'missing', 'superseded', 'model_unavailable'].includes(normalized)) return 'unavailable'
  return 'neutral'
}

const iconForTone = (tone: StatusTone) => {
  if (tone === 'success') return <Check aria-hidden="true" size={13} />
  if (tone === 'warning') return <AlertTriangle aria-hidden="true" size={13} />
  if (tone === 'error') return <X aria-hidden="true" size={13} />
  if (tone === 'unavailable') return <Minus aria-hidden="true" size={13} />
  return <CircleDashed aria-hidden="true" size={13} />
}

export function StatusBadge({ state, className = '' }: { state: string; className?: string }) {
  const { t } = useLocale()
  const normalized = state.toLowerCase()
  const presentationStatus = ({ passed: 'healthy', failed: 'connection_error', not_tested: 'not_checked' } as Record<string, string>)[normalized] ?? normalized
  const key = localizeEnumKey(presentationStatus)
  const tone = toneForStatus(presentationStatus)
  return <span className={`status-badge status-badge--${tone} ${className}`.trim()} data-status={state}>{iconForTone(tone)}<span>{key ? t(key) : state.replaceAll('_', ' ')}</span></span>
}

export function Surface({ children, className = '', tone = 'grouped' }: HTMLAttributes<HTMLElement> & { tone?: 'grouped' | 'inset' | 'selected' | 'inspector' | 'popover' }) {
  return <section className={`surface surface--${tone} ${className}`.trim()}>{children}</section>
}

export function Modal({ title, eyebrow, closeLabel, onClose, children, className = '' }: { title: string; eyebrow?: string; closeLabel: string; onClose: () => void; children: ReactNode; className?: string }) {
  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [onClose])

  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
    <section className={`modal ${className}`.trim()} role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <header className="modal__header">
        <div className="modal__heading">
          {eyebrow && <span className="modal__eyebrow">{eyebrow}</span>}
          <h2 id="modal-title">{title}</h2>
        </div>
        <IconButton label={closeLabel} onClick={onClose}><X size={16} /></IconButton>
      </header>
      <div className="modal__body">{children}</div>
    </section>
  </div>
}

export function InspectorSection({ title, action, children, className = '' }: { title: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`inspector-section ${className}`.trim()}><header><h3>{title}</h3>{action}</header><div>{children}</div></section>
}

export function DisclosureSection({ title, children, open = false, className = '' }: { title: string; children: ReactNode; open?: boolean; className?: string }) {
  return <details className={`disclosure-section ${className}`.trim()} open={open}><summary>{title}</summary><div>{children}</div></details>
}

export function DataTable({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`data-table ${className}`.trim()}><table>{children}</table></div>
}
