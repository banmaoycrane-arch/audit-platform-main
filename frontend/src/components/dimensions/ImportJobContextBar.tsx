import { Alert, Button, Space } from 'antd'
import { ArrowLeftOutlined, FileSearchOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'

import {
  dimensionsPath,
  step2ReturnPath,
  step4ReturnPath,
} from '../../utils/importJobContext'

type ImportJobContextBarProps = {
  jobId: number
  activeTab?: string
}

export function ImportJobContextBar({ jobId, activeTab }: ImportJobContextBarProps) {
  if (!jobId) return null

  return (
    <Alert
      type="info"
      showIcon
      style={{ marginBottom: 16 }}
      title={`导入任务 #${jobId} — 维度维护中，staging 数据已保留，无需重新上传`}
      description={
        <Space wrap size="middle" style={{ marginTop: 4 }}>
          <span>补完主数据或待处理项后，请返回凭证流程继续复核；勿重新走 Step2 上传（除非要换文件）。</span>
          <Link to={step4ReturnPath(jobId, 'dimensions')}>
            <Button type="primary" size="small" icon={<ArrowLeftOutlined />}>
              返回 Step4 维度复核
            </Button>
          </Link>
          <Link to={step4ReturnPath(jobId, 'vouchers')}>
            <Button size="small" icon={<FileSearchOutlined />}>
              返回 Step4 凭证复核
            </Button>
          </Link>
          <Link to={step2ReturnPath(jobId)}>
            <Button size="small">查看 Step2 导入结果</Button>
          </Link>
          {activeTab !== 'pending' && (
            <Link to={dimensionsPath('pending', jobId)}>
              <Button size="small">待处理队列</Button>
            </Link>
          )}
        </Space>
      }
    />
  )
}
