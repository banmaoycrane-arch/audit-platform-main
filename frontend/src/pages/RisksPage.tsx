import { useState } from 'react'
import { api, type AuditRisk, type RiskDetail } from '../api/client'
import { RiskBadge } from '../components/RiskBadge'

export function RisksPage({ risks, onChanged }: { risks: AuditRisk[]; onChanged: () => Promise<void> }) {
  const [detail, setDetail] = useState<RiskDetail | null>(null)

  async function openDetail(riskId: number) {
    setDetail(await api.getRisk(riskId))
  }

  async function review(action: string) {
    if (!detail) return
    await api.reviewRisk(detail.id, action)
    setDetail(await api.getRisk(detail.id))
    await onChanged()
  }

  return (
    <section>
      <h2>审计风险提示</h2>
      <div className="risk-layout">
        <div className="panel table-wrap">
          <table><thead><tr><th>ID</th><th>等级</th><th>标题</th><th>状态</th><th>判断强度</th></tr></thead><tbody>
            {risks.map((risk) => (
              <tr key={risk.id} onClick={() => openDetail(risk.id)} className="clickable">
                <td>{risk.id}</td><td><RiskBadge level={risk.risk_level} /></td><td>{risk.title}</td><td>{risk.status}</td><td>{Math.round(risk.confidence * 100)}%</td>
              </tr>
            ))}
          </tbody></table>
        </div>
        <div className="panel detail">
          {detail ? (
            <>
              <h3>{detail.title}</h3>
              <RiskBadge level={detail.risk_level} />
              <p>{detail.description}</p>
              <h4>证据链</h4>
              {detail.evidence.map((item) => <blockquote key={item.id}>{item.reason}<br />{item.source_text}</blockquote>)}
              <button onClick={() => review('confirmed')}>确认风险</button>
              <button onClick={() => review('false_positive')}>标记误报</button>
            </>
          ) : <p>点击左侧风险查看详情。</p>}
        </div>
      </div>
    </section>
  )
}
