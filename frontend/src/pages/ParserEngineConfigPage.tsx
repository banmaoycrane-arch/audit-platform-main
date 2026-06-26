import { useState, useEffect } from 'react'
import { Card, Row, Col, Form, Input, Select, Switch, InputNumber, Button, Space, Typography, Divider, Alert, Spin, message } from 'antd'
import { ReloadOutlined, SaveOutlined, ExperimentOutlined, InfoCircleOutlined, ThunderboltOutlined, DatabaseOutlined, SettingOutlined } from '@ant-design/icons'
import { api } from '../api/client'

const { Title, Text } = Typography
const { Option } = Select

export function ParserEngineConfigPage() {
  const [form] = Form.useForm()
  const [config, setConfig] = useState<{ [key: string]: unknown } | null>(null)
  const [options, setOptions] = useState<{
    providers: Array<{ value: string; label: string; description: string; default_base_url: string; default_model: string; requires_api_key: boolean }>
    models: Array<{ value: string; label: string; description: string }>
    comparison_modes: Array<{ value: string; label: string }>
    comparison_strategies: Array<{ value: string; label: string }>
    selection_modes: Array<{ value: string; label: string }>
  } | null>(null)
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [ollamaLoading, setOllamaLoading] = useState(false)
  const [ollamaModels, setOllamaModels] = useState<Array<{ value: string; label: string; description: string }>>([])

  useEffect(() => {
    fetchConfig()
    fetchOptions()
  }, [])

  const fetchConfig = async () => {
    try {
      const cfg = await api.getParserEngineConfig()
      setConfig(cfg)
      form.setFieldsValue(cfg)
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
      const result = await api.testAIConnection({
        ai_base_url: values.ai_base_url,
        ai_model: values.ai_model,
        ai_api_key: values.ai_api_key || undefined,
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

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      const result = await api.saveParserEngineConfig(values)
      if (result.success) {
        message.success(result.message || '配置保存成功！')
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
      <Text type="secondary">配置本地大模型连接、解析引擎性能参数和并行策略</Text>

      <Alert
        message={<><InfoCircleOutlined /> 提示：配置保存到数据库后，刷新页面即可生效，无需重启服务</>}
        type="info"
        style={{ marginBottom: 24 }}
      />

      <Form form={form} layout="vertical" onFinish={handleSave}>
        <Row gutter={16}>
          <Col span={16}>
            <Card title="AI 模型配置（本地大模型入口）" extra={<Space><Button icon={<ReloadOutlined />} onClick={fetchConfig}>刷新</Button></Space>}>
              <Divider orientation="left"><SettingOutlined /> AI供应商</Divider>
              
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

              <Divider orientation="left"><DatabaseOutlined /> 连接信息</Divider>

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
                  <Form.Item name="ai_model" label="模型名称" rules={[{ required: true, message: '请选择模型名称' }]}>
                    <Select placeholder="请选择模型" showSearch>
                      {ollamaModels.length > 0 && (
                        <>
                          <Option disabled style={{ fontWeight: 'bold' }}>—— 自动发现的模型 ——</Option>
                          {ollamaModels.map(model => (
                            <Option key={model.value} value={model.value}>
                              {model.label}
                              <div style={{ color: '#52c41a', fontSize: 12, marginTop: 4 }}>{model.description}</div>
                            </Option>
                          ))}
                          <Option disabled style={{ fontWeight: 'bold' }}>—— 常用预设模型 ——</Option>
                        </>
                      )}
                      {options?.models.map(model => (
                        <Option key={model.value} value={model.value}>
                          {model.label}
                          <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>{model.description}</div>
                        </Option>
                      ))}
                    </Select>
                  </Form.Item>
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
              <Divider orientation="left"><ThunderboltOutlined /> 模型性能</Divider>

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
                <Switch />
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
                <Switch />
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
                    <Switch />
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

            <Card title="规则引擎配置" style={{ marginTop: 24 }}>
              <Form.Item name="ai_local_model_enabled" label="启用本地规则识别">
                <Switch />
                <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
                  启用后即使LLM不可用也能进行基本识别
                </Text>
              </Form.Item>

              <Form.Item name="ai_fallback_to_rules" label="AI失败时回退到规则">
                <Switch />
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
                <Text type="secondary">模型：</Text>
                <Text strong>{config?.ai_model || '未配置'}</Text>
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
            </Card>

            <Button type="primary" icon={<SaveOutlined />} block onClick={handleSave} style={{ marginTop: 24 }}>
              保存配置
            </Button>
          </Col>
        </Row>
      </Form>
    </div>
  )
}
