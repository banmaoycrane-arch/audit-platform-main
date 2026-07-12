import { Alert, Descriptions, Tag, Typography } from 'antd'
import { useAuthStore } from '../../stores/authStore'

const { Text } = Typography

export type VoucherSignatureInfo = {
  source_preparer_name?: string | null
  cross_reviewed_by_user_id?: number | null
  cross_reviewed_by_name?: string | null
  cross_reviewed_at?: string | null
  approved_by_name?: string | null
  approved_at?: string | null
}

type VoucherSignatureStripProps = {
  signature?: VoucherSignatureInfo | null
  /** 是否在未复核时提示当前用户将作为复核人记名 */
  showReviewerHint?: boolean
  compact?: boolean
}

function formatSignedAt(value?: string | null) {
  if (!value) return null
  return value.replace('T', ' ').slice(0, 16)
}

export function VoucherSignatureStrip({
  signature,
  showReviewerHint = false,
  compact = false,
}: VoucherSignatureStripProps) {
  const { user } = useAuthStore()
  const preparer = signature?.source_preparer_name?.trim() || null
  const reviewer = signature?.cross_reviewed_by_name?.trim() || null
  const reviewerAt = formatSignedAt(signature?.cross_reviewed_at)
  const approver = signature?.approved_by_name?.trim() || null
  const approverAt = formatSignedAt(signature?.approved_at)

  if (compact) {
    return (
      <Text type="secondary" style={{ fontSize: 12 }}>
        制单：{preparer || '—'} · 复核：{reviewer || '—'}
        {approver ? ` · 审核：${approver}` : ''}
      </Text>
    )
  }

  return (
    <div style={{ marginBottom: 16 }}>
      <Descriptions
        bordered
        size="small"
        column={3}
        title="凭证签章"
        styles={{ label: { width: 72 } }}
      >
        <Descriptions.Item label="制单人">
          {preparer ? <Tag color="blue">{preparer}</Tag> : <Text type="secondary">序时簿未识别</Text>}
        </Descriptions.Item>
        <Descriptions.Item label="复核人">
          {reviewer ? (
            <span>
              <Tag color="green">{reviewer}</Tag>
              {reviewerAt && (
                <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                  {reviewerAt}
                </Text>
              )}
            </span>
          ) : (
            <Text type="secondary">待复核记名</Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="审核人">
          {approver ? (
            <span>
              <Tag color="purple">{approver}</Tag>
              {approverAt && (
                <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                  {approverAt}
                </Text>
              )}
            </span>
          ) : (
            <Text type="secondary">Step5 确认入账时记名</Text>
          )}
        </Descriptions.Item>
      </Descriptions>
      {showReviewerHint && !reviewer && user?.username && (
        <Alert
          type="info"
          showIcon
          style={{ marginTop: 8 }}
          message={`勾选「已复核」后，复核人将记名为：${user.username}`}
        />
      )}
    </div>
  )
}
