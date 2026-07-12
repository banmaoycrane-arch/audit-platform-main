import { useState, useEffect, useRef } from 'react'
import { Card, Row, Col, Form, Input, Select, Switch, InputNumber, Button, Space, Typography, Divider, Alert, Spin, message, Modal, Tabs } from 'antd'
import { ReloadOutlined, SaveOutlined, ExperimentOutlined, InfoCircleOutlined, ThunderboltOutlined, DatabaseOutlined, SettingOutlined, BookOutlined, UploadOutlined, DownloadOutlined, EditOutlined, CheckOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

const { Title, Text } = Typography
const { Option } = Select

export function ParserEngineConfigPage() {
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [config, setConfig] = useState<{ 
    ai_provider?: string; 
    ai_model?: string;
    ai_reasoning_model?: string;
    ai_base_url?: string;
    llm_enable_parallel_parsing?: boolean;
    llm_multi_engine_enabled?: boolean;
    [key: string]: unknown 
  } | null>(null)
  const [options, setOptions] = useState<{
    providers: Array<{ value: string; label: string; description: string; default_base_url: string; default_model: string; requires_api_key: boolean }>
    models: Array<{ value: string; label: string; description: string }>
    comparison_modes: Array<{ value: string; label: string }>
    comparison_strategies: Array<{ value: string; label: string }>
    selection_modes: Array<{ value: string; label: string }>
  } | null>(null)
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState(false)

  const llmEnableParallelParsing = Form.useWatch('llm_enable_parallel_parsing', form)
  const llmMultiEngineEnabled = Form.useWatch('llm_multi_engine_enabled', form)
  const aiLocalModelEnabled = Form.useWatch('ai_local_model_enabled', form)
  const aiFallbackToRules = Form.useWatch('ai_fallback_to_rules', form)
  const llmSaveAllResults = Form.useWatch('llm_save_all_results', form)
  const [testResult, setTestResult] = useState<{ 
    success: boolean; 
    message: string; 
    response_content?: string; 
    response_time_ms?: number;
    usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
  } | null>(null)
  const [ollamaLoading, setOllamaLoading] = useState(false)
  const [ollamaModels, setOllamaModels] = useState<Array<{ value: string; label: string; description: string }>>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [kbFileName, setKbFileName] = useState<string>('')
  const [saveAsModalVisible, setSaveAsModalVisible] = useState(false)
  const [saveAsFileName, setSaveAsFileName] = useState('')

  useEffect(() => {
    fetchConfig()
    fetchOptions()
  }, [])

  const fetchConfig = async () => {
    try {
      const cfg = await api.getParserEngineConfig()
      const merged = { ...cfg, ai_reasoning_model: cfg.ai_reasoning_model ?? '' }
      setConfig(merged)
      form.setFieldsValue(merged)
    } catch (error) {
      console.error('获取配置失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchOptions = async () => {
    try {
      const opts = await api.getProviderOptions()
      setOptions(opts)
    } catch (error) {
      console.error('获取选项失败:', error)
    }
  }

  const handleProviderChange = (value: string) => {
    const provider = options?.providers.find(p => p.value === value)
    if (provider) {
      form.setFieldsValue({
        ai_base_url: provider.default_base_url,
        ai_model: provider.default_model,
      })
      setOllamaModels([])
    }
  }

  const handleFetchOllamaModels = async () => {
    const values = form.getFieldsValue()
    if (!values.ai_base_url) {
      message.warning('请先填写 API 基础 URL')
      return
    }
    
    setOllamaLoading(true)
    try {
      const result = await api.getOllamaModels(values.ai_base_url)
      if (result.success && result.models.length > 0) {
        setOllamaModels(result.models)
        message.success(`发现 ${result.count} 个模型`)
      } else {
        message.warning(result.message || '未找到模型')
      }
    } catch (error) {
      message.error('获取模型列表失败，请检查 URL 是否正确')
    } finally {
      setOllamaLoading(false)
    }
  }

  const handleTestConnection = async () => {
    const values = form.getFieldsValue()
    setTesting(true)
    setTestResult(null)
    
    try {
      const apiKey = String(values.ai_api_key || '')
      const result = await api.testAIConnection({
        ai_base_url: values.ai_base_url,
        ai_model: values.ai_model,
        ai_api_key: apiKey.startsWith('*') ? undefined : (values.ai_api_key || undefined),
      })
      setTestResult(result)
      if (result.success) {
        message.success('连接测试成功！')
      } else {
        message.error('连接测试失败')
      }
    } catch (error) {
      setTestResult({ success: false, message: `请求失败: ${error instanceof Error ? error.message : String(error)}` })
    } finally {
      setTesting(false)
    }
  }

  const normalizeConfigValues = (values: Record<string, unknown>) => {
    const primary = String(values.ai_model || '').trim()
    let comparisonEngines = typeof values.llm_comparison_engines === 'string'
      ? values.llm_comparison_engines.split(',').map(item => item.trim()).filter(Boolean).join(',')
      : values.llm_comparison_engines
    if (primary) {
      const list = String(comparisonEngines || '')
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean)
      const legacyDefaults = ['qwen2.5-14b', 'qwen2.5-7b', 'deepseek-v2']
      const isLegacyDefault =
        list.length === legacyDefaults.length && legacyDefaults.every((item) => list.includes(item))
      if (!list.length || isLegacyDefault) {
        comparisonEngines = primary
      } else if (!list.includes(primary)) {
        comparisonEngines = [primary, ...list].join(',')
      }
    }
    return {
      ...values,
      ai_reasoning_model: String(values.ai_reasoning_model || '').trim(),
      llm_preferred_model: primary || values.llm_preferred_model,
      ai_local_model_enabled: Boolean(values.ai_local_model_enabled),
      ai_fallback_to_rules: Boolean(values.ai_fallback_to_rules),
      llm_enable_parallel_parsing: Boolean(values.llm_enable_parallel_parsing),
      llm_multi_engine_enabled: Boolean(values.llm_multi_engine_enabled),
      llm_save_all_results: Boolean(values.llm_save_all_results),
      llm_comparison_engines: comparisonEngines,
      llm_engine_weights: typeof values.llm_engine_weights === 'string' && values.llm_engine_weights.trim()
        ? JSON.stringify(JSON.parse(values.llm_engine_weights), null, 2)
        : values.llm_engine_weights || '{}',
    }
  }

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      const parseModel = String(values.ai_model || '').trim()
      const reasoningModel = String(values.ai_reasoning_model || '').trim()
      if (parseModel.toLowerCase().includes('vl') && !reasoningModel) {
        message.error('解析模型为视觉多模态时，必须单独配置「推理模型」（如 deepseek-r1:8b）')
        return
      }
      const payload = normalizeConfigValues(values)
      const result = await api.saveParserEngineConfig(payload)
      if (result.success) {
        const savedReasoning = String(result.config?.ai_reasoning_model || '').trim()
        if (reasoningModel && savedReasoning !== reasoningModel) {
          message.warning('推理模型可能未写入数据库，请刷新页面确认后重试')
        } else {
          message.success(result.message || '配置保存成功！')
        }
        if (result.config) {
          setConfig(result.config)
          form.setFieldsValue(result.config)
        } else {
          fetchConfig()
        }
      } else {
        message.error(result.message || '保存失败')
      }
    } catch (error) {
      if (error && typeof error === 'object' && 'errorFields' in error) {
        message.warning('请检查表单填写是否正确')
      } else {
        message.error(`保存失败: ${error instanceof Error ? error.message : String(error)}`)
      }
    }
  }

  const kbContent = Form.useWatch('llm_knowledge_base', form) as string | undefined

  const saveKnowledgeBaseToFile = (content: string, fileName: string) => {
    const blob = new Blob([content || ''], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleKbSave = () => {
    if (kbContent === undefined) {
      message.warning('请先填写知识库内容')
      return
    }
    const fileName = kbFileName || 'llm-knowledge-base.md'
    saveKnowledgeBaseToFile(kbContent, fileName)
    message.success(`已保存到 ${fileName}`)
  }

  const handleKbSaveAs = () => {
    setSaveAsFileName(kbFileName || 'llm-knowledge-base.md')
    setSaveAsModalVisible(true)
  }

  const handleConfirmSaveAs = () => {
    const value = saveAsFileName.trim()
    if (!value) {
      message.warning('请输入文件名')
      return
    }
    const fileName = value.endsWith('.md') ? value : `${value}.md`
    setKbFileName(fileName)
    saveKnowledgeBaseToFile(kbContent || '', fileName)
    setSaveAsModalVisible(false)
    message.success(`已另存为 ${fileName}`)
  }

  const handleKbLoad = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const tryDecode = (buffer: ArrayBuffer, encoding: string) => {
      try {
        const decoder = new TextDecoder(encoding, { fatal: true })
        return decoder.decode(buffer)
      } catch {
        return null
      }
    }

    const reader = new FileReader()
    reader.onload = (e) => {
      const buffer = e.target?.result as ArrayBuffer
      if (!buffer) {
        message.error('读取文件失败')
        return
      }
      let text = tryDecode(buffer, 'utf-8')
      if (text === null) {
        text = tryDecode(buffer, 'gb18030')
      }
      if (text === null) {
        text = tryDecode(buffer, 'gbk')
      }
      if (text === null) {
        text = new TextDecoder('utf-8', { fatal: false }).decode(buffer)
      }
      form.setFieldsValue({ llm_knowledge_base: text })
      setKbFileName(file.name)
      message.success(`已载入 ${file.name}`)
    }
    reader.onerror = () => {
      message.error('读取文件失败')
    }
    reader.readAsArrayBuffer(file)
    event.target.value = ''
  }

  const renderModelSelect = (name: string, label: string, placeholder: string, required = false) => (
    <Form.Item
      name={name}
      label={label}
      rules={required ? [{ required: true, message: '请选择模型名称' }] : []}
    >
      <Select placeholder={placeholder} showSearch allowClear={!required}>
        {ollamaModels.length > 0 && (
          <>
            <Option disabled style={{ fontWeight: 'bold' }}>—— 自动发现的模型 ——</Option>
            {ollamaModels.map(model => (
              <Option key={`${name}-${model.value}`} value={model.value}>
                {model.label}
                <div style={{ color: '#52c41a', fontSize: 12, marginTop: 4 }}>{model.description}</div>
              </Option>
            ))}
            <Option disabled style={{ fontWeight: 'bold' }}>—— 常用预设模型 ——</Option>
          </>
        )}
        {options?.models.map(model => (
          <Option key={`${name}-preset-${model.value}`} value={model.value}>
            {model.label}
            <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>{model.description}</div>
          </Option>
        ))}
      </Select>
    </Form.Item>
  )

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '100px' }}>
        <Spin size="large" tip="正在加载配置..." />
      </div>
    )
  }

  return (
    <div>
      <Title level={2}>解析引擎配置</Title>
      <Text type="secondary">配置本地大模型连接、解析引擎性能参数、并行策略和科目解析规则</Text>

      <Alert
        message={<><InfoCircleOutlined /> 提示：配置保存到数据库后，刷新页面即可生效，无需重启服务</>}
        type="info"
        style={{ marginBottom: 24 }}
      />

      <Tabs defaultActiveKey="ai">
        <Tabs.TabPane tab="AI 模型配置" key="ai">
          <Form form={form} layout="vertical" onFinish={handleSave}>
            <Row gutter={16}>
              <Col span={16}>
                <Card title="AI 模型配置（双模型分工）" extra={<Space><Button icon={<ReloadOutlined />} onClick={fetchConfig}>刷新</Button></Space>}>
                  <Alert
                    type="warning"
                    showIcon
                    style={{ marginBottom: 16 }}
                    message="解析模型与推理模型请分开配置"
                    description="非结构化文件解析（含图片/票据）使用视觉或多模态解析模型；Step4 合规审查使用纯文本推理模型。两者共用同一 API 地址，但不应强行使用同一个模型，否则容易在 Ollama 上互相挤占显存或导致审查效果变差。"
                  />
                  <Divider titlePlacement="start"><SettingOutlined /> AI供应商</Divider>
                  
                  <Form.Item name="ai_provider" label="供应商类型" rules={[{ required: true, message: '请选择供应商类型' }]}>
                    <Select
                      placeholder="请选择供应商类型"
                      onChange={handleProviderChange}
                      showSearch
                      optionFilterProp="children"
                    >
                      {options?.providers.map(provider => (
                        <Option key={provider.value} value={provider.value}>
                          {provider.label}
                          <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>{provider.description}</div>
                        </Option>
                      ))}
                    </Select>
                  </Form.Item>

                  <Divider titlePlacement="start"><ThunderboltOutlined /> 路由策略（本地优先 / 云端回退）</Divider>

                  <Form.Item
                    name="ai_routing_mode"
                    label="LLM 路由模式"
                    tooltip="auto：先连局域网/反向代理本地模型，失败再用云端 API"
                  >
                    <Select>
                      <Option value="manual">手动（仅用上方 API 地址）</Option>
                      <Option value="auto">Auto — 本地优先，云端回退</Option>
                      <Option value="local">仅本地/边缘节点</Option>
                      <Option value="cloud">仅云端 API</Option>
                    </Select>
                  </Form.Item>

                  <Alert
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                    message="云端部署时，本地模型需通过 frp/Nginx 反代暴露公网可达地址"
                    description="例：http://你的域名或IP:11434/v1 指向办公室 Ollama。生产服务器无法直接访问 192.168.x.x 内网。"
                  />

                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name="ai_local_base_url" label="本地/边缘 API 地址">
                        <Input placeholder="http://192.168.x.x:11434/v1 或反代公网地址" />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item name="ai_local_model" label="本地解析模型">
                        <Input placeholder="qwen2.5vl:latest" />
                      </Form.Item>
                    </Col>
                  </Row>

                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name="ai_cloud_base_url" label="云端 API 地址（回退）">
                        <Input placeholder="https://api.moonshot.cn/v1" />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item name="ai_cloud_model" label="云端模型 ID">
                        <Input placeholder="moonshot-v1-8k" />
                      </Form.Item>
                    </Col>
                  </Row>

                  <Form.Item name="ai_cloud_api_key" label="云端 API 密钥（可与上方密钥相同）">
                    <Input.Password placeholder="sk-..." allowClear />
                  </Form.Item>

                  <Divider titlePlacement="start"><DatabaseOutlined /> 连接信息</Divider>

                  <Alert
                    message="快速配置提示"
                    description="先选供应商类型，URL 和模型会自动填充。Ollama 服务可以点击「获取模型列表」自动发现可用模型。"
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />

                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name="ai_base_url" label="API基础URL" rules={[{ required: true, message: '请输入API基础URL' }]}>
                        <Input placeholder="如: http://192.168.1.100:11434/v1" />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      {renderModelSelect(
                        'ai_model',
                        '解析模型（非结构化文件 / 视觉）',
                        '如 qwen2.5vl:latest',
                        true,
                      )}
                    </Col>
                  </Row>

                  <Row gutter={16}>
                    <Col span={12}>
                      {renderModelSelect(
                        'ai_reasoning_model',
                        '推理模型（合规审查 / 语义分析）',
                        '如 deepseek-r1:8b；留空则回退到解析模型',
                        false,
                      )}
                    </Col>
                    <Col span={12}>
                      <Alert
                        type="info"
                        showIcon
                        message="推荐组合"
                        description="解析：qwen2.5vl:latest · 推理：deepseek-r1:8b。推理模型支持思索过程输出时，合规审查抽屉会显示思索链。"
                      />
                    </Col>
                  </Row>

                  <Row gutter={16}>
                    <Col span={24}>
                      <Form.Item name="ai_api_key" label="API密钥">
                        <Input.Password 
                          placeholder="本地 Ollama 不需要密钥，云端 API 需要填写" 
                          allowClear
                        />
                      </Form.Item>
                    </Col>
                  </Row>

                  <Space>
                    <Button
                      icon={<ReloadOutlined />}
                      onClick={handleFetchOllamaModels}
                      loading={ollamaLoading}
                    >
                      获取模型列表（Ollama）
                    </Button>
                    <Button
                      type="primary"
                      icon={<ExperimentOutlined />}
                      onClick={handleTestConnection}
                      loading={testing}
                    >
                      {testing ? '测试中...' : '测试连接'}
                    </Button>
                  </Space>

                  {testResult && (
                    <Alert
                      message={testResult.message}
                      type={testResult.success ? 'success' : 'error'}
                      showIcon
                      style={{ marginTop: 16 }}
                      description={
                        testResult.success && testResult.response_content ? (
                          <div style={{ marginTop: 8 }}>
                            <div style={{ marginBottom: 4 }}>
                              <Text type="secondary">模型返回：</Text>
                              <Text strong style={{ marginLeft: 8 }}>{testResult.response_content}</Text>
                            </div>
                            <div style={{ marginBottom: 4 }}>
                              <Text type="secondary">响应时间：</Text>
                              <Text strong style={{ marginLeft: 8 }}>{(testResult.response_time_ms || 0).toFixed(0)} ms</Text>
                            </div>
                            {testResult.usage && (
                              <div>
                                <Text type="secondary">Token使用：</Text>
                                <Text strong style={{ marginLeft: 8 }}>
                                  输入 {testResult.usage.prompt_tokens} / 输出 {testResult.usage.completion_tokens} / 总计 {testResult.usage.total_tokens}
                                </Text>
                              </div>
                            )}
                          </div>
                        ) : undefined
                      }
                    />
                  )}
                </Card>

                <Card title="性能配置" style={{ marginTop: 24 }}>
                  <Divider titlePlacement="start"><ThunderboltOutlined /> 模型性能</Divider>

                  <Row gutter={16}>
                    <Col span={8}>
                      <Form.Item name="llm_max_concurrent_models" label="最大并发模型数">
                        <InputNumber min={1} max={8} placeholder="1" />
                        <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
                          建议：16GB内存设为1，32GB内存设为2，64GB内存设为3-4
                        </Text>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="llm_memory_limit_mb" label="内存限制(MB)">
                        <InputNumber min={1024} max={65536} placeholder="8192" />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="llm_timeout_seconds" label="超时时间(秒)">
                        <InputNumber min={10} max={300} placeholder="60" />
                      </Form.Item>
                    </Col>
                  </Row>

                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name="llm_preferred_model" label="优先模型">
                        <Select placeholder="请选择优先模型" showSearch>
                          {options?.models.map(model => (
                            <Option key={model.value} value={model.value}>{model.label}</Option>
                          ))}
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item name="llm_fallback_model" label="降级模型">
                        <Select placeholder="请选择降级模型" showSearch>
                          {options?.models.map(model => (
                            <Option key={model.value} value={model.value}>{model.label}</Option>
                          ))}
                        </Select>
                      </Form.Item>
                    </Col>
                  </Row>
                </Card>

                <Card title="并行策略配置" style={{ marginTop: 24 }}>
                  <Form.Item name="llm_enable_parallel_parsing" label="启用双引擎并行解析">
                    <Switch checked={Boolean(llmEnableParallelParsing)} onChange={(checked) => form.setFieldsValue({ llm_enable_parallel_parsing: checked })} />
                    <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
                      启用后规则引擎和LLM引擎同时解析，按置信度选择最优结果
                    </Text>
                  </Form.Item>

                  <Form.Item name="llm_parallel_timeout_seconds" label="并行解析总超时(秒)">
                    <InputNumber min={30} max={300} placeholder="120" />
                  </Form.Item>
                </Card>

                <Card title="结果选择策略" style={{ marginTop: 24 }}>
                  <Form.Item name="llm_result_selection_mode" label="选择模式">
                    <Select placeholder="请选择选择模式">
                      {options?.selection_modes.map(mode => (
                        <Option key={mode.value} value={mode.value}>{mode.label}</Option>
                      ))}
                    </Select>
                  </Form.Item>

                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name="llm_confidence_threshold_auto" label="自动选择阈值">
                        <InputNumber min={0} max={1} step={0.05} placeholder="0.8" />
                        <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
                          置信度高于此值自动采纳
                        </Text>
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item name="llm_confidence_threshold_user" label="用户确认阈值">
                        <InputNumber min={0} max={1} step={0.05} placeholder="0.6" />
                        <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
                          置信度低于此值提示用户确认
                        </Text>
                      </Form.Item>
                    </Col>
                  </Row>
                </Card>

                <Card title="多LLM引擎对比配置" style={{ marginTop: 24 }}>
                  <Form.Item name="llm_multi_engine_enabled" label="启用多LLM引擎对比">
                    <Switch checked={Boolean(llmMultiEngineEnabled)} onChange={(checked) => form.setFieldsValue({ llm_multi_engine_enabled: checked })} />
                    <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
                      启用后同时调用多个模型，加权投票选择结果（需要足够内存）
                    </Text>
                  </Form.Item>

                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name="llm_comparison_mode" label="对比模式">
                        <Select placeholder="请选择对比模式">
                          {options?.comparison_modes.map(mode => (
                            <Option key={mode.value} value={mode.value}>{mode.label}</Option>
                          ))}
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item name="llm_comparison_strategy" label="对比策略">
                        <Select placeholder="请选择对比策略">
                          {options?.comparison_strategies.map(strategy => (
                            <Option key={strategy.value} value={strategy.value}>{strategy.label}</Option>
                          ))}
                        </Select>
                      </Form.Item>
                    </Col>
                  </Row>

                  <Form.Item name="llm_comparison_engines" label="对比引擎列表">
                    <Input placeholder="逗号分隔，如: qwen2.5-14b-chat,qwen2.5-7b-chat" />
                  </Form.Item>

                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name="llm_agreement_threshold" label="字段一致率阈值">
                        <InputNumber min={0} max={1} step={0.05} placeholder="0.7" />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item name="llm_save_all_results" label="保存所有结果">
                        <Switch checked={Boolean(llmSaveAllResults)} onChange={(checked) => form.setFieldsValue({ llm_save_all_results: checked })} />
                      </Form.Item>
                    </Col>
                  </Row>

                  <Form.Item name="llm_engine_weights" label="引擎权重(JSON)">
                    <Input.TextArea 
                      placeholder='{"qwen2.5-14b-chat":0.40,"qwen2.5-7b-chat":0.25}' 
                      rows={3}
                    />
                  </Form.Item>
                </Card>

                <Card title="LLM 解析知识库" style={{ marginTop: 24 }}>
                  <Alert
                    message="知识库作用说明"
                    description="在下方的文本框中输入企业自定义解析规则、字段别名映射、业务口径说明等，系统会在调用 LLM 解析文件时自动将其注入到系统提示词（system prompt）中，影响所有 LLM 解析请求。"
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />

                  <Form.Item name="llm_knowledge_base" label="知识库内容">
                    <Input.TextArea
                      placeholder={`例如：
1. 本公司发票中“购买方名称”统一显示为“XX科技股份有限公司”。
2. 银行流水摘要为“工资”时，对方户名应取银行备注中的公司名称。
3. 合同金额大写优先于小写，若不一致以发票或结算单为准。`}
                      rows={8}
                      showCount
                      maxLength={5000}
                    />
                  </Form.Item>

                  <input
                    type="file"
                    accept=".md,.txt,.markdown"
                    ref={fileInputRef}
                    style={{ display: 'none' }}
                    onChange={handleFileChange}
                  />
                  <Space>
                    <Button icon={<DownloadOutlined />} onClick={handleKbSave}>
                      保存到文件
                    </Button>
                    <Button icon={<SaveOutlined />} onClick={handleKbSaveAs}>
                      另存为...
                    </Button>
                    <Button icon={<UploadOutlined />} onClick={handleKbLoad}>
                      从文件载入
                    </Button>
                  </Space>
                  {kbFileName && (
                    <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
                      当前文件：{kbFileName}
                    </Text>
                  )}
                </Card>

                <Card title="规则引擎配置" style={{ marginTop: 24 }}>
                  <Form.Item name="ai_local_model_enabled" label="启用本地规则识别">
                    <Switch checked={Boolean(aiLocalModelEnabled)} onChange={(checked) => form.setFieldsValue({ ai_local_model_enabled: checked })} />
                    <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
                      启用后即使LLM不可用也能进行基本识别
                    </Text>
                  </Form.Item>

                  <Form.Item name="ai_fallback_to_rules" label="AI失败时回退到规则">
                    <Switch checked={Boolean(aiFallbackToRules)} onChange={(checked) => form.setFieldsValue({ ai_fallback_to_rules: checked })} />
                    <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
                      LLM解析失败时自动使用规则引擎
                    </Text>
                  </Form.Item>
                </Card>
              </Col>

              <Col span={8}>
                <Card title="配置说明">
                  <Alert
                    message="只要网络可达就能用"
                    description="不需要在本地下载模型，配置局域网或云端的大模型服务地址即可。"
                    type="success"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />

                  <div style={{ marginBottom: 24 }}>
                    <Text strong>支持的服务类型：</Text>
                    <ul style={{ margin: '8px 0', paddingLeft: 20 }}>
                      <li><strong>局域网 Ollama</strong>：如 http://192.168.1.100:11434/v1</li>
                      <li><strong>公司内部 vLLM</strong>：内网部署的推理服务</li>
                      <li><strong>云端 API</strong>：DeepSeek、Kimi、智谱等</li>
                      <li><strong>本地 Ollama</strong>：自己电脑跑的话用 localhost</li>
                    </ul>
                  </div>

                  <Divider />

                  <div style={{ marginBottom: 24 }}>
                    <Text strong>配置步骤：</Text>
                    <ol style={{ margin: '8px 0', paddingLeft: 20 }}>
                      <li>在 <code>AI_BASE_URL</code> 填写服务地址</li>
                      <li>在 <code>AI_MODEL</code> 选择模型名称</li>
                      <li>有 API Key 就填，没有就留空</li>
                      <li>点 <strong>测试连接</strong> 验证是否可用</li>
                    </ol>
                  </div>

                  <Divider />

                  <div style={{ marginBottom: 24 }}>
                    <Text strong>常见地址格式：</Text>
                    <pre style={{ background: '#f5f5f5', padding: 12, marginTop: 8, fontSize: 11, whiteSpace: 'pre-wrap' }}>
{`# 局域网 Ollama
http://192.168.1.100:11434/v1

# 本地 Ollama
http://localhost:11434/v1

# DeepSeek 云端
https://api.deepseek.com/v1

# Kimi 云端
https://api.moonshot.cn/v1`}
                    </pre>
                  </div>

                  <Divider />

                  <div>
                    <Text strong>配置生效方式：</Text>
                    <ul style={{ margin: '8px 0', paddingLeft: 20 }}>
                      <li>点击「保存配置」按钮保存到数据库</li>
                      <li>刷新前端页面即可生效</li>
                      <li>无需重启后端服务</li>
                    </ul>
                  </div>
                </Card>

                <Card title="当前配置状态" style={{ marginTop: 24 }}>
                  <div>
                    <Text type="secondary">供应商：</Text>
                    <Text strong>{config?.ai_provider}</Text>
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">解析模型：</Text>
                    <Text strong>{config?.ai_model || '未配置'}</Text>
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">推理模型：</Text>
                    <Text strong>{config?.ai_reasoning_model || config?.ai_model || '未配置（回退解析模型）'}</Text>
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">API URL：</Text>
                    <Text strong>{config?.ai_base_url || '未配置'}</Text>
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">并行解析：</Text>
                    <Text strong>{config?.llm_enable_parallel_parsing ? '启用' : '禁用'}</Text>
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">多引擎对比：</Text>
                    <Text strong>{config?.llm_multi_engine_enabled ? '启用' : '禁用'}</Text>
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">知识库：</Text>
                    <Text strong>{(config?.llm_knowledge_base as string | undefined)?.length ? '已加载' : '未加载'}</Text>
                  </div>
                </Card>

                <Modal
                  title="另存为 MD 文件"
                  open={saveAsModalVisible}
                  onOk={handleConfirmSaveAs}
                  onCancel={() => setSaveAsModalVisible(false)}
                  okText="保存"
                  cancelText="取消"
                >
                  <Input
                    placeholder="请输入文件名（以 .md 结尾）"
                    value={saveAsFileName}
                    onChange={(e) => setSaveAsFileName(e.target.value)}
                    suffix=".md"
                  />
                </Modal>

                <Button type="primary" icon={<SaveOutlined />} block htmlType="submit" style={{ marginTop: 24 }}>
                  保存配置
                </Button>
              </Col>
            </Row>
          </Form>
        </Tabs.TabPane>

        <Tabs.TabPane tab="科目解析规则配置" key="account-tag">
          <Alert
            type="info"
            showIcon
            message="科目解析映射已迁入「账簿维度管理」"
            description={
              <div>
                <p style={{ marginBottom: 8 }}>
                  序时簿导入时「一级科目保留 / 强制二级 / 下级段转 Tag / 摘要补维度」等规则，请在账簿维度中心的「解析映射」Tab 维护。
                </p>
                <p style={{ marginBottom: 0, color: '#666' }}>
                  本页保留 LLM 与解析引擎参数；平台默认模板仍存于 YAML，账簿侧保存后写入数据库并优先生效。
                </p>
              </div>
            }
          />
          <Button
            type="primary"
            style={{ marginTop: 16 }}
            onClick={() => navigate('/ledger/dimensions?tab=parse-mapping')}
          >
            打开账簿维度管理 · 解析映射
          </Button>
        </Tabs.TabPane>
      </Tabs>
    </div>
  )
}
