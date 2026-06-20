import type { AccountingEntry, AuditRisk, ImportJob } from '../api/client'

export function DashboardPage({ jobs, entries, risks }: { jobs: ImportJob[]; entries: AccountingEntry[]; risks: AuditRisk[] }) {
  const pendingRisks = risks.filter((risk) => risk.status === 'pending_review').length
  return (
    <section>
      <h2>仪表盘</h2>
      <div className="cards">
        <article><strong>{jobs.length}</strong><span>导入批次</span></article>
        <article><strong>{entries.length}</strong><span>会计分录</span></article>
        <article><strong>{risks.length}</strong><span>风险提示</span></article>
        <article><strong>{pendingRisks}</strong><span>待复核</span></article>
      </div>
      <div className="panel">
        <h3>当前 MVP 能力</h3>
        <ul>
          <li>上传 Excel / CSV 凭证分录与 PDF / TXT 原始文件</li>
          <li>自动解析分录、生成标签并写入向量库</li>
          <li>基于规则与相似检索形成审计风险提示</li>
          <li>支持风险证据链查看和人工复核状态更新</li>
        </ul>
      </div>
    </section>
  )
}
