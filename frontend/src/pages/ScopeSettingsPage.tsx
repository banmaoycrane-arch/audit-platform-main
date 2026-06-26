import { useEffect, useMemo, useState } from 'react'
import {
  Button,
  Card,
  Form,
  Input,
  Select,
  Space,
  Switch,
  Tabs,
  Typography,
  message,
} from 'antd'
import { SettingOutlined, SaveOutlined } from '@ant-design/icons'
import { useSearchParams } from 'react-router-dom'
import {
  api,
  type Ledger,
  type LedgerSettingsData,
  type Project,
  type ProjectSettingsData,
  type Team,
  type TeamSettingsData,
  type EntityScopeSettingsData,
} from '../api/client'
import { useAuthStore } from '../stores/authStore'

const { Title, Paragraph, Text } = Typography

export function ScopeSettingsPage() {
  const [searchParams] = useSearchParams()
  const { currentLedgerId } = useAuthStore()
  const [teams, setTeams] = useState<Team[]>([])
  const [ledgers, setLedgers] = useState<Ledger[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [teamId, setTeamId] = useState<number | null>(null)
  const [ledgerId, setLedgerId] = useState<number | null>(null)
  const [projectId, setProjectId] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [ledgerForm] = Form.useForm<LedgerSettingsData>()
  const [teamForm] = Form.useForm<TeamSettingsData>()
  const [projectForm] = Form.useForm<ProjectSettingsData>()
  const [entityForm] = Form.useForm<EntityScopeSettingsData>()

  const initialTab = searchParams.get('tab') || 'ledger'

  useEffect(() => {
    Promise.all([api.listTeams(), api.listLedgers(), api.listProjects()]).then(
      ([teamRows, ledgerRows, projectRows]) => {
        setTeams(teamRows)
        setLedgers(ledgerRows)
        setProjects(projectRows)
        setTeamId(teamRows[0]?.id ?? null)
        const defaultLedger =
          ledgerRows.find((row) => row.id === currentLedgerId)?.id ?? ledgerRows[0]?.id ?? null
        setLedgerId(defaultLedger)
        setProjectId(projectRows[0]?.id ?? null)
      },
    )
  }, [currentLedgerId])

  const teamOptions = useMemo(
    () => teams.map((team) => ({ value: team.id, label: team.name })),
    [teams],
  )
  const ledgerOptions = useMemo(
    () => ledgers.map((ledger) => ({ value: ledger.id, label: ledger.name })),
    [ledgers],
  )
  const projectOptions = useMemo(
    () => projects.map((project) => ({ value: project.id, label: project.name })),
    [projects],
  )

  const loadLedgerSettings = async (id: number) => {
    setLoading(true)
    try {
      const [ledgerResp, entityResp] = await Promise.all([
        api.getLedgerSettings(id),
        api.getEntityScopeSettings(id),
      ])
      ledgerForm.setFieldsValue(ledgerResp.settings)
      entityForm.setFieldsValue(entityResp.settings)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载账套配置失败')
    } finally {
      setLoading(false)
    }
  }

  const loadTeamSettings = async (id: number) => {
    setLoading(true)
    try {
      const resp = await api.getTeamSettings(id)
      teamForm.setFieldsValue(resp.settings)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载团队配置失败')
    } finally {
      setLoading(false)
    }
  }

  const loadProjectSettings = async (id: number) => {
    setLoading(true)
    try {
      const resp = await api.getProjectSettings(id)
      projectForm.setFieldsValue(resp.settings)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载项目配置失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (ledgerId) loadLedgerSettings(ledgerId)
  }, [ledgerId])

  useEffect(() => {
    if (teamId) loadTeamSettings(teamId)
  }, [teamId])

  useEffect(() => {
    if (projectId) loadProjectSettings(projectId)
  }, [projectId])

  const saveLedgerSettings = async () => {
    if (!ledgerId) return
    const values = await ledgerForm.validateFields()
    setSaving(true)
    try {
      await api.updateLedgerSettings(ledgerId, values)
      message.success('账套配置已保存')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const saveEntitySettings = async () => {
    if (!ledgerId) return
    const values = await entityForm.validateFields()
    setSaving(true)
    try {
      await api.updateEntityScopeSettings(ledgerId, values)
      message.success('主体配置已保存')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const saveTeamSettings = async () => {
    if (!teamId) return
    const values = await teamForm.validateFields()
    setSaving(true)
    try {
      await api.updateTeamSettings(teamId, values)
      message.success('团队配置已保存')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const saveProjectSettings = async () => {
    if (!projectId) return
    const values = await projectForm.validateFields()
    setSaving(true)
    try {
      await api.updateProjectSettings(projectId, values)
      message.success('项目配置已保存')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const ledgerCurrencyMode = Form.useWatch('currency_mode', ledgerForm)
  const allowVirtualProject = Form.useWatch('allow_virtual_project', projectForm)

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Title level={3}>
            <SettingOutlined /> 管理配置参数
          </Title>
          <Paragraph type="secondary">
            按账套、团队、项目、主体分别维护常见管理策略。账套侧重会计政策与核算习惯；团队侧重成员兼任与授权；项目侧重合并与虚拟项目；主体侧重纳税与虚拟主体策略。
          </Paragraph>
        </div>

        <Tabs
          defaultActiveKey={initialTab}
          items={[
            {
              key: 'ledger',
              label: '账套',
              children: (
                <Card loading={loading}>
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    <Select
                      style={{ width: 320 }}
                      placeholder="选择账套"
                      value={ledgerId ?? undefined}
                      options={ledgerOptions}
                      onChange={setLedgerId}
                    />
                    <Form form={ledgerForm} layout="vertical">
                      <Form.Item name="currency_mode" label="币种模式">
                        <Select
                          options={[
                            { value: 'single', label: '单一币种' },
                            { value: 'multi', label: '多币种' },
                          ]}
                        />
                      </Form.Item>
                      {ledgerCurrencyMode === 'multi' && (
                        <Form.Item name="base_currency" label="本位币">
                          <Input placeholder="如 CNY、USD" />
                        </Form.Item>
                      )}
                      <Form.Item
                        name="balance_direction_rule"
                        label="余额方向规则"
                        tooltip="严格模式要求账簿余额方向与科目借贷方向一致；自然模式按科目最终余额方向展示"
                      >
                        <Select
                          options={[
                            { value: 'strict', label: '账簿余额与借贷方向强制一致' },
                            { value: 'natural', label: '按科目最终方向定义余额' },
                          ]}
                        />
                      </Form.Item>
                      <Form.Item name="account_code_pattern" label="科目代码层级">
                        <Select
                          options={[
                            { value: '4-2-2-2', label: '4-2-2-2（如 1002.01.01.01）' },
                            { value: '3-3-2-2', label: '3-3-2-2（如 100.200.01.01）' },
                          ]}
                        />
                      </Form.Item>
                      <Form.Item
                        name="allow_custom_subjects"
                        label="允许自定义会计科目"
                        valuePropName="checked"
                      >
                        <Switch />
                      </Form.Item>
                    </Form>
                    <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={saveLedgerSettings}>
                      保存账套配置
                    </Button>
                  </Space>
                </Card>
              ),
            },
            {
              key: 'team',
              label: '团队',
              children: (
                <Card loading={loading}>
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    <Select
                      style={{ width: 320 }}
                      placeholder="选择团队"
                      value={teamId ?? undefined}
                      options={teamOptions}
                      onChange={setTeamId}
                    />
                    <Form form={teamForm} layout="vertical">
                      <Form.Item
                        name="allow_multi_team_membership"
                        label="允许用户兼任多个团队"
                        valuePropName="checked"
                      >
                        <Switch />
                      </Form.Item>
                      <Form.Item
                        name="require_binding_approval"
                        label="加入团队需审批"
                        valuePropName="checked"
                      >
                        <Switch />
                      </Form.Item>
                      <Form.Item name="default_ledger_role" label="新授权默认账套角色">
                        <Select
                          options={[
                            { value: 'admin', label: '管理员' },
                            { value: 'accountant', label: '记账员' },
                            { value: 'viewer', label: '查看者' },
                          ]}
                        />
                      </Form.Item>
                      <Form.Item name="ledger_grant_policy" label="账套授权策略">
                        <Select
                          options={[
                            { value: 'admin_only', label: '仅账套管理员可授权' },
                            { value: 'manager_can_grant', label: '团队经理可授权' },
                          ]}
                        />
                      </Form.Item>
                    </Form>
                    <Text type="secondary">团队角色列表（admin / manager / member / viewer）将在后续版本与成员表联动。</Text>
                    <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={saveTeamSettings}>
                      保存团队配置
                    </Button>
                  </Space>
                </Card>
              ),
            },
            {
              key: 'project',
              label: '项目',
              children: (
                <Card loading={loading}>
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    <Select
                      style={{ width: 320 }}
                      placeholder="选择项目"
                      value={projectId ?? undefined}
                      options={projectOptions}
                      onChange={setProjectId}
                    />
                    <Form form={projectForm} layout="vertical">
                      <Form.Item name="allow_merge" label="允许合并项目" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                      <Form.Item
                        name="allow_virtual_project"
                        label="允许定义虚拟项目"
                        valuePropName="checked"
                      >
                        <Switch />
                      </Form.Item>
                      {allowVirtualProject && (
                        <Form.Item name="virtual_project_label" label="虚拟项目展示名称">
                          <Input />
                        </Form.Item>
                      )}
                      <Form.Item
                        name="require_manager_on_create"
                        label="创建项目必须指定负责人"
                        valuePropName="checked"
                      >
                        <Switch />
                      </Form.Item>
                    </Form>
                    <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={saveProjectSettings}>
                      保存项目配置
                    </Button>
                  </Space>
                </Card>
              ),
            },
            {
              key: 'entity',
              label: '主体',
              children: (
                <Card loading={loading}>
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    <Select
                      style={{ width: 320 }}
                      placeholder="选择账套（主体策略按账套定义）"
                      value={ledgerId ?? undefined}
                      options={ledgerOptions}
                      onChange={setLedgerId}
                    />
                    <Form form={entityForm} layout="vertical">
                      <Form.Item name="allow_virtual_entity" label="允许虚拟主体" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                      <Form.Item
                        name="require_tax_registration"
                        label="创建主体必须填写税务登记号"
                        valuePropName="checked"
                      >
                        <Switch />
                      </Form.Item>
                      <Form.Item name="default_entity_category" label="默认主体类别">
                        <Select
                          options={[
                            { value: 'operating', label: '经营实体' },
                            { value: 'holding', label: '控股主体' },
                            { value: 'branch', label: '分支机构' },
                          ]}
                        />
                      </Form.Item>
                      <Form.Item
                        name="allow_multi_entity_per_ledger"
                        label="账套下允许多个会计主体"
                        valuePropName="checked"
                      >
                        <Switch />
                      </Form.Item>
                    </Form>
                    <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={saveEntitySettings}>
                      保存主体配置
                    </Button>
                  </Space>
                </Card>
              ),
            },
          ]}
        />
      </Space>
    </div>
  )
}
