#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""诊断脚本：检查后端服务状态"""

import urllib.request
import json
import sys
import os

result_file = r"e:\projects\finance-vector-audit\wroksapce20260616\diag_result.json"
result = {"steps": []}

# Step 1: 检查健康端点
try:
    r = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)
    result["health"] = {"status": r.status, "body": r.read().decode()}
    result["steps"].append("health_check: OK")
except Exception as e:
    result["health"] = {"error": str(e)}
    result["steps"].append(f"health_check: FAILED - {e}")

# Step 2: 写入结果文件
try:
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    result["steps"].append(f"write_result: OK - {result_file}")
except Exception as e:
    result["write_error"] = str(e)
    result["steps"].append(f"write_result: FAILED - {e}")

# Step 3: 打印到 stdout
print(json.dumps(result, ensure_ascii=False, indent=2))
