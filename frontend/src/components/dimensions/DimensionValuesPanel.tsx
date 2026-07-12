import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'
import { PlusOutlined, ReloadOutlined, UploadOutlined, DeleteOutlined } from '@ant-design/icons'
import {
  api,
  type BankAccount,
  type Counterparty,
  type DimensionRegistryResponse,
  type EntryTagAggregate,
  type TagCategoryNode,
} from '../../api/client'
import { formatDimensionTagLabel } from '../staging/formatDimensionTag'
import {
  flattenTagCategories,
  isMonetaryFundAccount,
  masterDataCollectionLabel,
  resolveDimensionValueSource,
  resolveMasterDataCollectionKind,
  isSharedTagValueReady,
  type MasterDataCollectionKind,
} from './dimensionUtils'
import { BANK_ACCOUNT_CATEGORY_CODE, categoryDisplayLabel } from './tagCategoryConstants'

const { Text } = Typography

const ROLE_LABEL: Record<string, string> = {
  customer: '客户',
  supplier: '供应商',
  related_party: '关联方',
  government: '政府/税务',
  individual: '个人',
  internal: '内部',
  other: '其他',
}

const ROLE_OPTIONS = Object.entries(ROLE_LABEL).map(([value, label]) => ({ value, label }))

function normalizeBankLabel(value: string): string {
  return value.replace(/银行/g, '').replace(/存款/g, '').trim().toLowerCase()
}

function isBankRegistryItemRegistered(
  item: { source_sub_code?: string | null; display_name?: string; tag_value?: string },
  banks: BankAccount[],
): boolean {
  const sub = (item.source_sub_code || '').trim()
  if (sub && banks.some((bank) => (bank.source_sub_code || '').trim() === sub)) {
    return true
  }
  const label = normalizeBankLabel((item.display_name || item.tag_value || '').trim())
  if (!label) return false
  return banks.some((bank) => {
    const bankLabel = normalizeBankLabel(bank.bank_name || '')
    const accountLabel = normalizeBankLabel(bank.account_name || '')
    return bankLabel === label || accountLabel === label || (bank.bank_name || '').trim() === (item.display_name || item.tag_value || '').trim()
  })
}

function buildBankPrefillFromRegistry(item: {
  source_sub_code?: string | null
  display_name?: string
  tag_value?: string
  account_code?: string
}): Record<string, string> | null {
  if (!isMonetaryFundAccount(item.account_code)) {
    return null
  }
  const branchName = (item.display_name || item.tag_value || '').trim()
  return {
    source_sub_code: (item.source_sub_code || '').trim(),
    bank_name: branchName,
    account_name: branchName,
    coa_account_code: item.account_code?.startsWith('1001') ? '1001' : '1002',
  }
}

function buildCounterpartyPrefillFromRegistry(item: {
  display_name?: string
  tag_value?: string
}): Record<string, string> {
  const name = (item.display_name || item.tag_value || '').trim()
  return { name }
}

function parseCsvText(text: string): Array<Record<string, string>> {
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
  if (lines.length < 2) return []
  const headers = lines[0].split(',').map((h) => h.trim())
  return lines.slice(1).map((line) => {
    const cells = line.split(',').map((c) => c.trim())
    const record: Record<string, string> = {}
    headers.forEach((header, idx) => {
      record[header] = cells[idx] || ''
    })
    return record
  })
}

type DimensionValuesPanelProps = {
  ledgerId: number
  categories: TagCategoryNode[]
  jobId?: number
  registry?: DimensionRegistryResponse | null
  onChanged?: () => void
  selectedCategoryCode?: string
  onCategoryChange?: (code: string) => void
}

export function DimensionValuesPanel({
  ledgerId,
  categories,
  jobId = 0,
  registry,
  onChanged,
  selectedCategoryCode,
  onCategoryChange,
}: DimensionValuesPanelProps) {
  const flatCategories = useMemo(() => flattenTagCategories(categories), [categories])
  const [categoryCode, setCategoryCode] = useState(
    selectedCategoryCode === 'account_detail' ? BANK_ACCOUNT_CATEGORY_CODE : selectedCategoryCode || BANK_ACCOUNT_CATEGORY_CODE,
  )
  const [loading, setLoading] = useState(false)
  const [banks, setBanks] = useState<BankAccount[]>([])
  const [counterparties, setCounterparties] = useState<Counterparty[]>([])
  const [aggregates, setAggregates] = useState<EntryTagAggregate[]>([])
  const [bankModalOpen, setBankModalOpen] = useState(false)
  const [editingBankId, setEditingBankId] = useState<number | null>(null)
  const [bankSaving, setBankSaving] = useState(false)
  const [cpModalOpen, setCpModalOpen] = useState(false)
  const [editingCounterpartyId, setEditingCounterpartyId] = useState<number | null>(null)
  const [cpSaving, setCpSaving] = useState(false)
  const [selectedCpIds, setSelectedCpIds] = useState<number[]>([])
  const [batchRoleOpen, setBatchRoleOpen] = useState(false)
  const [batchRoleSaving, setBatchRoleSaving] = useState(false)
  const [batchRoleForm] = Form.useForm()
  const [bankForm] = Form.useForm()
  const [cpForm] = Form.useForm()

  const selectedCategory = useMemo(
    () => flatCategories.find((c) => c.code === categoryCode) || flatCategories[0],
    [flatCategories, categoryCode],
  )
  const valueSource = useMemo(
    () => (selectedCategory ? resolveDimensionValueSource(selectedCategory) : { source: 'aggregate' as const }),
    [selectedCategory],
  )

  useEffect(() => {
    if (!selectedCategoryCode || selectedCategoryCode === categoryCode) return
    if (!flatCategories.some((c) => c.code === selectedCategoryCode)) return
    setCategoryCode(selectedCategoryCode)
  }, [selectedCategoryCode, categoryCode, flatCategories])

  useEffect(() => {
    if (!flatCategories.length) return
    if (flatCategories.some((c) => c.code === categoryCode)) return
    setCategoryCode(flatCategories[0].code)
  }, [flatCategories, categoryCode])

  const registryForCategory = useMemo(() => {
    if (!registry) return []
    return registry.items.filter((item) => item.category_code === categoryCode)
  }, [registry, categoryCode])

  const loadValues = useCallback(async () => {
    if (!selectedCategory) return
    const vs = resolveDimensionValueSource(selectedCategory)
    setLoading(true)
    try {
      if (vs.source === 'bank_accounts') {
        const data = await api.listBankAccounts(ledgerId)
        setBanks(data)
      } else if (vs.source === 'counterparties') {
        const data = await api.listCounterparties()
        setCounterparties(
          vs.counterpartyRole
            ? data.filter((cp) => cp.role === vs.counterpartyRole && cp.is_active)
            : data.filter((cp) => cp.is_active),
        )
      } else {
        const data = await api.aggregateEntryTags(ledgerId, categoryCode)
        setAggregates(data)
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载维度值失败')
    } finally {
      setLoading(false)
    }
  }, [ledgerId, categoryCode, selectedCategory])

  useEffect(() => {
    void loadValues()
  }, [loadValues])

  useEffect(() => {
    setSelectedCpIds([])
  }, [categoryCode])

  const handleCategorySelect = (code: string) => {
    setCategoryCode(code)
    onCategoryChange?.(code)
  }

  const notifyChanged = () => {
    void loadValues()
    onChanged?.()
  }

  const openBankModal = (prefill?: Record<string, string> | null, bank?: BankAccount) => {
    setEditingBankId(bank?.id ?? null)
    bankForm.resetFields()
    bankForm.setFieldsValue({
      coa_account_code: '1002',
      ...prefill,
      ...(bank
        ? {
            source_sub_code: bank.source_sub_code || '',
            bank_name: bank.bank_name,
            account_no: bank.account_no,
            account_name: bank.account_name,
            coa_account_code: bank.coa_account_code || '1002',
          }
        : {}),
    })
    setBankModalOpen(true)
  }

  const handleSaveBank = async () => {
    try {
      const values = await bankForm.validateFields()
      setBankSaving(true)
      const payload = {
        bank_name: String(values.bank_name || '').trim(),
        account_no: String(values.account_no || '').trim(),
        account_name: String(values.account_name || '').trim(),
        coa_account_code: String(values.coa_account_code || '1002').trim() || '1002',
        source_sub_code: String(values.source_sub_code || '').trim() || null,
      }
      if (editingBankId) {
        await api.updateBankAccount(ledgerId, editingBankId, payload)
        message.success('银行账户已更新')
      } else {
        await api.createBankAccount(ledgerId, payload)
        message.success('银行账户已登记')
      }
      setBankModalOpen(false)
      setEditingBankId(null)
      bankForm.resetFields()
      notifyChanged()
    } catch (error) {
      if (error && typeof error === 'object' && 'errorFields' in error) {
        return
      }
      message.error(error instanceof Error ? error.message : '保存银行账户失败')
    } finally {
      setBankSaving(false)
    }
  }

  const handleDeleteBank = (bank: BankAccount) => {
    const usedInBatch = registryForCategory.some(
      (item) =>
        (item.source_sub_code && item.source_sub_code === bank.source_sub_code) ||
        isBankRegistryItemRegistered(item, [bank]),
    )
    Modal.confirm({
      title: '删除这条银行账户？',
      content: usedInBatch
        ? `「${bank.account_name || bank.bank_name}」本批序时簿仍在使用。删除后只是从主数据移除，不影响已导入分录；可重新补登记。`
        : `将从主数据移除「${bank.account_name || bank.bank_name}」，误登记时可删除后重建。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.deleteBankAccount(ledgerId, bank.id)
          message.success('已删除')
          if (editingBankId === bank.id) {
            setBankModalOpen(false)
            setEditingBankId(null)
            bankForm.resetFields()
          }
          notifyChanged()
        } catch (error) {
          message.error(error instanceof Error ? error.message : '删除失败')
        }
      },
    })
  }

  const openCounterpartyModal = (prefill?: Record<string, string>, counterparty?: Counterparty) => {
    setEditingCounterpartyId(counterparty?.id ?? null)
    cpForm.resetFields()
    cpForm.setFieldsValue(
      counterparty
        ? {
            name: counterparty.name,
            role: counterparty.role,
            unified_credit_no: counterparty.unified_credit_no || '',
            is_related_party: counterparty.is_related_party,
          }
        : {
            role: valueSource.counterpartyRole || 'other',
            is_related_party: false,
            ...prefill,
          },
    )
    setCpModalOpen(true)
  }

  const handleRegisterFromRegistry = (
    row: (typeof registryForCategory)[number],
    kind: MasterDataCollectionKind,
  ) => {
    if (kind === 'bank_account') {
      const prefill = buildBankPrefillFromRegistry(row)
      if (!prefill) {
        message.warning('仅货币资金科目（1001/1002）需登记银行账户')
        return
      }
      openBankModal(prefill)
      return
    }
    if (kind === 'counterparty') {
      openCounterpartyModal(buildCounterpartyPrefillFromRegistry(row))
      return
    }
    if (kind === 'shared_tag') {
      message.info('共享 Tag 由分录自动沉淀；可在待处理队列或 Step4 补规范名，也可在「维度分类」新增自定义 Tag 继续细分')
      return
    }
  }

  const isRegistryItemInMaster = (
    row: (typeof registryForCategory)[number],
    kind: MasterDataCollectionKind,
  ): boolean => {
    if (kind === 'shared_tag') {
      return isSharedTagValueReady(row, masterNames)
    }
    if (kind === 'bank_account') return isBankRegistryItemRegistered(row, banks)
    const name = (row.display_name || row.tag_value || '').trim()
    return Boolean(name && masterNames.has(name))
  }

  const handleSaveCounterparty = async () => {
    try {
      const values = await cpForm.validateFields()
      setCpSaving(true)
      const payload = {
        name: String(values.name || '').trim(),
        role: String(values.role || 'other'),
        unified_credit_no: String(values.unified_credit_no || '').trim() || null,
        is_related_party: Boolean(values.is_related_party),
      }
      if (editingCounterpartyId) {
        await api.updateCounterparty(editingCounterpartyId, payload)
        message.success('往来单位已更新')
      } else {
        await api.createCounterparty(payload)
        message.success('往来单位已创建')
      }
      setCpModalOpen(false)
      setEditingCounterpartyId(null)
      cpForm.resetFields()
      notifyChanged()
    } catch (error) {
      if (error && typeof error === 'object' && 'errorFields' in error) {
        return
      }
      message.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setCpSaving(false)
    }
  }

  const handleDeleteCounterparty = (counterparty: Counterparty) => {
    const usedInBatch = registryForCategory.some(
      (item) => item.tag_value === counterparty.name || item.display_name === counterparty.name,
    )
    Modal.confirm({
      title: '删除这条往来单位？',
      content: usedInBatch
        ? `「${counterparty.name}」本批序时簿仍在使用。删除后只是从主数据移除，不影响已导入分录。`
        : `将从主数据移除「${counterparty.name}」，误登记时可删除后重建。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.disableCounterparty(counterparty.id)
          message.success('已删除')
          if (editingCounterpartyId === counterparty.id) {
            setCpModalOpen(false)
            setEditingCounterpartyId(null)
            cpForm.resetFields()
          }
          setSelectedCpIds((prev) => prev.filter((id) => id !== counterparty.id))
          notifyChanged()
        } catch (error) {
          message.error(error instanceof Error ? error.message : '删除失败')
        }
      },
    })
  }

  const defaultBatchRole = useMemo(() => {
    if (categoryCode === 'customer') return 'customer'
    if (categoryCode === 'supplier') return 'supplier'
    return 'other'
  }, [categoryCode])

  const openBatchRoleModal = () => {
    if (!selectedCpIds.length) {
      message.warning('请先勾选要变更的往来单位')
      return
    }
    batchRoleForm.resetFields()
    batchRoleForm.setFieldsValue({ role: defaultBatchRole })
    setBatchRoleOpen(true)
  }

  const handleBatchUpdateRole = async () => {
    try {
      const values = await batchRoleForm.validateFields()
      setBatchRoleSaving(true)
      const role = String(values.role || 'other')
      const result = await api.batchUpdateCounterpartyRole({ ids: selectedCpIds, role })
      message.success(`已更新 ${result.updated} 条往来单位的角色为「${ROLE_LABEL[role] || role}」`)
      if (result.skipped_ids?.length) {
        message.warning(`${result.skipped_ids.length} 条未找到或已停用，已跳过`)
      }
      setBatchRoleOpen(false)
      setSelectedCpIds([])
      batchRoleForm.resetFields()
      notifyChanged()
    } catch (error) {
      if (error && typeof error === 'object' && 'errorFields' in error) {
        return
      }
      message.error(error instanceof Error ? error.message : '批量更新失败')
    } finally {
      setBatchRoleSaving(false)
    }
  }

  const handleCsvImport = async (file: File) => {
    const text = await file.text()
    const records = parseCsvText(text)
    if (!records.length) {
      message.error('CSV 为空或格式不正确')
      return false
    }
    const result = await api.bulkImportBankAccounts(ledgerId, records)
    message.success(`导入完成：新增 ${result.created}，跳过/更新 ${result.skipped}`)
    notifyChanged()
    return false
  }

  const masterNames = useMemo(() => {
    if (valueSource.source === 'bank_accounts') {
      return new Set(banks.map((b) => (b.account_name || b.bank_name || '').trim()).filter(Boolean))
    }
    if (valueSource.source === 'counterparties') {
      return new Set(counterparties.map((cp) => cp.name.trim()).filter(Boolean))
    }
    return new Set(aggregates.map((a) => a.tag_value.trim()).filter(Boolean))
  }, [valueSource, banks, counterparties, aggregates])

  const usedNotInMaster = useMemo(() => {
    return registryForCategory.filter((item) => {
      const kind = resolveMasterDataCollectionKind(item)
      return !isRegistryItemInMaster(item, kind)
    })
  }, [registryForCategory, masterNames, banks])

  const bankColumns: ColumnsType<BankAccount> = [
    { title: '来源段', dataIndex: 'source_sub_code', width: 72, render: (v) => v || '-' },
    { title: '开户银行', dataIndex: 'bank_name', ellipsis: true },
    { title: '账号', dataIndex: 'account_no', width: 140, ellipsis: true },
    { title: '户名（规范全称）', dataIndex: 'account_name', ellipsis: true },
    { title: '关联科目', dataIndex: 'coa_account_code', width: 80 },
    {
      title: '本批使用',
      key: 'used',
      width: 72,
      render: (_, row) => {
        const used = registryForCategory.some(
          (item) =>
            (item.source_sub_code && item.source_sub_code === row.source_sub_code) ||
            isBankRegistryItemRegistered(item, [row]),
        )
        return used ? <Tag color="blue">是</Tag> : <Tag>否</Tag>
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_, row) => (
        <Space size={4}>
          <Button type="link" size="small" onClick={() => openBankModal(undefined, row)}>
            编辑
          </Button>
          <Button type="link" size="small" danger onClick={() => handleDeleteBank(row)}>
            删除
          </Button>
        </Space>
      ),
    },
  ]

  const cpColumns: ColumnsType<Counterparty> = [
    { title: '名称', dataIndex: 'name', ellipsis: true },
    { title: '角色', dataIndex: 'role', width: 88, render: (v: string) => ROLE_LABEL[v] || v },
    { title: '信用代码', dataIndex: 'unified_credit_no', width: 160, render: (v) => v || '-' },
    {
      title: '关联方',
      dataIndex: 'is_related_party',
      width: 72,
      render: (v: boolean) => (v ? <Tag color="red">是</Tag> : <Tag>否</Tag>),
    },
    {
      title: '本批使用',
      key: 'used',
      width: 72,
      render: (_, row) => {
        const used = registryForCategory.some(
          (item) => item.tag_value === row.name || item.display_name === row.name,
        )
        return used ? <Tag color="blue">是</Tag> : <Tag>否</Tag>
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_, row) => (
        <Space size={4}>
          <Button type="link" size="small" onClick={() => openCounterpartyModal(undefined, row)}>
            编辑
          </Button>
          <Button type="link" size="small" danger onClick={() => handleDeleteCounterparty(row)}>
            删除
          </Button>
        </Space>
      ),
    },
  ]

  const aggregateColumns: ColumnsType<EntryTagAggregate> = [
    { title: '维度值', dataIndex: 'tag_value', ellipsis: true },
    { title: '分录次数', dataIndex: 'count', width: 88 },
    { title: '平均权重', dataIndex: 'avg_weight', width: 88, render: (v: number) => v?.toFixed(2) ?? '-' },
    {
      title: '本批使用',
      key: 'used',
      width: 88,
      render: (_, row) => {
        const used = registryForCategory.some((item) => item.tag_value === row.tag_value)
        return used ? <Tag color="blue">是</Tag> : <Tag>否</Tag>
      },
    },
  ]

  const renderActions = () => {
    if (valueSource.source === 'bank_accounts') {
      return (
        <Space>
          <Upload accept=".csv,.txt" showUploadList={false} beforeUpload={handleCsvImport}>
            <Button icon={<UploadOutlined />}>导入 CSV</Button>
          </Upload>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => openBankModal()}>
            登记账户
          </Button>
        </Space>
      )
    }
    if (valueSource.source === 'counterparties') {
      return (
        <Space wrap>
          <Button
            disabled={!selectedCpIds.length}
            onClick={openBatchRoleModal}
          >
            批量变更角色{selectedCpIds.length ? `（${selectedCpIds.length}）` : ''}
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => openCounterpartyModal()}>
            新增往来单位
          </Button>
          <Link to="/basic/counterparties">完整管理页</Link>
        </Space>
      )
    }
    return (
      <Text type="secondary" style={{ fontSize: 12 }}>
        共享 Tag 值由入账分录自动沉淀，跨模块共用；可补规范名，或在「维度分类」新建自定义 Tag 继续细分口径。
      </Text>
    )
  }

  return (
    <div>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="维度值主数据（配置层 / 证据层）"
        description="三类维护方式：① 银行账户/往来单位 → 实体档案（原辅助核算字段保留）；② 部门/项目/费用类型等 → 共享 Tag（存 EntryTag，各模块通用，避免多表重复）；③ 自定义 Tag 可随时叠加，规则配好后支持口径切换。"
      />

      <Space wrap style={{ marginBottom: 16 }}>
        <span>维度分类</span>
        <Select
          style={{ minWidth: 260 }}
          value={categoryCode}
          onChange={handleCategorySelect}
          options={flatCategories.map((c) => ({
            value: c.code,
            label: categoryDisplayLabel(c.code, c.name),
          }))}
        />
        <Button icon={<ReloadOutlined />} onClick={() => void loadValues()} loading={loading}>
          刷新
        </Button>
        {renderActions()}
      </Space>

      {selectedCategory && (
        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          数据源：
          {valueSource.source === 'bank_accounts' && '银行账户主数据（仅适用于 1001/1002 货币资金）'}
          {valueSource.source === 'counterparties' &&
            `往来单位主数据${valueSource.counterpartyRole ? ` · ${ROLE_LABEL[valueSource.counterpartyRole]}` : ''}（名称、角色、信用代码、关联方等，对应原辅助核算档案）`}
          {valueSource.source === 'aggregate' &&
            '共享 Tag · 已入账分录聚合（部门/项目/费用类型等，跨模块共用 EntryTag）'}
          {selectedCategory.source_table ? ` · source_table=${selectedCategory.source_table}` : ''}
        </Text>
      )}

      {jobId > 0 && usedNotInMaster.length > 0 && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message={`本批序时簿有 ${usedNotInMaster.length} 个「${selectedCategory?.name || categoryCode}」值待完善`}
          description={
            <>
              {usedNotInMaster
                .slice(0, 8)
                .map((item) =>
                  formatDimensionTagLabel({
                    source_sub_code: item.source_sub_code,
                    display_name: item.display_name,
                    tag_value: item.tag_value,
                  }),
                )
                .join('、')}
              {usedNotInMaster.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  {(() => {
                    const first = usedNotInMaster[0]
                    const kind = resolveMasterDataCollectionKind(first)
                    if (kind === 'bank_account') {
                      const prefill = buildBankPrefillFromRegistry(first)
                      return (
                        <>
                          <Button
                            size="small"
                            type="primary"
                            disabled={!prefill}
                            onClick={() => prefill && openBankModal(prefill)}
                          >
                            补登记第一项（银行账户）
                          </Button>
                          <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                            仅货币资金科目需填写开户银行、账号与户名全称。
                          </Text>
                        </>
                      )
                    }
                    if (kind === 'counterparty') {
                      return (
                        <>
                          <Button
                            size="small"
                            type="primary"
                            onClick={() => openCounterpartyModal(buildCounterpartyPrefillFromRegistry(first))}
                          >
                            补登记第一项（往来单位）
                          </Button>
                        </>
                      )
                    }
                    return null
                  })()}
                </div>
              )}
            </>
          }
        />
      )}

      {valueSource.source === 'counterparties' && categoryCode === 'counterparty_object' && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="往来对象 · 初始归类"
          description="本页展示全部角色的往来单位。导入后若角色均为「其他」，可勾选多条后使用「批量变更角色」一次性设为客户、供应商、个人等，便于初始主数据设计。"
        />
      )}

      {valueSource.source === 'bank_accounts' && (
        <Table rowKey="id" size="small" loading={loading} columns={bankColumns} dataSource={banks} pagination={{ pageSize: 15 }} />
      )}
      {valueSource.source === 'counterparties' && (
        <Table
          rowKey="id"
          size="small"
          loading={loading}
          columns={cpColumns}
          dataSource={counterparties}
          pagination={{ pageSize: 15 }}
          rowSelection={{
            selectedRowKeys: selectedCpIds,
            onChange: (keys) => setSelectedCpIds(keys.map(Number)),
          }}
        />
      )}
      {valueSource.source === 'aggregate' && (
        <Table rowKey="tag_value" size="small" loading={loading} columns={aggregateColumns} dataSource={aggregates} pagination={{ pageSize: 15 }} />
      )}

      {jobId > 0 && registryForCategory.length > 0 && (
        <Card size="small" title="本批序时簿使用层" style={{ marginTop: 16 }}>
          <Table
            size="small"
            rowKey={(r) => `${r.account_code}-${r.source_sub_code}-${r.tag_value}`}
            pagination={false}
            dataSource={registryForCategory}
            columns={[
              {
                title: '维度实例',
                render: (_, row) =>
                  formatDimensionTagLabel({
                    source_sub_code: row.source_sub_code,
                    display_name: row.display_name,
                    tag_value: row.tag_value,
                  }),
              },
              { title: '入账科目', key: 'acct', render: (_, r) => `${r.account_code} ${r.account_name}`.trim() },
              { title: '分录行', dataIndex: 'line_count', width: 72 },
              {
                title: '收集粒度',
                key: 'collection_kind',
                width: 120,
                render: (_, row) => {
                  const kind = resolveMasterDataCollectionKind(row)
                  return (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {masterDataCollectionLabel(kind)}
                    </Text>
                  )
                },
              },
              {
                title: '主数据',
                key: 'in_master',
                width: 120,
                render: (_, row) => {
                  const kind = resolveMasterDataCollectionKind(row)
                  if (kind === 'shared_tag') {
                    return isSharedTagValueReady(row, masterNames) ? (
                      <Tag color="green">已规范</Tag>
                    ) : (
                      <Tag color="orange">待规范名</Tag>
                    )
                  }
                  return isRegistryItemInMaster(row, kind) ? (
                    <Tag color="green">已登记</Tag>
                  ) : (
                    <Tag color="orange">待补</Tag>
                  )
                },
              },
              {
                title: '操作',
                key: 'register',
                width: 100,
                render: (_: unknown, row: (typeof registryForCategory)[number]) => {
                  const kind = resolveMasterDataCollectionKind(row)
                  if (kind === 'shared_tag') {
                    if (isSharedTagValueReady(row, masterNames)) return '-'
                    return (
                      <Link to={`/ledger/dimensions?tab=pending&jobId=${jobId}`}>待处理队列</Link>
                    )
                  }
                  if (isRegistryItemInMaster(row, kind)) {
                    return '-'
                  }
                  return (
                    <Button type="link" size="small" onClick={() => handleRegisterFromRegistry(row, kind)}>
                      补登记
                    </Button>
                  )
                },
              },
            ]}
          />
        </Card>
      )}

      <Modal
        title={editingBankId ? '编辑银行账户' : '登记银行账户'}
        open={bankModalOpen}
        destroyOnClose
        confirmLoading={bankSaving}
        onOk={() => void handleSaveBank()}
        onCancel={() => {
          setBankModalOpen(false)
          setEditingBankId(null)
        }}
        okText="保存"
        footer={(_, { OkBtn, CancelBtn }) => (
          <>
            {editingBankId ? (
              <Button
                danger
                icon={<DeleteOutlined />}
                style={{ float: 'left' }}
                onClick={() => {
                  const bank = banks.find((b) => b.id === editingBankId)
                  if (bank) handleDeleteBank(bank)
                }}
              >
                删除
              </Button>
            ) : null}
            <CancelBtn />
            <OkBtn />
          </>
        )}
      >
        <Form form={bankForm} layout="vertical" initialValues={{ coa_account_code: '1002' }}>
          <Form.Item
            name="source_sub_code"
            label="来源段"
            extra="与序时簿科目下级段一致（如 02），保存后系统靠此字段自动对上本批数据"
          >
            <Input placeholder="02" />
          </Form.Item>
          <Form.Item name="bank_name" label="开户银行" rules={[{ required: true, message: '请填写开户银行' }]}>
            <Input placeholder="如 浦发银行太原分行" />
          </Form.Item>
          <Form.Item name="account_no" label="账号" rules={[{ required: true, message: '请填写银行账号' }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="account_name"
            label="户名（规范全称）"
            rules={[{ required: true, message: '请填写户名规范全称' }]}
            extra="填写企业在银行开户的法定全称，可与「开户银行」不同"
          >
            <Input placeholder="如 XX有限公司" />
          </Form.Item>
          <Form.Item name="coa_account_code" label="关联科目">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingCounterpartyId ? '编辑往来单位' : '新增往来单位'}
        open={cpModalOpen}
        destroyOnClose
        confirmLoading={cpSaving}
        onOk={() => void handleSaveCounterparty()}
        onCancel={() => {
          setCpModalOpen(false)
          setEditingCounterpartyId(null)
        }}
        okText="保存"
        footer={(_, { OkBtn, CancelBtn }) => (
          <>
            {editingCounterpartyId ? (
              <Button
                danger
                icon={<DeleteOutlined />}
                style={{ float: 'left' }}
                onClick={() => {
                  const cp = counterparties.find((c) => c.id === editingCounterpartyId)
                  if (cp) handleDeleteCounterparty(cp)
                }}
              >
                删除
              </Button>
            ) : null}
            <CancelBtn />
            <OkBtn />
          </>
        )}
      >
        <Form
          form={cpForm}
          layout="vertical"
          initialValues={{ role: valueSource.counterpartyRole || 'other', is_related_party: false }}
        >
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true }]}>
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="unified_credit_no" label="统一社会信用代码">
            <Input placeholder="企业客户/供应商建议填写，个人可留空" />
          </Form.Item>
          <Form.Item
            name="is_related_party"
            label="是否关联方"
            valuePropName="checked"
            extra="审计与合并报表口径需要时可标记"
          >
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`批量变更角色（已选 ${selectedCpIds.length} 条）`}
        open={batchRoleOpen}
        destroyOnClose
        confirmLoading={batchRoleSaving}
        onOk={() => void handleBatchUpdateRole()}
        onCancel={() => {
          setBatchRoleOpen(false)
          batchRoleForm.resetFields()
        }}
        okText="应用"
      >
        <Form form={batchRoleForm} layout="vertical" initialValues={{ role: defaultBatchRole }}>
          <Form.Item
            name="role"
            label="目标角色"
            rules={[{ required: true, message: '请选择角色' }]}
            extra="变更后，在「客户」「供应商」等分类页将按新角色过滤显示。"
          >
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
