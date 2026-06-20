import { useState } from 'react'
import { api, type AccountingEntry } from '../api/client'

export function EntriesPage({ entries }: { entries: AccountingEntry[] }) {
  const [similar, setSimilar] = useState<string>('')

  async function search(entryId: number) {
    const result = await api.similarSearch(entryId)
    setSimilar(JSON.stringify(result, null, 2))
  }

  return (
    <section>
      <h2>会计分录</h2>
      <div className="panel table-wrap">
        <table><thead><tr><th>ID</th><th>凭证号</th><th>行号</th><th>日期</th><th>摘要</th><th>科目</th><th>借方</th><th>贷方</th><th>往来单位</th><th>向量检索</th></tr></thead><tbody>
          {entries.map((entry) => (
            <tr key={entry.id}>
              <td>{entry.id}</td><td>{entry.voucher_no}</td><td>{entry.entry_line_no}</td><td>{entry.voucher_date}</td><td>{entry.summary}</td><td>{entry.account_name}</td>
              <td>{entry.debit_amount}</td><td>{entry.credit_amount}</td><td>{entry.counterparty}</td>
              <td><button onClick={() => search(entry.id)}>相似</button></td>
            </tr>
          ))}
        </tbody></table>
      </div>
      {similar && <pre className="panel pre">{similar}</pre>}
    </section>
  )
}
