import { useEffect, useState } from 'react'
import { api, type AccountingEntry } from '../api/client'
import { useAuthStore } from '../stores/authStore'
import { EntriesPage } from './EntriesPage'

export function EntriesPageRoute() {
  const { currentLedgerId } = useAuthStore()
  const [entries, setEntries] = useState<AccountingEntry[]>([])

  useEffect(() => {
    if (!currentLedgerId) {
      setEntries([])
      return
    }
    api.listEntries(undefined, currentLedgerId).then(setEntries).catch(() => setEntries([]))
  }, [currentLedgerId])

  return <EntriesPage entries={entries} />
}
