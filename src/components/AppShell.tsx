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

export function PageHeader({ title, description, actions }: { title: string; description: string; actions?: ReactNode }) {
  return <section className="page-header"><div><h2>{title}</h2><p>{description}</p></div>{actions && <div className="page-header__actions">{actions}</div>}</section>
}
