import React, { useState } from 'react'
import { Modal, Image, Descriptions, Tag, Tooltip, Spin } from 'antd'
import { ZoomInOutlined, ZoomOutOutlined, EyeOutlined, ReloadOutlined } from '@ant-design/icons'
import type { ContractSeal } from '../api/client'

interface SealDetailModalProps {
  seal: ContractSeal | null
  visible: boolean
  onClose: () => void
}

export const SealDetailModal: React.FC<SealDetailModalProps> = ({ seal, visible, onClose }) => {
  const [scale, setScale] = useState(1)
  const [loading, setLoading] = useState(false)

  const handleZoomIn = () => {
    setScale((prev) => Math.min(prev + 0.25, 3))
  }

  const handleZoomOut = () => {
    setScale((prev) => Math.max(prev - 0.25, 0.5))
  }

  const handleReset = () => {
    setScale(1)
  }

  const getSealTypeLabel = (sealType?: string) => {
    const typeMap: Record<string, string> = {
      contract_seal: '合同专用章',
      finance_seal: '财务专用章',
      legal_person_seal: '法人章',
    }
    return typeMap[sealType || ''] || '未知类型'
  }

  const getSealTypeColor = (sealType?: string) => {
    const colorMap: Record<string, string> = {
      contract_seal: 'blue',
      finance_seal: 'red',
      legal_person_seal: 'orange',
    }
    return colorMap[sealType || ''] || 'default'
  }

  const getShapeLabel = (bbox?: { x1: number; y1: number; x2: number; y2: number }) => {
    if (!bbox) return '未知'
    const width = bbox.x2 - bbox.x1
    const height = bbox.y2 - bbox.y1
    const ratio = Math.min(width, height) / Math.max(width, height)
    if (ratio > 0.8) return '圆形'
    if (ratio > 0.5) return '椭圆形'
    return '矩形'
  }

  const getImageUrl = (sealImagePath?: string) => {
    if (!sealImagePath) return ''
    if (sealImagePath.startsWith('http')) return sealImagePath
    return `${window.location.origin}/api/files/seal/${sealImagePath}`
  }

  if (!seal) return null

  return (
    <Modal
      title="印章详情"
      open={visible}
      onCancel={onClose}
      width={800}
      footer={null}
      destroyOnClose
    >
      <div className="seal-detail-container">
        <div className="seal-image-section">
          <div className="image-toolbar">
            <Tooltip title="放大">
              <button type="button" className="tool-btn" onClick={handleZoomIn}>
                <ZoomInOutlined />
              </button>
            </Tooltip>
            <Tooltip title="缩小">
              <button type="button" className="tool-btn" onClick={handleZoomOut}>
                <ZoomOutOutlined />
              </button>
            </Tooltip>
            <Tooltip title="重置">
              <button type="button" className="tool-btn" onClick={handleReset}>
                <ReloadOutlined />
              </button>
            </Tooltip>
            <span className="scale-info">{Math.round(scale * 100)}%</span>
          </div>
          <div className="image-wrapper">
            {loading ? (
              <div className="loading-overlay">
                <Spin size="large" />
              </div>
            ) : (
              <Image
                src={getImageUrl(seal.seal_image_path || undefined)}
                alt="印章图片"
                style={{
                  transform: `scale(${scale})`,
                  transition: 'transform 0.2s ease',
                }}
                onLoad={() => setLoading(false)}
                onError={() => setLoading(false)}
                fallback="图片加载失败"
                preview={{
                  visible: false,
                }}
              />
            )}
          </div>
        </div>

        <div className="seal-info-section">
          <Descriptions title="基本信息" column={2} bordered>
            <Descriptions.Item label="印章ID">{seal.id}</Descriptions.Item>
            <Descriptions.Item label="合同ID">{seal.contract_id}</Descriptions.Item>
            <Descriptions.Item label="页码">{seal.page_no}</Descriptions.Item>
            <Descriptions.Item label="形状">{getShapeLabel(seal.bbox)}</Descriptions.Item>
            <Descriptions.Item label="印章类型" span={2}>
              <Tag color={getSealTypeColor(seal.seal_type || undefined)}>
                {getSealTypeLabel(seal.seal_type || undefined)}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="检测置信度" span={2}>
              <span className="confidence-value">{(seal.confidence * 100).toFixed(2)}%</span>
            </Descriptions.Item>
            <Descriptions.Item label="检测方法">{seal.detection_method || '未知'}</Descriptions.Item>
            <Descriptions.Item label="源文件ID">{seal.source_file_id || '-'}</Descriptions.Item>
          </Descriptions>

          {seal.recognized_text && (
            <Descriptions title="识别文字" bordered>
              <Descriptions.Item label="识别内容" span={2}>
                <div className="recognized-text">
                  <EyeOutlined className="text-icon" />
                  <span>{seal.recognized_text}</span>
                </div>
              </Descriptions.Item>
            </Descriptions>
          )}

          {seal.text_items && seal.text_items.length > 0 && (
            <div className="text-items-section">
              <h4 className="section-title">文字坐标详情</h4>
              <div className="text-items-list">
                {seal.text_items.map((item, index) => (
                  <div key={index} className="text-item-row">
                    <span className="text-content">{item.text}</span>
                    <span className="text-position">
                      ({item.x}, {item.y})
                    </span>
                    <span className="text-confidence">
                      {(item.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <Descriptions title="检测位置" bordered>
            <Descriptions.Item label="左上角">{seal.bbox.x1}, {seal.bbox.y1}</Descriptions.Item>
            <Descriptions.Item label="右下角">{seal.bbox.x2}, {seal.bbox.y2}</Descriptions.Item>
            <Descriptions.Item label="宽度">{seal.bbox.x2 - seal.bbox.x1}px</Descriptions.Item>
            <Descriptions.Item label="高度">{seal.bbox.y2 - seal.bbox.y1}px</Descriptions.Item>
          </Descriptions>

          <Descriptions title="时间信息" column={2} bordered>
            <Descriptions.Item label="创建时间">
              {new Date(seal.created_at).toLocaleString()}
            </Descriptions.Item>
            <Descriptions.Item label="更新时间">
              {new Date(seal.updated_at).toLocaleString()}
            </Descriptions.Item>
          </Descriptions>
        </div>
      </div>

      <style>{`
        .seal-detail-container {
          display: flex;
          gap: 24px;
          max-height: 500px;
          overflow-y: auto;
        }
        .seal-image-section {
          flex: 1;
          display: flex;
          flex-direction: column;
          align-items: center;
        }
        .image-toolbar {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 16px;
        }
        .tool-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;
          border: 1px solid #d9d9d9;
          border-radius: 4px;
          background: #fff;
          cursor: pointer;
          transition: all 0.2s;
        }
        .tool-btn:hover {
          border-color: #1890ff;
          background: #e6f7ff;
        }
        .scale-info {
          margin-left: 12px;
          font-size: 12px;
          color: #666;
        }
        .image-wrapper {
          flex: 1;
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 200px;
          background: #f5f5f5;
          border-radius: 8px;
          overflow: hidden;
        }
        .loading-overlay {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(255, 255, 255, 0.8);
        }
        .image-fallback {
          color: #999;
          font-size: 14px;
        }
        .seal-info-section {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .confidence-value {
          font-weight: bold;
          color: #52c41a;
          font-size: 16px;
        }
        .recognized-text {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 14px;
          color: #333;
        }
        .text-icon {
          color: #1890ff;
        }
        .text-items-section {
          background: #fafafa;
          padding: 12px;
          border-radius: 4px;
        }
        .section-title {
          margin: 0 0 12px 0;
          font-size: 14px;
          font-weight: 500;
          color: #333;
        }
        .text-items-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .text-item-row {
          display: flex;
          align-items: center;
          gap: 16px;
          font-size: 12px;
        }
        .text-content {
          flex: 1;
          font-weight: 500;
        }
        .text-position {
          color: #666;
          font-family: monospace;
        }
        .text-confidence {
          color: #1890ff;
          font-weight: 500;
        }
      `}</style>
    </Modal>
  )
}