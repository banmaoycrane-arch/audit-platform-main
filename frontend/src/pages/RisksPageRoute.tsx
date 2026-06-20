import { useEffect, useState } from 'react'
import { api, type AuditRisk } from '../api/client'
import { RisksPage } from './RisksPage'

export function RisksPageRoute() {
  const [risks, setRisks] = useState<AuditRisk[]>([])

  const refresh = async () => {
    try {
      const data = await api.listRisks()
      setRisks(data)
    } catch {
      setRisks([])
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  return <RisksPage risks={risks} onChanged={refresh} />
}
