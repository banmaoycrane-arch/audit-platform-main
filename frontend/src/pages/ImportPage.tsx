import { useState } from 'react'
import { api, type ImportJob } from '../api/client'
import { FileUploader } from '../components/FileUploader'
import { useAuthStore } from '../stores/authStore'

interface ImportReport {
  job_id: number
  total_files: number
  success_files: number
  failed_files: number
  total_entries: number
  quality: {
    overall_score: number
    valid_entries: number
    invalid_entries: number
    common_issues: Record<string, number>
    recommendations: string[]
  } | null
  file_summary: Array<{
    filename: string
    type: string
    success: boolean
    entries?: number
    template?: string
    quality_score?: number
    error?: string
  }>
}

function QualityBadge({ score }: { score: number }) {
  const getColor = (s: number) => {
    if (s >= 90) return '#4caf50'
    if (s >= 70) return '#8bc34a'
    if (s >= 50) return '#ff9800'
    return '#f44336'
  }
  return (
    <span style={{
      background: getColor(score),
      color: 'white',
      padding: '2px 8px',
      borderRadius: '12px',
      fontSize: '12px',
    }}>
      {score.toFixed(1)}分
    </span>
  )
}

export function ImportPage({ jobs, onChanged }: { jobs: ImportJob[]; onChanged: () => Promise<void> }) {
  const [organizationName, setOrganizationName] = useState('默认企业')
  const [selectedJobId, setSelectedJobId] = useState<number | null>(jobs[0]?.id ?? null)
  const [message, setMessage] = useState('')
  const [report, setReport] = useState<ImportReport | null>(null)
  const [loading, setLoading] = useState(false)
  const { currentLedgerId } = useAuthStore()

  async function createJob() {
    const job = await api.createImportJob(organizationName, undefined, currentLedgerId)
    setSelectedJobId(job.id)
    setMessage(`已创建导入批次 #${job.id}`)
    setReport(null)
    await onChanged()
  }

  async function upload(file: File) {
    if (!selectedJobId) return
    await api.uploadFile(selectedJobId, file)
    setMessage(`已上传 ${file.name}`)
    await onChanged()
  }

  async function process() {
    if (!selectedJobId) return
    setLoading(true)
    try {
      const files = await api.listImportFiles(selectedJobId)
      const latestFile = [...files].sort((a, b) => b.id - a.id)[0]
      if (!latestFile) {
        throw new Error('当前任务没有可解析的上传文件')
      }
      await api.parseSourceFileWithEngine(selectedJobId, latestFile.id)
      setMessage('统一解析引擎处理完成，结果已写入草稿')

      // 获取导入报告
      try {
        const reportData = await (api as any).getImportReport?.(selectedJobId)
        if (reportData) {
          setReport(reportData)
        }
      } catch {
        // 报告不可用，继续
      }

      await onChanged()
    } catch (err: any) {
      setMessage(`处理失败：${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  async function viewReport(jobId: number) {
    try {
      const res = await fetch(`${(api as any).baseUrl}/api/import-jobs/${jobId}/report`)
      const data = await res.json()
      setReport(data)
    } catch {
      setMessage('获取报告失败')
    }
  }

  return (
    <section>
      <h2>导入会计凭证与原始文件</h2>
      <div className="panel form-grid">
        <label>企业/账簿名称<input value={organizationName} onChange={(event) => setOrganizationName(event.target.value)} /></label>
        <button onClick={createJob}>新建导入批次</button>
        <label>选择批次
          <select value={selectedJobId ?? ''} onChange={(event) => setSelectedJobId(Number(event.target.value))}>
            <option value="">请选择</option>
            {jobs.map((job) => <option key={job.id} value={job.id}>#{job.id} {job.status} 分录 {job.entry_count}</option>)}
          </select>
        </label>
        <FileUploader onUpload={upload} />
        <button onClick={process} disabled={!selectedJobId || loading}>
          {loading ? '处理中...' : '解析、标签、向量化并识别风险'}
        </button>
        {message && <p className="message">{message}</p>}
      </div>

      {/* 导入报告展示 */}
      {report && (
        <div className="panel">
          <h3>导入报告</h3>
          <div className="report-summary">
            <div className="stat-card">
              <div className="stat-value">{report.total_entries}</div>
              <div className="stat-label">总条目</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{report.success_files}/{report.total_files}</div>
              <div className="stat-label">文件成功</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">
                {report.quality ? (
                  <QualityBadge score={report.quality.overall_score} />
                ) : '-'}
              </div>
              <div className="stat-label">质量评分</div>
            </div>
          </div>

          {report.quality && (
            <div className="quality-section">
              <h4>质量分析</h4>
              <div className="quality-metrics">
                <div className="metric">
                  <span className="metric-value" style={{ color: '#4caf50' }}>{report.quality.valid_entries}</span>
                  <span className="metric-label">有效条目</span>
                </div>
                <div className="metric">
                  <span className="metric-value" style={{ color: '#ff9800' }}>{report.quality.invalid_entries}</span>
                  <span className="metric-label">异常条目</span>
                </div>
              </div>

              {report.quality.common_issues && Object.keys(report.quality.common_issues).length > 0 && (
                <div className="issues-section">
                  <h5>常见问题</h5>
                  <ul>
                    {Object.entries(report.quality.common_issues).map(([issue, count]) => (
                      <li key={issue}>{issue.replace(/_/g, ' ')}: {count}次</li>
                    ))}
                  </ul>
                </div>
              )}

              {report.quality.recommendations && report.quality.recommendations.length > 0 && (
                <div className="recommendations-section">
                  <h5>建议</h5>
                  <ul>
                    {report.quality.recommendations.map((rec, i) => (
                      <li key={i}>{rec}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {report.file_summary && report.file_summary.length > 0 && (
            <div className="file-summary">
              <h4>文件处理结果</h4>
              <table>
                <thead>
                  <tr>
                    <th>文件名</th>
                    <th>类型</th>
                    <th>状态</th>
                    <th>详情</th>
                  </tr>
                </thead>
                <tbody>
                  {report.file_summary.map((f, i) => (
                    <tr key={i}>
                      <td>{f.filename}</td>
                      <td>{f.type === 'accounting_entry' ? '会计凭证' : '原始文件'}</td>
                      <td>
                        {f.success ? (
                          <span style={{ color: '#4caf50' }}>成功</span>
                        ) : (
                          <span style={{ color: '#f44336' }}>失败</span>
                        )}
                      </td>
                      <td>
                        {f.type === 'accounting_entry' && f.template && (
                          <span>模板: {f.template}, 条目: {f.entries}, 质量: {f.quality_score?.toFixed(1)}分</span>
                        )}
                        {f.error && <span style={{ color: '#f44336' }}>{f.error}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div className="panel">
        <h3>导入批次</h3>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>状态</th>
              <th>文件数</th>
              <th>分录数</th>
              <th>操作</th>
              <th>错误</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td>{job.id}</td>
                <td>{job.status}</td>
                <td>{job.file_count}</td>
                <td>{job.entry_count}</td>
                <td>
                  <button onClick={() => viewReport(job.id)}>查看报告</button>
                </td>
                <td>{job.error_message || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <style>{`
        .report-summary {
          display: flex;
          gap: 16px;
          margin-bottom: 16px;
        }
        .stat-card {
          background: #f5f5f5;
          padding: 16px;
          border-radius: 8px;
          text-align: center;
          min-width: 100px;
        }
        .stat-value {
          font-size: 24px;
          font-weight: bold;
        }
        .stat-label {
          font-size: 12px;
          color: #666;
        }
        .quality-section {
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px solid #eee;
        }
        .quality-metrics {
          display: flex;
          gap: 24px;
          margin-bottom: 16px;
        }
        .metric {
          text-align: center;
        }
        .metric-value {
          font-size: 20px;
          font-weight: bold;
          display: block;
        }
        .metric-label {
          font-size: 12px;
          color: #666;
        }
        .issues-section, .recommendations-section {
          margin-top: 12px;
        }
        .issues-section ul, .recommendations-section ul {
          margin: 8px 0;
          padding-left: 20px;
        }
        .issues-section li, .recommendations-section li {
          color: #666;
          margin: 4px 0;
        }
        .file-summary {
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px solid #eee;
        }
        .file-summary table {
          width: 100%;
          border-collapse: collapse;
        }
        .file-summary th, .file-summary td {
          padding: 8px;
          text-align: left;
          border-bottom: 1px solid #eee;
        }
      `}</style>
    </section>
  )
}
