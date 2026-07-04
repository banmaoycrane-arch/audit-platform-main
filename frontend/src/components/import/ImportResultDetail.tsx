import { Card, Typography, Space, Tag, Modal, Button, Input, message } from 'antd'
import { EditOutlined, SaveOutlined, DeleteOutlined, CheckOutlined } from '@ant-design/icons'
import { useState } from 'react'
import type { AccountingEntry, EntryTag, Counterparty } from '../../api/client'
import { AccountCompareView } from './AccountCompareView'
import { TagList } from './TagList'
import { CounterpartyInfo } from './CounterpartyInfo'
import { formatAmount } from '../../money'

const { Title, Text } = Typography

interface ImportResultDetailProps {
  entry: AccountingEntry
  tags: EntryTag[]
  counterparty?: Counterparty
  onClose: () => void
  onUpdate?: (entryId: number, updates: Partial<AccountingEntry>) => void
}

export function ImportResultDetail({ entry, tags, counterparty, onClose, onUpdate }: ImportResultDetailProps) {
  const [editingField, setEditingField] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [pendingUpdates, setPendingUpdates] = useState<Partial<AccountingEntry>>({})

  const handleEditStart = (field: string, currentValue: string | null | number) => {
    setEditingField(field)
    setEditValue(String(currentValue || ''))
  }

  const handleEditSave = () => {
    if (!editingField) return

    const updates: Partial<AccountingEntry> = {}
    if (editingField === 'summary') {
      updates.summary = editValue || null
    } else if (editingField === 'account_name') {
      updates.account_name = editValue || null
    } else if (editingField === 'counterparty') {
      updates.counterparty = editValue || null
    }

    setPendingUpdates((prev) => ({ ...prev, ...updates }))
    setEditingField(null)
    setEditValue('')

    if (onUpdate && Object.keys(updates).length > 0) {
      onUpdate(entry.id, updates)
    }
  }

  const handleEditCancel = () => {
    setEditingField(null)
    setEditValue('')
  }

  const renderEditableField = (
    label: string,
    field: string,
    value: string | null | number,
    width?: string
  ) => {
    const displayValue = String(value || '-')
    const isEditing = editingField === field

    return (
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0', width }}>
        <Text type="secondary" style={{ fontSize: 12 }}>{label}</Text>
        <Space size="small">
          {isEditing ? (
            <>
              <Input
                size="small"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                autoFocus
                onPressEnter={handleEditSave}
                style={{ width: width || 150 }}
              />
              <Button
                size="small"
                icon={<SaveOutlined />}
                onClick={handleEditSave}
                type="primary"
              />
              <Button size="small" icon={<DeleteOutlined />} onClick={handleEditCancel} />
            </>
          ) : (
            <>
              <span style={{ fontSize: 12 }}>{displayValue}</span>
              <Button
                size="small"
                icon={<EditOutlined />}
                onClick={() => handleEditStart(field, value)}
              />
            </>
          )}
        </Space>
      </div>
    )
  }

  return (
    <Modal
      title="分录详情"
      open
      onCancel={onClose}
      width={700}
      footer={
        <Space>
          {Object.keys(pendingUpdates).length > 0 && (
            <Tag color="blue">已修改</Tag>
          )}
          <Button onClick={onClose}>关闭</Button>
        </Space>
      }
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <Card size="small">
          <Title level={5} style={{ marginBottom: 12 }}>
            基本信息
            {entry.requires_llm_resolution && (
              <Tag color="orange" style={{ marginLeft: 8 }}>待LLM解析</Tag>
            )}
          </Title>

          <Space direction="vertical" style={{ width: '100%' }}>
            {renderEditableField('凭证号', 'voucher_no', entry.voucher_no)}
            {renderEditableField('日期', 'voucher_date', entry.voucher_date)}
            {renderEditableField('行号', 'entry_line_no', entry.entry_line_no)}
            {renderEditableField('摘要', 'summary', entry.summary, '300')}
          </Space>
        </Card>

        <AccountCompareView entry={entry} />

        <Card size="small">
          <Title level={5} style={{ marginBottom: 12 }}>金额信息</Title>
          <Space direction="vertical" style={{ width: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
              <Text type="secondary" style={{ fontSize: 12 }}>借方金额</Text>
              <span style={{ fontSize: 14, fontWeight: 500, color: '#cf1322' }}>
                {entry.debit_amount > 0 ? formatAmount(entry.debit_amount) : '-'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
              <Text type="secondary" style={{ fontSize: 12 }}>贷方金额</Text>
              <span style={{ fontSize: 14, fontWeight: 500, color: '#3f8600' }}>
                {entry.credit_amount > 0 ? formatAmount(entry.credit_amount) : '-'}
              </span>
            </div>
          </Space>
        </Card>

        <CounterpartyInfo entry={entry} counterparty={counterparty} />

        <TagList tags={tags} entryId={entry.id} />
      </Space>
    </Modal>
  )
}
