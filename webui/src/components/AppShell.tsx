import type { ReactNode } from 'react'

export function AppShell({ sidebar, toolbar, children }: { sidebar: ReactNode; toolbar: ReactNode; children: ReactNode }) {
  return <div className="app-shell">{sidebar}<main className="app-shell__main">{toolbar}<div className="app-shell__content">{children}</div></main></div>
}

export function Sidebar({ children, open }: { children: ReactNode; open: boolean }) {
  return <aside className={open ? 'sidebar sidebar--open' : 'sidebar'}>{children}</aside>
}

export function Toolbar({ children }: { children: ReactNode }) {
  return <header className="toolbar">{children}</header>
}

export function PageHeader({ title: _title, actions }: { title: string; actions?: ReactNode }) {
  // The application toolbar already provides the page heading.  Keep this
  // component solely as an action rail so pages do not repeat their title.
  if (!actions) return null
  return <section className="page-header page-header--actions"><div className="page-header__actions">{actions}</div></section>
}
