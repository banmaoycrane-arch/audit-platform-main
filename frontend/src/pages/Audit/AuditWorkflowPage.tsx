import { useEffect, useState } from 'react'
import {
  Button,
  Card,
  Form,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { ApartmentOutlined, PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import { api, type AuditProcedureRun, type Project } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'

const { Title, Paragraph } = Typography

const STATUS_COLOR: Record<string, string> = {
  planned: 'default',
  initiated: 'processing',
  awaiting_evidence: 'gold',
  in_review: 'blue',
  concluded: 'success',
  exception: 'error',
}

const ACTION_LABEL: Record<string, string> = {
  start: '启动',
  send: '发函/送审',
  receive: '收到证据',
  conclude: '结论',
  flag_exception: '标记异常',
}

export function AuditWorkflowPage() {
  const { currentLedgerId } = useAuthStore()
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState<number | null>(null)
  const [runs, setRuns] = useState<AuditProcedureRun[]>([])
  const [loading, setLoading] = useState(false)
  const [configForm] = Form.useForm()

  const loadProjects = () => {
    api.listProjects().then((rows) => {
      setProjects(rows)
      if (!projectId && rows.length > 0) setProjectId(rows[0].id)
    })
  }

  const loadRuns = () => {
    if (!currentLedgerId) return
    setLoading(true)
    api
      .listAuditProcedureRuns(currentLedgerId, projectId || undefined)
      .then(setRuns)
      .catch((error: Error) => message.error(error.message || '加载审计程序失败'))
      .finally(() => setLoading(false))
  }

  const loadConfig = () => {
    if (!projectId) return
    api.getWorkflowConfig(projectId).then((config) => {
      configForm.setFieldsValue({
        granularity: config.granularity,
        enabled_procedures: config.enabled_procedures,
        auto_link_workpaper: config.auto_link_workpaper,
      })
    })
  }

  useEffect(() => {
    loadProjects()
  }, [])

  useEffect(() => {
    loadRuns()
    loadConfig()
  }, [currentLedgerId, projectId])

  const handleSaveConfig = async () => {
    if (!projectId) return
    const values = await configForm.validateFields()
    try {
      await api.updateWorkflowConfig(projectId, values)
      message.success('项目工作流配置已保存')
    } catch (error: any) {
      message.error(error.message || '保存配置失败')
    }
  }

  const handleAdvance = async (run: AuditProcedureRun, action: string) => {
    if (!currentLedgerId) return
    try {
      await api.advanceAuditProcedureRun(currentLedgerId, run.id, { action })
      message.success('程序状态已更新')
      loadRuns()
    } catch (error: any) {
      message.error(error.message || '更新失败')
    }
  }

  const columns = [
    { title: '程序', dataIndex: 'procedure_label', key: 'procedure_label' },
    { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
    {
      title: '状态',
      dataIndex: 'status_label',
      key: 'status_label',
      render: (value: string, row: AuditProcedureRun) => (
        <Tag color={STATUS_COLOR[row.status]}>{value}</Tag>
      ),
    },
    {
      title: '来源',
      dataIndex: 'recommended_by',
      key: 'recommended_by',
      width: 100,
      render: (value: string) => (value === 'decomposition' ? '分解推荐' : value === 'system' ? '系统同步' : '手工'),
    },
    {
      title: '底稿索引',
      dataIndex: 'workpaper_index_id',
      key: 'workpaper_index_id',
      width: 100,
      render: (value: number | null) => (value ? `#${value}` : '-'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, row: AuditProcedureRun) => (
        <Space wrap>
          {row.status === 'planned' && (
            <Button size="small" icon={<PlayCircleOutlined />} onClick={() => handleAdvance(row, 'start')}>
              启动
            </Button>
          )}
          {row.procedure_key === 'counterparty_confirmation' && row.status === 'initiated' && (
            <Button size="small" onClick={() => handleAdvance(row, 'send')}>发函</Button>
          )}
          {row.status === 'in_review' && (
            <>
              <Button size="small" type="primary" onClick={() => handleAdvance(row, 'conclude')}>结论</Button>
              <Button size="small" danger onClick={() => handleAdvance(row, 'flag_exception')}>异常</Button>
            </>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Title level={4} style={{ margin: 0 }}>
              <ApartmentOutlined /> 审计程序工作流
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              项目级颗粒度配置 + 函证/调节/三单匹配程序状态机；底稿分解后自动推荐并挂接工作底稿索引。
            </Paragraph>
          </div>
          <Button icon={<ReloadOutlined />} onClick={loadRuns} loading={loading} disabled={!currentLedgerId}>
            刷新
          </Button>
        </div>

        <Card title="项目配置" size="small">
          <Space wrap style={{ marginBottom: 12 }}>
            <span>项目：</span>
            <Select
              style={{ width: 220 }}
              value={projectId || undefined}
              onChange={setProjectId}
              options={projects.map((item) => ({ value: item.id, label: item.name }))}
              placeholder="选择项目"
            />
          </Space>
          <Form form={configForm} layout="inline" onFinish={handleSaveConfig}>
            <Form.Item name="granularity" label="颗粒度">
              <Select
                style={{ width: 140 }}
                options={[
                  { value: 'coarse', label: '粗' },
                  { value: 'standard', label: '标准' },
                  { value: 'fine', label: '细' },
                ]}
              />
            </Form.Item>
            <Form.Item name="enabled_procedures" label="启用程序">
              <Select
                mode="multiple"
                style={{ minWidth: 320 }}
                options={[
                  { value: 'counterparty_confirmation', label: '往来函证' },
                  { value: 'bank_reconciliation', label: '银行调节' },
                  { value: 'purchase_three_way_match', label: '采购三单匹配' },
                ]}
              />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" disabled={!projectId}>保存配置</Button>
            </Form.Item>
          </Form>
        </Card>

        <Card title="程序运行清单">
          <Table
            rowKey="id"
            loading={loading}
            columns={columns}
            dataSource={runs}
            pagination={{ pageSize: 15 }}
            locale={{ emptyText: '暂无审计程序，上传底稿后将自动推荐或从函证/调节入口同步' }}
          />
        </Card>
      </Space>
    </div>
  )
}
