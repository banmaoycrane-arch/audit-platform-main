import { useCallback, useEffect, useMemo, useState } from 'react'

import {

  Alert,

  Button,

  Card,

  Col,

  Row,

  Space,

  Table,

  Tabs,

  Typography,

} from 'antd'

import { ReloadOutlined, ApartmentOutlined, PartitionOutlined, DatabaseOutlined, SwapOutlined, UnorderedListOutlined, BookOutlined } from '@ant-design/icons'

import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'

import {

  api,

  type DimensionRegistryResponse,

  type TagCategoryNode,

} from '../api/client'

import { useAuthStore } from '../stores/authStore'

import { formatDimensionTagLabel } from '../components/staging/formatDimensionTag'

import { AccountTagRulesPanel } from '../components/dimensions/AccountTagRulesPanel'

import { TagCategoryManager } from '../components/dimensions/TagCategoryManager'

import { DimensionValuesPanel } from '../components/dimensions/DimensionValuesPanel'

import { TagMappingRulesPanel } from '../components/dimensions/TagMappingRulesPanel'

import { DimensionPendingQueuePanel } from '../components/dimensions/DimensionPendingQueuePanel'

import { flattenTagCategories } from '../components/dimensions/dimensionUtils'

import { AccountingStructureNav, type AccountingStructureTab } from '../components/accounting/AccountingStructureNav'

import { ChartOfAccountsPanel } from '../components/accounting/ChartOfAccountsPanel'

import { ImportJobContextBar } from '../components/dimensions/ImportJobContextBar'

import {
  dimensionsPath,
  persistImportJobContext,
  readImportJobContext,
} from '../utils/importJobContext'



const { Title, Paragraph, Text } = Typography



function flattenCategoryCodes(nodes: TagCategoryNode[]): string[] {

  return flattenTagCategories(nodes).map((c) => c.code)

}



export function LedgerDimensionsPage() {

  const { currentLedgerId } = useAuthStore()

  const location = useLocation()

  const navigate = useNavigate()

  const [searchParams, setSearchParams] = useSearchParams()

  const jobId = Number(searchParams.get('jobId') || 0)

  const savedImportContext = jobId > 0 ? null : readImportJobContext()

  const rawTab = searchParams.get('tab') || 'categories'

  const activeTab = rawTab === 'bank-evidence' ? 'master-values' : rawTab

  const categoryParam = searchParams.get('category') || undefined



  const [categories, setCategories] = useState<TagCategoryNode[]>([])

  const [registry, setRegistry] = useState<DimensionRegistryResponse | null>(null)

  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (jobId > 0) {
      persistImportJobContext(jobId, `${location.pathname}${location.search}`)
    }
  }, [jobId, location.pathname, location.search])

  const restoreSavedImportJob = () => {
    if (!savedImportContext) return
    const tab = searchParams.get('tab') || 'master-values'
    const category = searchParams.get('category')
    navigate(
      dimensionsPath(tab, savedImportContext.jobId, category ? { category } : undefined),
    )
  }

  const loadAll = useCallback(async () => {
    if (!currentLedgerId) return
    setLoading(true)
    try {
      const cats = await api.listTagCategories(currentLedgerId, { status: 'active' })
      setCategories(cats)
      if (jobId) {
        const reg = await api.getDimensionRegistry(jobId)
        setRegistry(reg)
      } else {
        setRegistry(null)
      }
    } catch (error) {
      console.error('加载维度数据失败', error)
    } finally {
      setLoading(false)
    }
  }, [currentLedgerId, jobId])

  const handleDimensionDataChanged = useCallback(() => {
    void loadAll()
  }, [loadAll])

  useEffect(() => {
    void loadAll()
  }, [loadAll])

  const categoryCodes = useMemo(() => flattenCategoryCodes(categories), [categories])

  const flatCategories = useMemo(() => flattenTagCategories(categories), [categories])



  const categoryUsageSummary = useMemo(() => {

    if (!registry) return []

    const grouped = new Map<string, typeof registry.items>()

    for (const item of registry.items) {

      const list = grouped.get(item.category_code) || []

      list.push(item)

      grouped.set(item.category_code, list)

    }

    return Array.from(grouped.entries()).map(([code, items]) => {

      const cat = flatCategories.find((c) => c.code === code)

      return {

        code,

        name: cat?.name || code,

        valueCount: items.length,

        lineCount: items.reduce((sum, i) => sum + i.line_count, 0),

        items,

      }

    })

  }, [registry, flatCategories])



  const handleTabChange = (key: string) => {

    navigateStructure(key as AccountingStructureTab)

  }



  const navigateStructure = (tab: AccountingStructureTab, category?: string) => {

    const next = new URLSearchParams(searchParams)

    if (tab === 'categories') {

      next.delete('tab')

      next.delete('category')

    } else {

      next.set('tab', tab)

      if (tab === 'master-values' && category) {

        next.set('category', category)

      } else if (tab !== 'master-values') {

        next.delete('category')

      }

    }

    setSearchParams(next)

  }



  const handleCategoryChange = (code: string) => {

    const next = new URLSearchParams(searchParams)

    next.set('tab', 'master-values')

    next.set('category', code)

    setSearchParams(next)

  }



  if (!currentLedgerId && activeTab !== 'coa') {

    return (

      <div style={{ padding: 24 }}>

        <Alert

          type="warning"

          showIcon

          title="请先在顶部切换账簿"

          description="解析映射、维度分类与维度值主数据需绑定账簿。科目表可在下方入口单独维护。"

          action={

            <Button type="primary" onClick={() => navigateStructure('coa')}>

              先维护科目表

            </Button>

          }

        />

      </div>

    )

  }



  return (

    <div style={{ padding: 24 }}>

      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>

        <Col>

          <Title level={4} style={{ margin: 0 }}>

            <ApartmentOutlined /> 核算结构（科目 + 维度）

          </Title>

          <Paragraph type="secondary" style={{ marginBottom: 0 }}>

            科目表与 Tag 维度配套设计：上方卡片快速跳转 · 下方 Tab 详细维护

          </Paragraph>

        </Col>

        <Col>

          <Button icon={<ReloadOutlined />} onClick={() => void loadAll()} loading={loading}>

            刷新

          </Button>

        </Col>

      </Row>



      {jobId > 0 && <ImportJobContextBar jobId={jobId} activeTab={activeTab} />}

      {!jobId && savedImportContext && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          title={`检测到未完成的导入任务 #${savedImportContext.jobId}`}
          description="当前 URL 未带 jobId（可能切换了顶部标签页）。staging 预览数据仍在服务端，无需重新上传文件。"
          action={
            <Button type="primary" size="small" onClick={restoreSavedImportJob}>
              恢复导入上下文
            </Button>
          }
        />
      )}

      <AccountingStructureNav

        activeTab={

          (['coa', 'categories', 'parse-mapping', 'master-values', 'external-mapping', 'pending'] as const).includes(

            activeTab as AccountingStructureTab,

          )

            ? (activeTab as AccountingStructureTab)

            : 'categories'

        }

        hasLedger={Boolean(currentLedgerId)}

        hasJob={jobId > 0}

        onNavigate={navigateStructure}

      />



      <Tabs

        activeKey={activeTab}

        onChange={handleTabChange}

        items={[

          {

            key: 'coa',

            label: (

              <span>

                <BookOutlined /> 科目表

              </span>

            ),

            children: (

              <ChartOfAccountsPanel embedded onNavigateTab={navigateStructure} />

            ),

          },

          {

            key: 'categories',

            label: '维度分类',

            children: <TagCategoryManager ledgerId={currentLedgerId} onChanged={handleDimensionDataChanged} />,

          },

          {

            key: 'parse-mapping',

            label: (

              <span>

                <PartitionOutlined /> 解析映射

              </span>

            ),

            children: <AccountTagRulesPanel ledgerId={currentLedgerId} categoryCodes={categoryCodes} />,

          },

          {

            key: 'master-values',

            label: (

              <span>

                <DatabaseOutlined /> 维度值主数据

              </span>

            ),

            children: (

              <DimensionValuesPanel

                ledgerId={currentLedgerId}

                categories={categories}

                jobId={jobId}

                registry={registry}

                selectedCategoryCode={categoryParam === 'account_detail' ? 'bank_account' : categoryParam || (rawTab === 'bank-evidence' ? 'bank_account' : undefined)}

                onCategoryChange={handleCategoryChange}

                onChanged={handleDimensionDataChanged}

              />

            ),

          },

          {

            key: 'external-mapping',

            label: (

              <span>

                <SwapOutlined /> 外部映射

              </span>

            ),

            children: <TagMappingRulesPanel ledgerId={currentLedgerId} categoryCodes={categoryCodes} />,

          },

          {

            key: 'pending',

            label: (

              <span>

                <UnorderedListOutlined /> 待处理队列

              </span>

            ),

            disabled: !jobId,

            children: jobId ? (

              <DimensionPendingQueuePanel jobId={jobId} onChanged={handleDimensionDataChanged} />

            ) : (

              <Alert type="info" showIcon message="请从 Step4 或导入任务链接进入（带 jobId）后查看待处理队列" />

            ),

          },

          {

            key: 'compare',

            label: '三层对照',

            disabled: !jobId,

            children: registry ? (

              <Space direction="vertical" style={{ width: '100%' }} size={16}>

                {registry.warnings.map((w) => (

                  <Alert

                    key={`${w.code}-${w.message}`}

                    type={w.severity === 'warning' ? 'warning' : 'info'}

                    showIcon

                    message={w.message}

                  />

                ))}



                {categoryUsageSummary.length > 0 && (

                  <Card size="small" title="按维度分类 · 本批使用汇总">

                    <Table

                      size="small"

                      pagination={false}

                      rowKey="code"

                      dataSource={categoryUsageSummary}

                      columns={[

                        { title: '分类', dataIndex: 'name' },

                        { title: '编码', dataIndex: 'code', width: 120 },

                        { title: '实例数', dataIndex: 'valueCount', width: 72 },

                        { title: '分录行', dataIndex: 'lineCount', width: 72 },

                        {

                          title: '操作',

                          key: 'action',

                          width: 120,

                          render: (_, row) => (

                            <Button type="link" size="small" onClick={() => handleCategoryChange(row.code)}>

                              维护主数据

                            </Button>

                          ),

                        },

                      ]}

                    />

                  </Card>

                )}



                <Row gutter={16}>

                  <Col span={8}>

                    <Card size="small" title="① 配置层 · 科目表下级">

                      <Text type="secondary" style={{ display: 'block', marginBottom: 8, fontSize: 12 }}>

                        结构性下级见

                        <Link to="/ledger/dimensions?tab=coa"> 科目表 </Link>

                        ；户名/客户等请用

                        <Button type="link" size="small" style={{ padding: 0 }} onClick={() => handleTabChange('master-values')}>

                          维度值主数据

                        </Button>

                      </Text>

                      <Table

                        size="small"

                        pagination={false}

                        rowKey={(r) => `${r.parent_code}-${r.account_code}`}

                        dataSource={registry.layers?.config_coa || []}

                        columns={[

                          { title: '一级', dataIndex: 'parent_code', width: 70 },

                          { title: '下级科目', dataIndex: 'account_code' },

                        ]}

                      />

                    </Card>

                  </Col>

                  <Col span={8}>

                    <Card size="small" title="② 证据层 · 主数据">

                      <Text type="secondary" style={{ display: 'block', marginBottom: 8, fontSize: 12 }}>

                        银行户见 bank_account；客户/供应商见对应分类主数据。

                      </Text>

                      <Table

                        size="small"

                        pagination={false}

                        rowKey={(r) => r.account_no}

                        dataSource={registry.layers?.config_bank_evidence || []}

                        columns={[

                          { title: '段', dataIndex: 'source_sub_code', width: 50, render: (v) => v || '-' },

                          { title: '银行', dataIndex: 'bank_name', ellipsis: true },

                        ]}

                      />

                    </Card>

                  </Col>

                  <Col span={8}>

                    <Card size="small" title="③ 使用层 · 本批序时簿">

                      <Table

                        size="small"

                        pagination={false}

                        rowKey={(r) => `${r.account_code}-${r.category_code}-${r.source_sub_code}-${r.tag_value}`}

                        dataSource={registry.layers?.import_used || registry.items}

                        columns={[

                          {

                            title: '分类',

                            dataIndex: 'category_code',

                            width: 100,

                            ellipsis: true,

                          },

                          {

                            title: '维度',

                            render: (_, row) =>

                              formatDimensionTagLabel({

                                source_sub_code: row.source_sub_code,

                                display_name: row.display_name,

                                tag_value: row.tag_value,

                              }),

                          },

                          { title: '行', dataIndex: 'line_count', width: 50 },

                        ]}

                      />

                    </Card>

                  </Col>

                </Row>



                <Card size="small" title="差异汇总">

                  <Space direction="vertical" style={{ width: '100%' }}>

                    {(registry.comparison?.in_import_not_in_evidence || []).length > 0 && (

                      <Alert

                        type="warning"

                        showIcon

                        message="序时簿已用但主数据未登记（银行）"

                        description={(registry.comparison?.in_import_not_in_evidence || [])

                          .map((item) =>

                            formatDimensionTagLabel({

                              source_sub_code: item.source_sub_code,

                              display_name: item.display_name,

                              tag_value: item.tag_value,

                            }),

                          )

                          .join('、')}

                        action={

                          <Button size="small" onClick={() => handleCategoryChange('bank_account')}>

                            去补登记

                          </Button>

                        }

                      />

                    )}

                    {(registry.comparison?.in_evidence_not_in_import || []).length > 0 && (

                      <Alert

                        type="warning"

                        showIcon

                        message="主数据有但本批序时簿未出现"

                        description={(registry.comparison?.in_evidence_not_in_import || [])

                          .map((item) => `${item.source_sub_code || '-'} ${item.bank_name}`)

                          .join('、')}

                      />

                    )}

                    {(registry.comparison?.coa_gaps || []).map((gap) => (

                      <Alert

                        key={gap.account_code}

                        type="info"

                        showIcon

                        message={`科目 ${gap.account_code}：科目表有 ${gap.defined_sub_codes.join('、')}，本批仅用 ${gap.used_sub_codes.join('、')}`}

                      />

                    ))}

                    {!registry.comparison?.in_import_not_in_evidence?.length &&

                      !registry.comparison?.in_evidence_not_in_import?.length &&

                      !registry.comparison?.coa_gaps?.length && (

                        <Text type="secondary">三层数据一致，未发现明显缺口（仍建议人工核对全称）。</Text>

                      )}

                  </Space>

                </Card>

              </Space>

            ) : (

              <Alert

                type="info"

                showIcon

                message="请从 Step4 复核页带上 jobId 进入，或在本页 URL 加 ?jobId= 参数以查看三层对照。"

              />

            ),

          },

        ]}

      />

    </div>

  )

}


