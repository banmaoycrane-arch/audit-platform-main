import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

modules = [
    'app.schemas.audit_workflow',
    'app.services.audit_task_service',
    'app.services.audit_branch_service',
    'app.services.audit_review_service',
    'app.services.audit_comment_service',
    'app.api.routes_audit_tasks',
    'app.api.routes_audit_branches',
    'app.api.routes_audit_review',
    'app.api.routes_audit_comments',
    'app.api.routes_audit_dashboard',
]

results = []
for mod in modules:
    try:
        __import__(mod)
        results.append((mod, 'OK', ''))
    except Exception as e:
        results.append((mod, 'FAIL', str(e)))

with open('_test_results.txt', 'w', encoding='utf-8') as f:
    for mod, status, err in results:
        f.write(f'{status}: {mod}\n')
        if err:
            f.write(f'  Error: {err}\n')

print('Done, check _test_results.txt')
