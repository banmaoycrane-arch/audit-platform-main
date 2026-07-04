import re


PATTERNS = [
    (re.compile(r"\b1[3-9]\d{9}\b"), "[手机号]"),
    (re.compile(r"\b\d{15}(?:\d{2}[0-9Xx])?\b"), "[身份证号]"),
    (re.compile(r"\b\d{12,30}\b"), "[账号]"),
    (re.compile(r"[\u4e00-\u9fa5]{2,}(?:有限公司|有限责任公司|集团|公司)"), "[企业名称]"),
]


def redact_text(text: str) -> str:
    redacted = text
    for pattern, replacement in PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted
