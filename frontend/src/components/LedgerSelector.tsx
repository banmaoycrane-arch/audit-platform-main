import { Button, Divider, Form, Input, message, Modal, Select, Tag, DatePicker } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import dayjs from 'dayjs'
import { api } from '../api/client'
import type { Team } from '../api/client'
import { useAuthStore } from '../stores/authStore'

const ledgerStatusColorMap: Record<string, string> = {
  draft: 'default',
  active: 'success',
  suspended: 'warning',
  archived: 'error',
  deleted: 'red',
}

const ledgerStatusLabelMap: Record<string, string> = {
  draft: '草稿',
  active: '活跃',
  suspended: '暂停',
  archived: '归档',
  deleted: '删除',
}

export function LedgerSelector() {
  const { currentLedgerId, setCurrentLedger, userLedgers, setUserLedgers, refreshAuthContext } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [teams, setTeams] = useState<Team[]>([])
  const [form] = Form.useForm()

  const loadLedgers = () => {
    setLoading(true)
    api
      .listLedgers()
      .then((ledgers) => {
        setUserLedgers(ledgers)
        if (!currentLedgerId) {
          const defaultLedger = ledgers.find((l) => l.is_default)
          if (defaultLedger) {
            setCurrentLedger(defaultLedger.id)
          } else if (ledgers.length > 0) {
            setCurrentLedger(ledgers[0].id)
          }
        }
      })
      .catch(() => {
        // 静默失败，不影响页面渲染
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (userLedgers.length === 0) {
      loadLedgers()
    }
  }, [userLedgers.length])

  const openCreateModal = async () => {
    setCreateOpen(true)
    try {
      const nextTeams = await api.listTeams()
      setTeams(nextTeams)
      if (nextTeams.length === 1) {
        form.setFieldValue('team_id', nextTeams[0].id)
      }
    } catch {
      message.error('加载团队列表失败，请先确认当前用户已加入团队')
    }
  }

  const handleCreateLedger = async () => {
    const values = await form.validateFields()
    setCreating(true)
    try {
      const ledger = await api.createLedger({
        team_id: values.team_id,
        name: values.name,
        accounting_start_date: values.accounting_start_date
          ? dayjs(values.accounting_start_date).format('YYYY-MM-DD')
          : undefined,
      })
      await api.createEntity({
        entity_name: values.entity_name || values.name,
        entity_code: values.entity_code || null,
        ledger_id: ledger.id,
        entity_type: 'company',
        entity_category: 'parent',
        is_accounting_entity: true,
        is_legal_entity: true,
      })
      await api.switchLedger(ledger.id)
      const nextLedgers = [...userLedgers.filter((item) => item.id !== ledger.id), ledger]
      setUserLedgers(nextLedgers)
      setCurrentLedger(ledger.id)
      await refreshAuthContext()
      setCreateOpen(false)
      form.resetFields()
      message.success('账套创建成功，已切换到新账套')
    } catch (error: any) {
      message.error(error.message || '账套创建失败')
    } finally {
      setCreating(false)
    }
  }

  const handleChange = async (value: number) => {
    const selected = userLedgers.find((l) => l.id === value)
    if (!selected) return
    setLoading(true)
    try {
      await api.switchLedger(value)
      setCurrentLedger(value)
      message.success('账套已切换')
    } catch (error: any) {
      message.error(error.message || '切换账套失败')
    } finally {
      setLoading(false)
    }
  }

  const currentLedger = userLedgers.find((l) => l.id === currentLedgerId)

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ color: '#fff', fontSize: 14 }}>账套：</span>
      <Select
        value={currentLedgerId || undefined}
        onChange={handleChange}
        loading={loading}
        style={{ minWidth: 180 }}
        placeholder="选择账套"
        optionLabelProp="label"
        dropdownMatchSelectWidth={false}
        popupRender={(menu) => (
          <>
            {menu}
            <Divider style={{ margin: '8px 0' }} />
            <div style={{ padding: '0 8px 8px' }}>
              <Button type="link" icon={<PlusOutlined />} block onClick={openCreateModal}>
                新建账套
              </Button>
            </div>
          </>
        )}
      >
        {userLedgers.map((ledger) => (
          <Select.Option key={ledger.id} value={ledger.id} label={ledger.name}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span>{ledger.name}</span>
              {ledger.is_default && (
                <Tag color="blue" style={{ marginLeft: 8, fontSize: 12 }}>
                  默认
                </Tag>
              )}
              <Tag
                color={ledgerStatusColorMap[ledger.status] || 'default'}
                style={{ marginLeft: 8, fontSize: 12 }}
              >
                {ledgerStatusLabelMap[ledger.status] || ledger.status}
              </Tag>
            </div>
          </Select.Option>
        ))}
      </Select>
      {currentLedger && (
        <Tag color="green" style={{ fontSize: 12 }}>
          {currentLedger.role}
        </Tag>
      )}
      <Modal
        title="新建账套"
        open={createOpen}
        onOk={handleCreateLedger}
        onCancel={() => setCreateOpen(false)}
        confirmLoading={creating}
        okText="创建并切换"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Form.Item name="team_id" label="所属团队" rules={[{ required: true, message: '请选择账套所属团队' }]}>
            <Select
              placeholder="请选择团队"
              options={teams.map((team) => ({ value: team.id, label: team.name }))}
            />
          </Form.Item>
          <Form.Item name="name" label="账套名称" rules={[{ required: true, message: '请输入账套名称' }]}>
            <Input placeholder="例如：XX公司2026账套" />
          </Form.Item>
          <Form.Item
            name="accounting_start_date"
            label="会计时间线起点"
            initialValue={dayjs()}
            rules={[{ required: true, message: '请选择会计时间线起点' }]}
          >
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="entity_name" label="会计主体名称">
            <Input placeholder="默认使用账套名称；建议填写真实甲方/核算主体名称" />
          </Form.Item>
          <Form.Item name="entity_code" label="统一社会信用代码 / 主体编码">
            <Input placeholder="可选，用于合同、发票、审计证据匹配" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
