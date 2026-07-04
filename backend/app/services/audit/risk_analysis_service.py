from app.services.agent.ai_client_service import get_ai_client
from app.services.doc_parsing.redaction_service import redact_text


def _fallback_explain(title: str, evidence_text: str) -> str:
    """降级方案：模板化风险解释"""
    safe_text = redact_text(evidence_text)
    return f"{title}。系统基于规则与向量相似检索发现该事项需要人工复核。证据摘要：{safe_text[:300]}。建议核对合同、发票、付款审批、业务实质与入账期间。"


def explain_risk(title: str, evidence_text: str) -> str:
    """解释风险事项，生成风险原因、审计程序和复核建议"""
    ai_client = get_ai_client()
    
    if not ai_client.enabled:
        return _fallback_explain(title, evidence_text)
    
    safe_text = redact_text(evidence_text)
    
    prompt = f"""
你是一名专业的审计人员，请分析以下财务风险事项并提供专业的风险解释报告。

风险标题：{title}

证据摘要：{safe_text[:500]}

请按照以下结构输出专业的审计分析报告：

1. 风险描述：用简洁的语言描述该风险事项的核心内容
2. 风险原因分析：分析可能导致该风险的原因
3. 涉及凭证：列出涉及的主要凭证编号和金额
4. 证据摘要：证据的核心要点
5. 建议审计程序：建议执行的审计程序
6. 人工复核要点：人工复核时需要关注的要点

输出格式要求：
- 使用中文
- 条理清晰
- 语言专业但易懂
- 不要超过500字
"""
    
    try:
        result = ai_client.sync_chat_completion([
            {"role": "system", "content": "你是一名专业的注册会计师，擅长财务审计风险分析。"},
            {"role": "user", "content": prompt.strip()},
        ])
        return result.strip()
    except Exception:
        return _fallback_explain(title, evidence_text)
