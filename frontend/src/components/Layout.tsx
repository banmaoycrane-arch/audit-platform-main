import type { ReactNode } from 'react'

export type PageKey = 'dashboard' | 'import' | 'entries' | 'risks'

export function Layout({ page, onNavigate, children }: { page: PageKey; onNavigate: (page: PageKey) => void; children: ReactNode }) {
  const items: Array<[PageKey, string]> = [
    ['dashboard', '仪表盘'],
    ['import', '导入'],
    ['entries', '分录'],
    ['risks', '风险']
  ]
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>财务向量审计</h1>
        <p>导入、标签、向量分析与审计风险识别</p>
        <nav>
          {items.map(([key, label]) => (
            <button key={key} className={page === key ? 'active' : ''} onClick={() => onNavigate(key)}>{label}</button>
          ))}
        </nav>
      </aside>
      <main>{children}</main>
    </div>
  )
}
