import requests
import tempfile
import os

API_URL = 'http://127.0.0.1:8000'

# 1. 查看当前配置
print('=== 当前解析引擎配置 ===')
config_response = requests.get(f'{API_URL}/api/config/parser-engine')
config = config_response.json()
print('ai_base_url:', config.get('ai_base_url'))
print('ai_model:', config.get('ai_model'))
print('llm_enable_parallel_parsing:', config.get('llm_enable_parallel_parsing'))
print()

# 2. 测试 LLM 解析
print('=== 测试 LLM 解析 ===')
test_text = '''增值税专用发票
发票代码: 14002345
发票号码: 00123456
开票日期: 2024年01月15日

销售方名称: 山西春刚商贸有限公司
纳税人识别号: 91140100MA0XXXXXX

购买方名称: 岚县尚德鑫矿业有限公司
纳税人识别号: 91141127MA0YYYYYY

货物名称: 钢材
规格型号: Φ16mm
单位: 吨
数量: 100
单价: 5000.00
金额: 500000.00
税率: 13%
税额: 65000.00
价税合计: 伍拾陆万伍仟元整 ￥565,000.00
'''

tmp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
tmp_file.write(test_text)
tmp_file.close()

with open(tmp_file.name, 'rb') as f:
    files = {'file': ('test_invoice.txt', f, 'text/plain')}
    data = {'organization_id': '1'}
    parse_response = requests.post(
        f'{API_URL}/api/parser-engine/parse-file',
        files=files,
        data=data,
        timeout=120
    )

result = parse_response.json()
print('file_format:', result.get('file_format'))
print('document_type:', result.get('document_type'))
print('engine_type:', result.get('engine_type'))
print('confidence:', result.get('confidence'))
print()

# 检查双引擎对比
comp = result.get('engine_comparison')
if comp:
    print('=== 双引擎对比 ===')
    print('选择原因:', comp.get('selection_reason'))
    print('规则引擎置信度:', comp.get('rule_confidence'))
    print('llm引擎置信度:', comp.get('llm_confidence'))
    
    llm_res = comp.get('llm_engine_result')
    if llm_res:
        print('LLM引擎结果名:', llm_res.get('engine_name'))
        print('LLM置信度:', llm_res.get('confidence'))
        if llm_res.get('data'):
            llm_data = llm_res['data']
            extracted = [k for k, v in llm_data.items() if v]
            print('LLM提取字段数:', len(extracted), '/', len(llm_data))
    else:
        print('LLM引擎结果为空')
else:
    print('没有engine_comparison字段')

os.unlink(tmp_file.name)
