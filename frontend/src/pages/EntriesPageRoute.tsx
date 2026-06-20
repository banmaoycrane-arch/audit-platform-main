import { useEffect, useState } from 'react'
import { api, type AccountingEntry } from '../api/client'
import { EntriesPage } from './EntriesPage'

export function EntriesPageRoute() {
  const [entries, setEntries] = useState<AccountingEntry[]>([])
  useEffect(() => {
    api.listEntries().then(setEntries).catch(() => setEntries([]))
  }, [])
  return <EntriesPage entries={entries} />
}
