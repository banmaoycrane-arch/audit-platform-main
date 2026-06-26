import sys
sys.path.insert(0, '.')
try:
    from app.main import app
    print('SUCCESS: FastAPI app loaded')
    routes = [r.path for r in app.routes if hasattr(r, 'path')]
    audit_routes = [r for r in routes if 'audit' in r.lower()]
    print(f'Total routes: {len(routes)}')
    print(f'Audit routes ({len(audit_routes)}):')
    for r in sorted(audit_routes):
        print(f'  - {r}')
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
