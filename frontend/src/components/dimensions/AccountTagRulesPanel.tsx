import { useCallback, useEffect, useMemo, useState } from 'react'
import dayjs from 'dayjs'
import {
  Alert,
  Button,
  Card,
  Col,
  Input,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  message,
  Modal,
} from 'antd'
import {
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  PlusOutlined,
  ReloadOutlined,
  SaveOutlined,
} from '@ant-design/icons'
import { api, type AccountTagConfig } from '../../api/client'

const { Text } = Typography

type AccountTagRulesPanelProps = {
  /** 当前账簿 ID；有值时读写账簿级覆盖，无值时读写平台全局 */
  ledgerId?: number
  /** 当前账簿已有的 TagCategory 编码，用于映射下拉与校验提示 */
  categoryCodes?: string[]
}

const AUXILIARY_LABEL: Record<string, string> = {
  department: '部门',
  project: '项目',
  region: '区域',
}

function flattenCategoryOptions(codes: string[]): Array<{ value: string; label: string }> {
  const unique = Array.from(new Set(codes.filter(Boolean)))
  return unique.map((code) => ({ value: code, label: code }))
}

export function AccountTagRulesPanel({ ledgerId, categoryCodes = [] }: AccountTagRulesPanelProps) {
  const [config, setConfig] = useState<AccountTagConfig | null>(null)
  const [hasLedgerOverride, setHasLedgerOverride] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [acknowledging, setAcknowledging] = useState(false)
  const [tagRulesReviewedAt, setTagRulesReviewedAt] = useState<string | null>(null)
  const [editingRow, setEditingRow] = useState<{ table: string; index: number } | null>(null)
  const [editValue, setEditValue] = useState('')
  const [newAuxKeyword, setNewAuxKeyword] = useState<Record<string, string>>({})

  const categoryOptions = useMemo(() => {
    const fromConfig = config
      ? [
          ...Object.values(config.account_code_tag_category),
          ...Object.values(config.account_name_tag_category),
          ...Object.keys(config.auxiliary_keywords),
        ]
      : []
    return flattenCategoryOptions([...categoryCodes, ...fromConfig])
  }, [categoryCodes, config])

  const loadConfig = useCallback(async () => {
    setLoading(true)
    try {
      let result
      if (ledgerId) {
        try {
          result = await api.getLedgerAccountTagRules(ledgerId)
        } catch (ledgerError) {
          try {
            result = await api.getAccountTagRules()
            message.warning('无法加载账簿级解析映射，已展示平台默认规则（重启后端后可启用账簿覆盖）')
          } catch {
            throw ledgerError
          }
        }
      } else {
        result = await api.getAccountTagRules()
      }
      if (result.success) {
        setConfig(result.config)
        setHasLedgerOverride(Boolean('has_ledger_override' in result && result.has_ledger_override))
      } else {
        message.error(result.message || '加载解析映射失败')
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载解析映射失败，请刷新重试')
    } finally {
      setLoading(false)
    }
  }, [ledgerId])

  useEffect(() => {
    void loadConfig()
  }, [loadConfig])

  const loadReadiness = useCallback(async () => {
    if (!ledgerId) {
      setTagRulesReviewedAt(null)
      return
    }
    try {
      const readiness = await api.getLedgerDimensionReadiness(ledgerId)
      setTagRulesReviewedAt(readiness.tag_rules_reviewed_at || null)
    } catch {
      setTagRulesReviewedAt(null)
    }
  }, [ledgerId])

  useEffect(() => {
    void loadReadiness()
  }, [loadReadiness])

  const handleAcknowledgeRules = async () => {
    if (!ledgerId) return
    setAcknowledging(true)
    try {
      const result = await api.acknowledgeLedgerDimensionReadiness(ledgerId)
      setTagRulesReviewedAt(result.tag_rules_reviewed_at || new Date().toISOString())
      message.success('已确认本账簿维度规则，可进行序时簿导入')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '确认失败')
    } finally {
      setAcknowledging(false)
    }
  }

  const handleSave = async () => {
    if (!config) return
    setSaving(true)
    try {
      const result = ledgerId
        ? await api.saveLedgerAccountTagRules(ledgerId, config)
        : await api.saveAccountTagRules(config)
      if (result.success) {
        message.success(result.message || '解析映射已保存')
        await loadConfig()
        await loadReadiness()
      } else {
        message.error(result.message || '保存失败')
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    Modal.confirm({
      title: ledgerId ? '确认清除账簿覆盖' : '确认重置',
      content: ledgerId
        ? '将清除本账簿的解析映射覆盖，恢复使用平台默认规则。确认继续？'
        : '将恢复为系统默认解析映射（YAML 模板），当前平台自定义规则将清除。确认继续？',
      onOk: async () => {
        try {
          const result = ledgerId
            ? await api.resetLedgerAccountTagRules(ledgerId)
            : await api.resetAccountTagRules()
          if (result.success) {
            message.success(result.message || '已重置')
            await loadConfig()
          }
        } catch (error) {
          message.error(error instanceof Error ? error.message : '重置失败')
        }
      },
    })
  }

  const handleAddRule = (table: string) => {
    if (!config) return
    const newConfig = { ...config }
    if (table === 'mandatory_accounts') {
      newConfig.mandatory_hierarchical_accounts = [...newConfig.mandatory_hierarchical_accounts, '']
    } else if (table === 'mandatory_keywords') {
      newConfig.mandatory_hierarchical_keywords = [...newConfig.mandatory_hierarchical_keywords, '']
    }
    setConfig(newConfig)
    setEditingRow({
      table,
      index:
        newConfig[table === 'mandatory_accounts' ? 'mandatory_hierarchical_accounts' : 'mandatory_hierarchical_keywords']
          .length - 1,
    })
  }

  const handleEditRule = (table: string, index: number, value: string) => {
    if (!config) return
    const newConfig = { ...config }
    if (table === 'mandatory_accounts') {
      newConfig.mandatory_hierarchical_accounts = newConfig.mandatory_hierarchical_accounts.map((item, i) =>
        i === index ? value : item,
      )
    } else if (table === 'mandatory_keywords') {
      newConfig.mandatory_hierarchical_keywords = newConfig.mandatory_hierarchical_keywords.map((item, i) =>
        i === index ? value : item,
      )
    } else if (table === 'code_mapping') {
      const entries = Object.entries(newConfig.account_code_tag_category)
      const [key] = entries[index]
      newConfig.account_code_tag_category = { ...newConfig.account_code_tag_category, [key]: value }
    } else if (table === 'name_mapping') {
      const entries = Object.entries(newConfig.account_name_tag_category)
      const [key] = entries[index]
      newConfig.account_name_tag_category = { ...newConfig.account_name_tag_category, [key]: value }
    }
    setConfig(newConfig)
  }

  const handleDeleteRule = (table: string, index: number) => {
    if (!config) return
    const newConfig = { ...config }
    if (table === 'mandatory_accounts') {
      newConfig.mandatory_hierarchical_accounts = newConfig.mandatory_hierarchical_accounts.filter((_, i) => i !== index)
    } else if (table === 'mandatory_keywords') {
      newConfig.mandatory_hierarchical_keywords = newConfig.mandatory_hierarchical_keywords.filter((_, i) => i !== index)
    } else if (table === 'code_mapping') {
      const entries = Object.entries(newConfig.account_code_tag_category)
      const [key] = entries[index]
      delete newConfig.account_code_tag_category[key]
    } else if (table === 'name_mapping') {
      const entries = Object.entries(newConfig.account_name_tag_category)
      const [key] = entries[index]
      delete newConfig.account_name_tag_category[key]
    }
    setConfig(newConfig)
    setEditingRow(null)
  }

  const handleAddCodeMapping = () => {
    if (!config) return
    setConfig({
      ...config,
      account_code_tag_category: {
        ...config.account_code_tag_category,
        新科目编码: 'customer',
      },
    })
  }

  const handleAddNameMapping = () => {
    if (!config) return
    setConfig({
      ...config,
      account_name_tag_category: {
        ...config.account_name_tag_category,
        新关键词: 'customer',
      },
    })
  }

  const handleAddAuxCategory = () => {
    if (!config) return
    const base = 'new_dimension'
    let code = base
    let n = 1
    while (config.auxiliary_keywords[code]) {
      code = `${base}_${n}`
      n += 1
    }
    setConfig({
      ...config,
      auxiliary_keywords: { ...config.auxiliary_keywords, [code]: [] },
    })
  }

  const handleAddAuxKeyword = (category: string) => {
    if (!config) return
    const keyword = (newAuxKeyword[category] || '').trim()
    if (!keyword) {
      message.warning('请输入关键词')
      return
    }
    const existing = config.auxiliary_keywords[category] || []
    if (existing.includes(keyword)) {
      message.warning('关键词已存在')
      return
    }
    setConfig({
      ...config,
      auxiliary_keywords: {
        ...config.auxiliary_keywords,
        [category]: [keyword, ...existing],
      },
    })
    setNewAuxKeyword((prev) => ({ ...prev, [category]: '' }))
  }

  const handleRemoveAuxKeyword = (category: string, keyword: string) => {
    if (!config) return
    setConfig({
      ...config,
      auxiliary_keywords: {
        ...config.auxiliary_keywords,
        [category]: (config.auxiliary_keywords[category] || []).filter((item) => item !== keyword),
      },
    })
  }

  const renderCategorySelect = (table: string, index: number, value: string) => {
    const isEditing = editingRow?.table === table && editingRow?.index === index
    if (isEditing) {
      return (
        <Select
          size="small"
          style={{ minWidth: 160 }}
          showSearch
          value={editValue || value}
          options={categoryOptions}
          onChange={(v) => {
            handleEditRule(table, index, v)
            setEditingRow(null)
          }}
          autoFocus
          open
        />
      )
    }
    const known = categoryCodes.includes(value)
    return (
      <Space size={4}>
        <Tag color={known ? 'blue' : 'orange'}>{value}</Tag>
        {!known && categoryCodes.length > 0 && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            未在维度分类中
          </Text>
        )}
        <Button
          size="small"
          icon={<EditOutlined />}
          onClick={() => {
            setEditValue(value)
            setEditingRow({ table, index })
          }}
        />
      </Space>
    )
  }

  if (loading && !config) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
        <Spin tip="加载解析映射..." />
      </div>
    )
  }

  if (!config) {
    return <Alert type="error" showIcon message="加载解析映射失败，请刷新重试" />
  }

  return (
    <div>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message={ledgerId ? '账簿级解析映射（覆盖平台默认）' : '平台默认解析映射'}
        description={
          <div>
            <div>① 强制保留层级：税法/准则二级科目、实收资本/盈余公积等权益明细不扁平化；固定资产/在建工程等下级名称段转 Tag 供向量分析。</div>
            <div>② 科目代码映射：如 1122 → customer，1002 → bank_account（勿与往来混淆）。</div>
            <div>③ 摘要关键词：科目段无法识别时，从摘要补充 department / project 等维度。</div>
            <div style={{ marginTop: 4 }}>
              {ledgerId
                ? '保存后写入本账簿覆盖配置，下一批导入优先使用；已解析 staging 需重新处理才更新。'
                : '保存后作为平台默认，各账簿无覆盖时生效。'}
            </div>
            {ledgerId && (
              <div style={{ marginTop: 4 }}>
                当前状态：{hasLedgerOverride ? '已启用账簿覆盖' : '使用平台默认（未单独覆盖）'}
                {' · '}
                {tagRulesReviewedAt ? (
                  <Text type="success">维度规则已审阅（{dayjs(tagRulesReviewedAt).format('YYYY-MM-DD HH:mm')}）</Text>
                ) : (
                  <Text type="warning">尚未确认审阅，序时簿导入将被拦截</Text>
                )}
              </div>
            )}
            {ledgerId && (
              <div style={{ marginTop: 4 }}>
                向量检索按本账簿隔离，不同公司的维度叫法不会串库映射。
              </div>
            )}
          </div>
        }
      />

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col flex="auto">
          <Space wrap>
            <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={() => void handleSave()}>
              保存解析映射
            </Button>
            <Button icon={<ReloadOutlined />} onClick={() => void loadConfig()}>
              刷新
            </Button>
            <Button danger icon={<DownloadOutlined />} onClick={handleReset}>
              {ledgerId ? '清除账簿覆盖' : '重置为默认'}
            </Button>
            {ledgerId && (
              <Button loading={acknowledging} onClick={() => void handleAcknowledgeRules()}>
                确认规则已审阅，允许导入
              </Button>
            )}
          </Space>
        </Col>
        <Col>
          <Alert message={`配置版本 ${config.version}`} type="info" showIcon />
        </Col>
      </Row>

      <Card title="强制保留层级的科目编码" size="small">
        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          应交增值税、应付职工薪酬等必须保留完整层级，不得扁平化为 Tag。
        </Text>
        <div style={{ marginBottom: 8, textAlign: 'right' }}>
          <Button size="small" icon={<PlusOutlined />} onClick={() => handleAddRule('mandatory_accounts')}>
            添加科目编码
          </Button>
        </div>
        <Table
          size="small"
          dataSource={config.mandatory_hierarchical_accounts.map((code, index) => ({ key: index, code }))}
          pagination={false}
          columns={[
            { title: '#', width: 48, render: (_, __, index) => index + 1 },
            {
              title: '科目编码',
              dataIndex: 'code',
              render: (code: string, _, index: number) => (
                <Space>
                  {editingRow?.table === 'mandatory_accounts' && editingRow?.index === index ? (
                    <Input
                      size="small"
                      value={editValue || code}
                      onChange={(e) => setEditValue(e.target.value)}
                      onBlur={() => {
                        handleEditRule('mandatory_accounts', index, editValue || code)
                        setEditingRow(null)
                      }}
                      onPressEnter={() => {
                        handleEditRule('mandatory_accounts', index, editValue || code)
                        setEditingRow(null)
                      }}
                      autoFocus
                    />
                  ) : (
                    <>
                      <Tag color="red">{code || '（空）'}</Tag>
                      <Button
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => {
                          setEditValue(code)
                          setEditingRow({ table: 'mandatory_accounts', index })
                        }}
                      />
                      <Button
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => handleDeleteRule('mandatory_accounts', index)}
                      />
                    </>
                  )}
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Card title="强制保留层级的科目名称关键词" size="small" style={{ marginTop: 16 }}>
        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          编码未命中时，名称包含这些词则保留层级（如「应交增值税」）。
        </Text>
        <div style={{ marginBottom: 8, textAlign: 'right' }}>
          <Button size="small" icon={<PlusOutlined />} onClick={() => handleAddRule('mandatory_keywords')}>
            添加关键词
          </Button>
        </div>
        <Table
          size="small"
          dataSource={config.mandatory_hierarchical_keywords.map((keyword, index) => ({ key: index, keyword }))}
          pagination={false}
          columns={[
            { title: '#', width: 48, render: (_, __, index) => index + 1 },
            {
              title: '关键词',
              dataIndex: 'keyword',
              render: (keyword: string, _, index: number) => (
                <Space>
                  {editingRow?.table === 'mandatory_keywords' && editingRow?.index === index ? (
                    <Input
                      size="small"
                      value={editValue || keyword}
                      onChange={(e) => setEditValue(e.target.value)}
                      onBlur={() => {
                        handleEditRule('mandatory_keywords', index, editValue || keyword)
                        setEditingRow(null)
                      }}
                      onPressEnter={() => {
                        handleEditRule('mandatory_keywords', index, editValue || keyword)
                        setEditingRow(null)
                      }}
                      autoFocus
                    />
                  ) : (
                    <>
                      <Tag color="orange">{keyword || '（空）'}</Tag>
                      <Button
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => {
                          setEditValue(keyword)
                          setEditingRow({ table: 'mandatory_keywords', index })
                        }}
                      />
                      <Button
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => handleDeleteRule('mandatory_keywords', index)}
                      />
                    </>
                  )}
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Card title="一级科目代码 → Tag 维度分类" size="small" style={{ marginTop: 16 }}>
        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          科目下级段转为 Tag 时使用的 category_code。例：1122 应收账款 → customer。
        </Text>
        <div style={{ marginBottom: 8, textAlign: 'right' }}>
          <Button size="small" icon={<PlusOutlined />} onClick={handleAddCodeMapping}>
            添加映射
          </Button>
        </div>
        <Table
          size="small"
          dataSource={Object.entries(config.account_code_tag_category).map(([code, category], index) => ({
            key: index,
            code,
            category,
          }))}
          pagination={false}
          columns={[
            { title: '#', width: 48, render: (_, __, index) => index + 1 },
            { title: '科目代码', dataIndex: 'code', render: (code: string) => <Tag color="blue">{code}</Tag> },
            {
              title: 'Tag 分类',
              dataIndex: 'category',
              render: (category: string, _, index: number) => renderCategorySelect('code_mapping', index, category),
            },
            {
              title: '操作',
              width: 72,
              render: (_, __, index: number) => (
                <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteRule('code_mapping', index)} />
              ),
            },
          ]}
        />
      </Card>

      <Card title="科目名称关键词 → Tag 维度分类" size="small" style={{ marginTop: 16 }}>
        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          科目代码未知时，按名称关键词推断维度。例：名称含「应收」→ customer。
        </Text>
        <div style={{ marginBottom: 8, textAlign: 'right' }}>
          <Button size="small" icon={<PlusOutlined />} onClick={handleAddNameMapping}>
            添加映射
          </Button>
        </div>
        <Table
          size="small"
          dataSource={Object.entries(config.account_name_tag_category).map(([keyword, category], index) => ({
            key: index,
            keyword,
            category,
          }))}
          pagination={false}
          columns={[
            { title: '#', width: 48, render: (_, __, index) => index + 1 },
            { title: '关键词', dataIndex: 'keyword', render: (v: string) => <Tag color="purple">{v}</Tag> },
            {
              title: 'Tag 分类',
              dataIndex: 'category',
              render: (category: string, _, index: number) => renderCategorySelect('name_mapping', index, category),
            },
            {
              title: '操作',
              width: 72,
              render: (_, __, index: number) => (
                <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteRule('name_mapping', index)} />
              ),
            },
          ]}
        />
      </Card>

      <Card
        title="摘要辅助核算关键词"
        size="small"
        style={{ marginTop: 16 }}
        extra={
          <Button size="small" icon={<PlusOutlined />} onClick={handleAddAuxCategory}>
            新增维度类别
          </Button>
        }
      >
        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          科目段未识别出维度时，从摘要匹配这些词。请先在「维度分类」Tab 创建对应 TagCategory。
        </Text>
        {Object.entries(config.auxiliary_keywords).map(([category, keywords]) => (
          <div key={category} style={{ marginBottom: 16 }}>
            <Text strong>{AUXILIARY_LABEL[category] || category}</Text>
            <Tag style={{ marginLeft: 8 }}>{category}</Tag>
            <div style={{ marginTop: 8 }}>
              <Space wrap>
                {keywords.map((keyword) => (
                  <Tag
                    key={keyword}
                    closable
                    onClose={() => handleRemoveAuxKeyword(category, keyword)}
                    color={category === 'department' ? 'orange' : category === 'project' ? 'pink' : 'cyan'}
                  >
                    {keyword}
                  </Tag>
                ))}
              </Space>
            </div>
            <Space.Compact style={{ marginTop: 8, maxWidth: 360 }}>
              <Input
                size="small"
                placeholder={`为 ${category} 添加关键词`}
                value={newAuxKeyword[category] || ''}
                onChange={(e) => setNewAuxKeyword((prev) => ({ ...prev, [category]: e.target.value }))}
                onPressEnter={() => handleAddAuxKeyword(category)}
              />
              <Button size="small" type="primary" onClick={() => handleAddAuxKeyword(category)}>
                添加
              </Button>
            </Space.Compact>
          </div>
        ))}
      </Card>
    </div>
  )
}
