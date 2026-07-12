import { Card, Upload, Button, Steps, Typography, message, Tag, Space, Modal, Input, List } from 'antd'
import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { InboxOutlined, PlusOutlined, RobotOutlined } from '@ant-design/icons'
import { api } from '../../api/client'
import { FlowNav } from '../../components/FlowNav'
import { useAuthStore } from '../../stores/authStore'
import { withJobQuery } from '../../utils/navigation'

const { Dragger } = Upload
const { Title, Text } = Typography

// 预定义审计证据类型
const AUDIT_EVIDENCE_TYPES = [
  { type: 'invoice', label: '发票', icon: '🧾', description: '增值税发票、普通发票等' },
  { type: 'bank_statement', label: '银行对账单', icon: '🏦', description: '银行流水、回单等' },
  { type: 'contract', label: '合同协议', icon: '📄', description: '采购合同、销售合同等' },
  { type: 'inventory', label: '入库/出库单', icon: '📦', description: '入库单、出库单、领料单' },
  { type: 'payroll', label: '工资表', icon: '💰', description: '工资表、社保缴纳明细' },
  { type: 'fixed_asset', label: '固定资产', icon: '🏠', description: '固定资产清单、折旧表' },
  { type: 'confirmation', label: '往来询证函', icon: '✉️', description: '应收账款/应付账款询证函' },
  { type: 'other', label: '其他原始凭证', icon: '📋', description: '自定义原始凭证类型' },
]

// 上传的文件信息
interface UploadedFile {
  name: string
  size: number
  fileType: string
  jobId?: number
  fileId?: number
}

export function Step2AuditImportSource() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { currentLedgerId } = useAuthStore()
  const currentStep = 1
  const initialJobId = Number(searchParams.get('jobId') || 0)
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [selectedTypes, setSelectedTypes] = useState<string[]>([])
  const [customTypeModalVisible, setCustomTypeModalVisible] = useState(false)
  const [customTypeInput, setCustomTypeInput] = useState('')
  const [customTypes, setCustomTypes] = useState<{ type: string; label: string; description: string }[]>([])
  const [currentJobId, setCurrentJobId] = useState<number | null>(initialJobId || null)

  useEffect(() => {
    if (initialJobId) {
      setCurrentJobId(initialJobId)
    }
  }, [initialJobId])

  const syncJobIdToUrl = (jobId: number) => {
    const next = new URLSearchParams(searchParams)
    next.set('jobId', String(jobId))
    setSearchParams(next, { replace: true })
  }

  const handleUpload = async (file: File) => {
    try {
      // 确保有导入任务 ID（Step1 应已创建；此处仅作兜底）
      let jobId = currentJobId
      if (!jobId) {
        message.warning('请先从步骤1选择审计范围')
        return false
      }

      // 调用 API 上传文件
      const result = await api.uploadFile(jobId, file)

      const fileInfo: UploadedFile = {
        name: file.name,
        size: file.size,
        fileType: file.type || 'unknown',
        jobId: jobId,
        fileId: result.id,
      }
      setUploadedFiles(prev => [...prev, fileInfo])

      // 上传后走 import-jobs 解析路由（审计序时簿为场景 A，证据文件为场景 B）
      message.loading({ content: '正在解析上传的审计证据（原始资料解析 · 场景 B），请稍候...', key: 'parsing' })
      try {
        await api.parseSourceFileWithEngine(jobId, result.id)
        message.success({ content: `原始资料解析完成，${file.name} 已处理`, key: 'parsing' })
      } catch {
        message.warning({ content: `${file.name} 上传成功，但原始资料解析失败`, key: 'parsing' })
      }
    } catch (error) {
      message.error(`${file.name} 上传失败`)
      console.error('Upload error:', error)
    }
    return false // 阻止默认上传行为
  }

  const handleAddCustomType = () => {
    if (customTypeInput.trim()) {
      const newType = {
        type: `custom_${Date.now()}`,
        label: customTypeInput.trim(),
        description: '用户自定义原始凭证类型',
      }
      setCustomTypes(prev => [...prev, newType])
      setSelectedTypes(prev => [...prev, newType.type])
      setCustomTypeInput('')
      setCustomTypeModalVisible(false)
      message.success(`已添加自定义类型：${newType.label}`)
    }
  }

  const toggleType = (type: string) => {
    setSelectedTypes(prev =>
      prev.includes(type)
        ? prev.filter(t => t !== type)
        : [...prev, type]
    )
  }

  const handleNext = async () => {
    if (uploadedFiles.length === 0) {
      message.warning('请先上传文件')
      return
    }
    if (!currentJobId) {
      message.warning('导入任务未创建')
      return
    }
    // 跳转到下一步，传递 jobId
    navigate(withJobQuery('/audit/step/3', currentJobId))
  }

  return (
    <div style={{ padding: '24px', maxWidth: '900px', margin: '0 auto' }}>
      <Steps
        current={currentStep}
        items={[
          { title: '选择范围' },
          { title: '导入资料' },
          { title: '导入分录' },
          { title: '执行测试' },
          { title: '复核发现' },
          { title: '导出报告' }
        ]}
        style={{ marginBottom: '32px' }}
      />

      <FlowNav
        prev={withJobQuery('/audit/step/1', currentJobId)}
        onNext={handleNext}
        nextDisabled={uploadedFiles.length === 0 || !currentJobId}
        style={{ marginBottom: '16px' }}
      />

      <Title level={4}>导入审计证据</Title>
      <Text type="secondary">选择原始凭证类型，上传支持性文件</Text>

      <Card style={{ marginTop: '16px' }}>
        <Title level={5}>1. 选择原始凭证类型</Title>
        <Text type="secondary">勾选本次审计需要用到的原始凭证类型（可多选）</Text>

        <div style={{ marginTop: '16px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {[...AUDIT_EVIDENCE_TYPES.filter(t => t.type !== 'other'), ...customTypes].map((item) => (
            <Tag.CheckableTag
              key={item.type}
              checked={selectedTypes.includes(item.type)}
              onClick={() => toggleType(item.type)}
              style={{
                padding: '8px 16px',
                fontSize: '14px',
                borderRadius: '6px',
              }}
            >
              <Space>
                <span>{'icon' in item && typeof item.icon === 'string' ? item.icon : '📋'}</span>
                <span>{item.label}</span>
              </Space>
            </Tag.CheckableTag>
          ))}
        </div>

        <Button
          type="dashed"
          icon={<PlusOutlined />}
          onClick={() => setCustomTypeModalVisible(true)}
          style={{ marginTop: '16px' }}
        >
          添加自定义凭证类型
        </Button>

        {selectedTypes.length > 0 && (
          <div style={{ marginTop: '16px', padding: '12px', background: '#f6ffed', borderRadius: '6px' }}>
            <Text type="secondary">
              <RobotOutlined style={{ color: '#52c41a', marginRight: '8px' }} />
              已选择 {selectedTypes.length} 种凭证类型，系统将根据类型自动分配导入处理流程
            </Text>
          </div>
        )}
      </Card>

      <Card style={{ marginTop: '16px' }}>
        <Title level={5}>2. 上传原始凭证文件</Title>

        <Dragger
          name="files"
          multiple
          beforeUpload={handleUpload}
          accept=".xlsx,.xls,.csv,.pdf,.jpg,.jpeg,.png,.txt"
          style={{ padding: '40px' }}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">
            支持多种格式，可多选。上传后系统将根据文件类型自动分类
          </p>
        </Dragger>

        {uploadedFiles.length > 0 && (
          <List
            header={<Text strong>已上传文件 ({uploadedFiles.length})</Text>}
            dataSource={uploadedFiles}
            renderItem={(file) => (
              <List.Item>
                <List.Item.Meta
                  title={file.name}
                  description={`${(file.size / 1024).toFixed(1)} KB`}
                />
              </List.Item>
            )}
            style={{ marginTop: '16px' }}
          />
        )}
      </Card>

      <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
        <Button onClick={() => navigate(withJobQuery('/audit/step/1', currentJobId))}>
          上一步
        </Button>
        <Button
          type="primary"
          onClick={handleNext}
          disabled={uploadedFiles.length === 0}
        >
          下一步 {uploadedFiles.length > 0 ? `(${uploadedFiles.length}个文件)` : ''}
        </Button>
      </div>

      <Modal
        title="添加自定义凭证类型"
        open={customTypeModalVisible}
        onOk={handleAddCustomType}
        onCancel={() => {
          setCustomTypeModalVisible(false)
          setCustomTypeInput('')
        }}
        okText="添加"
        cancelText="取消"
      >
        <div style={{ marginBottom: '16px' }}>
          <Text type="secondary">
            如果您的审计证据包含特殊类型的原始凭证（如入库单、验收单、审批单等），
            可以在这里添加，系统将自动识别并处理。
          </Text>
        </div>
        <Input
          placeholder="请输入凭证类型名称，如：入库单、验收单、出库单"
          value={customTypeInput}
          onChange={(e) => setCustomTypeInput(e.target.value)}
          onPressEnter={handleAddCustomType}
        />
        <div style={{ marginTop: '8px', color: '#999', fontSize: '12px' }}>
          <Text type="warning">提示：</Text> 请尽量使用规范的凭证名称，便于系统识别
        </div>
      </Modal>
    </div>
  )
}
