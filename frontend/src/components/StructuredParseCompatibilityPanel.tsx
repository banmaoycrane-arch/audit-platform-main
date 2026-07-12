import { Alert, Button, Col, Row, Select, Space, Typography, Upload } from 'antd'
import { FileSearchOutlined, SettingOutlined } from '@ant-design/icons'
import {
  CHARSET_OPTIONS,
  DEFAULT_STRUCTURED_PARSE_OPTIONS,
  DELIMITER_OPTIONS,
  STRUCTURED_PARSE_GUIDANCE,
  type StructuredParseOptions,
} from '../constants/structuredParseOptions'

const { Text } = Typography

export type FormatDetectionResult = {
  charset: string | null
  delimiter_label?: string | null
  detected_headers: string[]
  estimated_data_rows: number
  parseable: boolean
  hints: string[]
  company_name?: string | null
  report_period?: string | null
}

type StructuredParseCompatibilityPanelProps = {
  options: StructuredParseOptions
  onChange: (next: StructuredParseOptions) => void
  formatDetection?: FormatDetectionResult | null
  detecting?: boolean
  onPreDetect?: (file: File) => void | Promise<void>
  compact?: boolean
}

export function StructuredParseCompatibilityPanel({
  options,
  onChange,
  formatDetection,
  detecting = false,
  onPreDetect,
  compact = false,
}: StructuredParseCompatibilityPanelProps) {
  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        icon={<SettingOutlined />}
        title={STRUCTURED_PARSE_GUIDANCE.title}
        description={
          <div>
            <div style={{ marginBottom: 8 }}>{STRUCTURED_PARSE_GUIDANCE.intro}</div>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {STRUCTURED_PARSE_GUIDANCE.bullets.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        }
      />

      <Row gutter={[16, 12]}>
        <Col xs={24} md={12}>
          <Text type="secondary">字符集（CSV/TSV）</Text>
          <Select
            style={{ width: '100%', marginTop: 4 }}
            value={options.charset}
            onChange={(value) => onChange({ ...options, charset: value })}
            options={CHARSET_OPTIONS.map((item) => ({
              value: item.value,
              label: item.hint ? `${item.label} — ${item.hint}` : item.label,
            }))}
          />
        </Col>
        <Col xs={24} md={12}>
          <Text type="secondary">列分隔符（CSV/TSV）</Text>
          <Select
            style={{ width: '100%', marginTop: 4 }}
            value={options.delimiter}
            onChange={(value) => onChange({ ...options, delimiter: value })}
            options={DELIMITER_OPTIONS.map((item) => ({
              value: item.value,
              label: item.hint ? `${item.label} — ${item.hint}` : item.label,
            }))}
          />
        </Col>
      </Row>

      {onPreDetect && (
        <Space wrap>
          <Upload
            accept=".xlsx,.xls,.csv,.tsv"
            showUploadList={false}
            beforeUpload={(file) => {
              void onPreDetect(file)
              return false
            }}
          >
            <Button icon={<FileSearchOutlined />} loading={detecting}>
              预检测文件（不上传）
            </Button>
          </Upload>
          <Text type="secondary">选择本地文件，仅检测编码/分隔符/表头，不会开始正式导入</Text>
        </Space>
      )}

      {formatDetection && (
        <Alert
          title="预检测结果"
          type={formatDetection.parseable ? 'success' : 'warning'}
          showIcon
          description={
            <div>
              {formatDetection.charset && (
                <div>
                  字符集：{formatDetection.charset}
                  {formatDetection.delimiter_label ? ` · 分隔符：${formatDetection.delimiter_label}` : ''}
                </div>
              )}
              {formatDetection.company_name && <div>表头单位：{formatDetection.company_name}</div>}
              {formatDetection.report_period && <div>报表期间：{formatDetection.report_period}</div>}
              {formatDetection.detected_headers.length > 0 && (
                <div>
                  识别表头：{formatDetection.detected_headers.slice(0, 8).join('、')}
                  {formatDetection.detected_headers.length > 8 ? '…' : ''}
                </div>
              )}
              {formatDetection.estimated_data_rows > 0 && (
                <div>预估数据行：约 {formatDetection.estimated_data_rows} 行</div>
              )}
              {formatDetection.hints.map((hint) => (
                <div key={hint}>{hint}</div>
              ))}
              {!formatDetection.parseable && !compact && (
                <div style={{ marginTop: 8 }}>
                  若表头未识别，请调整上方字符集/分隔符后重新预检测，或检查列名是否包含凭证号、科目、借贷等字段。
                </div>
              )}
            </div>
          }
        />
      )}
    </Space>
  )
}

export { DEFAULT_STRUCTURED_PARSE_OPTIONS }
