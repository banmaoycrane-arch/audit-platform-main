/**
 * 文档解析闭环微服务
 *
 * 模块功能：凭证录入 Step2 的文档解析闭环微服务
 * 业务场景：在 AI 生成凭证、人工录入、序时簿导入等入口中，统一处理原始凭证文件的上传、解析、错误处理和结果交付。
 * 政策依据：项目统一解析引擎 API（/api/parser-engine/*、/api/import-jobs/*）
 * 输入数据：原始凭证文件（PDF/图片/Excel/CSV）、导入任务 ID、文档类型辅助信息
 * 输出结果：解析结果对象，包含文件信息、识别摘要、风险线索、语义标签、归档上下文等
 * 创建日期：2026-07-03
 * 更新记录：
 *   2026-07-03  初始创建，将 Step2ImportSource 内联解析逻辑抽取为自包含服务
 */

import { message } from 'antd'
import { api, type SourceFileRead } from '../api/client'

/**
 * 解析结果中的单文件摘要信息。
 */
export interface ParsedFileSummary {
  /** 原始文件名 */
  fileName: string
  /** 文件在导入任务中的 ID */
  fileId: number
  /** 识别到的单据类型 */
  documentType: string | null
  /** 解析置信度 */
  confidence: number | null
  /** 解析引擎类型 */
  engineType: string | null
  /** 错误信息（如有） */
  errorMessage: string | null
  /** 语义标签 */
  semanticTags: string[]
  /** 风险线索 */
  riskHints: Array<{ risk_type: string; severity: string; description: string }>
  /** 模块登记摘要 */
  registerSummary: string | null
  /** 归档路径 */
  archivePath: string | null
  /** 归档分类 */
  archiveCategory: string | null
  /** 项目名 */
  projectName: string | null
}

/**
 * 文档解析服务单次调用结果。
 */
export interface DocumentParseResult {
  /** 导入任务 ID */
  jobId: number
  /** 本次上传并成功解析的文件摘要列表 */
  parsedFiles: ParsedFileSummary[]
  /** 是否存在错误（部分文件可能解析失败） */
  hasErrors: boolean
  /** 全局错误信息（非文件级） */
  globalError: string | null
  /** 输出路径标识 */
  outputPath: string
}

/**
 * 解析服务配置选项。
 */
export interface DocumentParserOptions {
  /** 是否显示消息提示 */
  showMessages?: boolean
  /** 消息提示的 key，用于 Ant Design 的 message.loading/error/success */
  messageKey?: string
  /** 解析失败后是否跳转到草稿页 */
  navigateToDraftOnError?: boolean
  /** 草稿页导航函数 */
  navigate?: (path: string) => void
  /** 成功后回调 */
  onSuccess?: (result: DocumentParseResult) => void
  /** 失败后回调 */
  onError?: (error: Error, result: DocumentParseResult) => void
}

/**
 * 创建导入任务所需参数。
 */
export interface CreateImportJobParams {
  organizationName?: string
  sourceType: string
  ledgerId?: number | null
  projectId?: number | null
  auditScopeType?: 'all' | 'by_account' | 'by_period'
  auditPeriodId?: number | null
  auditAccountCodes?: string[] | null
}

/**
 * 文档解析闭环微服务。
 *
 * 财务含义：原始凭证（发票、银行回单、合同等）不直接生成正式会计分录，
 * 而是先通过统一解析引擎生成“解析草稿”和“模块台账登记证据”，
 * 后续由人工复核确认后再进入凭证生成流程，符合 AI 不绕过人工复核的原则。
 */
export class DocumentParserService {
  private options: DocumentParserOptions

  constructor(options: DocumentParserOptions = {}) {
    this.options = {
      showMessages: true,
      messageKey: 'document-parser',
      navigateToDraftOnError: false,
      ...options,
    }
  }

  /**
   * 创建导入任务。
   *
   * 业务逻辑：为后续文件上传和解析创建一个容器（import_job），
   * 该容器与账簿、项目、审计范围绑定，便于后续追溯。
   *
   * @param params 创建任务参数
   * @returns 导入任务对象
   */
  async createImportJob(params: CreateImportJobParams) {
    const {
      organizationName = '临时组织',
      sourceType,
      ledgerId,
      projectId,
      auditScopeType = 'all',
      auditPeriodId = null,
      auditAccountCodes = null,
    } = params

    return api.createImportJob(organizationName, sourceType, ledgerId, {
      audit_scope_type: auditScopeType,
      audit_period_id: auditPeriodId,
      audit_account_codes: auditAccountCodes,
      project_id: projectId,
    })
  }

  /**
   * 上传单个文件到指定导入任务。
   *
   * @param jobId 导入任务 ID
   * @param file 待上传文件
   * @param documentTypeHints 文档类型辅助信息
   * @returns 上传后的文件记录
   */
  async uploadFile(jobId: number, file: File, documentTypeHints?: string[]) {
    return api.uploadFile(jobId, file, documentTypeHints)
  }

  /**
   * 调用统一解析引擎解析单个已上传文件。
   *
   * @param jobId 导入任务 ID
   * @param fileId 文件 ID
   * @returns 解析后的文件记录（含 parser_engine_result）
   */
  async parseFileWithEngine(jobId: number, fileId: number) {
    return api.parseSourceFileWithEngine(jobId, fileId) as Promise<SourceFileRead>
  }

  /**
   * 执行完整的上传+解析闭环。
   *
   * 业务逻辑：
   * 1. 若未提供 jobId，则先创建导入任务；
   * 2. 上传文件；
   * 3. 调用统一解析引擎解析；
   * 4. 处理解析结果和错误；
   * 5. 返回标准化解析摘要。
   *
   * @param file 待上传文件
   * @param context 上下文信息
   * @returns 解析结果
   */
  async parseDocument(
    file: File,
    context: {
      jobId?: number | null
      ledgerId?: number | null
      projectId?: number | null
      sourceType?: string
      documentTypeHints?: string[]
    } = {},
  ): Promise<DocumentParseResult> {
    const {
      jobId: initialJobId,
      ledgerId,
      projectId,
      sourceType = 'ai_generated',
      documentTypeHints,
    } = context

    let jobId = initialJobId
    const result: DocumentParseResult = {
      jobId: 0,
      parsedFiles: [],
      hasErrors: false,
      globalError: null,
      outputPath: 'parser_engine_draft',
    }

    this.notifyLoading(`正在上传并解析 ${file.name} ...`)

    try {
      // 步骤 1：确保有导入任务
      if (!jobId) {
        const job = await this.createImportJob({
          sourceType,
          ledgerId,
          projectId,
        })
        jobId = job.id
      }
      result.jobId = jobId

      // 步骤 2：上传文件
      const uploadedFile = await this.uploadFile(jobId, file, documentTypeHints)

      // 步骤 3：调用统一解析引擎
      const parsedFile = await this.parseFileWithEngine(jobId, uploadedFile.id)

      // 步骤 4：标准化解析结果
      const summary = this.buildFileSummary(parsedFile)
      result.parsedFiles.push(summary)

      if (summary.errorMessage) {
        result.hasErrors = true
        this.notifyWarning(`${file.name} 已进入统一解析草稿，但存在解析提示：${summary.errorMessage}`)
      } else {
        this.notifySuccess(`${file.name} 已由统一解析引擎完成解析`)
      }

      if (this.options.onSuccess) {
        this.options.onSuccess(result)
      }
    } catch (error) {
      result.hasErrors = true
      const errorMessage = error instanceof Error ? error.message : String(error)
      result.globalError = errorMessage

      this.notifyError(`${file.name} 上传或解析失败：${errorMessage}`)

      if (this.options.navigateToDraftOnError && this.options.navigate && jobId) {
        this.options.navigate(`/ledger/vouchers/draft/${jobId}`)
      }

      if (this.options.onError) {
        this.options.onError(error instanceof Error ? error : new Error(errorMessage), result)
      }
    }

    return result
  }

  /**
   * 批量执行上传+解析闭环。
   *
   * @param files 待上传文件列表
   * @param context 上下文信息
   * @returns 汇总解析结果
   */
  async parseDocuments(
    files: File[],
    context: {
      jobId?: number | null
      ledgerId?: number | null
      projectId?: number | null
      sourceType?: string
      documentTypeHints?: string[]
    } = {},
  ): Promise<DocumentParseResult> {
    let jobId = context.jobId

    // 批量解析时共用一个导入任务
    if (!jobId && files.length > 0) {
      const job = await this.createImportJob({
        sourceType: context.sourceType || 'ai_generated',
        ledgerId: context.ledgerId,
        projectId: context.projectId,
      })
      jobId = job.id
    }

    const result: DocumentParseResult = {
      jobId: jobId || 0,
      parsedFiles: [],
      hasErrors: false,
      globalError: null,
      outputPath: 'parser_engine_draft',
    }

    for (const file of files) {
      const singleResult = await this.parseDocument(file, {
        ...context,
        jobId,
      })
      result.parsedFiles.push(...singleResult.parsedFiles)
      if (singleResult.hasErrors) {
        result.hasErrors = true
      }
      if (singleResult.globalError && !result.globalError) {
        result.globalError = singleResult.globalError
      }
      // 复用首次创建的任务 ID
      if (!jobId) {
        jobId = singleResult.jobId
        result.jobId = jobId
      }
    }

    return result
  }

  /**
   * 将后端返回的文件记录转换为前端可用的标准化摘要。
   *
   * @param file 后端 SourceFileRead 对象
   * @returns 标准化摘要
   */
  private buildFileSummary(file: SourceFileRead): ParsedFileSummary {
    const parserResult = file.parse_feedback || {}
    const moduleRegs = file.archive_context?.module_keys || []

    return {
      fileName: file.filename,
      fileId: file.id,
      documentType: parserResult.document_type || file.recognized_document_type || null,
      confidence: parserResult.confidence ?? null,
      engineType: null,
      errorMessage: parserResult.error_message || null,
      semanticTags: moduleRegs.map(key => `module:${key}`),
      riskHints: [],
      registerSummary: parserResult.document_type
        ? `统一解析引擎识别：${parserResult.document_type}`
        : '统一解析引擎已处理',
      archivePath: file.archive_path || null,
      archiveCategory: file.archive_category || null,
      projectName: file.project_name || null,
    }
  }

  private notifyLoading(content: string) {
    if (this.options.showMessages) {
      message.loading({ content, key: this.options.messageKey })
    }
  }

  private notifySuccess(content: string) {
    if (this.options.showMessages) {
      message.success({ content, key: this.options.messageKey })
    }
  }

  private notifyWarning(content: string) {
    if (this.options.showMessages) {
      message.warning({ content, key: this.options.messageKey })
    }
  }

  private notifyError(content: string) {
    if (this.options.showMessages) {
      message.error({ content, key: this.options.messageKey })
    }
  }
}
