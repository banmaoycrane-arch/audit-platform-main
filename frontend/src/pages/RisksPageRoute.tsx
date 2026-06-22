import { useEffect, useState } from 'react'
import { api, type AuditRisk } from '../api/client'
import { useAuthStore } from '../stores/authStore'
import { RisksPage } from './RisksPage'

export function RisksPageRoute() {
  const { currentLedgerId } = useAuthStore()
  const [risks, setRisks] = useState<AuditRisk[]>([])

  const refresh = async () => {
    if (!currentLedgerId) {
      setRisks([])
      return
    }
    try {
      const data = await api.listRisks(undefined, currentLedgerId)
      setRisks(data)
    } catch {
      setRisks([])
    }
  }

  useEffect(() => {
    void refresh()
  }, [currentLedgerId])

  return <RisksPage risks={risks} onChanged={refresh} />
}
