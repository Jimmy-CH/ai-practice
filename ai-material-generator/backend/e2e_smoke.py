import httpx

base_api = 'http://127.0.0.1:8000'
base_web = 'http://[::1]:5173'

# 1. 前端 dev server 可访问
r = httpx.get(base_web)
print('web index', r.status_code, 'AI 运营物料智能生成助手' in r.text)
assert r.status_code == 200
assert 'AI 运营物料智能生成助手' in r.text

# 2. 后端健康检查
r = httpx.get(f'{base_api}/api/health')
print('health', r.status_code)
assert r.status_code == 200

# 3. editor 登录并创建资产
r = httpx.post(f'{base_api}/api/auth/login', data={'username': 'editor', 'password': 'editor123'})
print('login editor', r.status_code)
editor_token = r.json()['access_token']

r = httpx.post(f'{base_api}/api/materials', json={
    'title': 'E2E 测试标题',
    'content': '# E2E 测试内容',
    'material_type': 'wechat',
    'audience': 'user'
}, headers={'Authorization': f'Bearer {editor_token}'})
print('create', r.status_code, r.json()['status'])
mid = r.json()['id']

# 4. 提交审核
r = httpx.post(f'{base_api}/api/materials/{mid}/submit', headers={'Authorization': f'Bearer {editor_token}'})
print('submit', r.status_code, r.json()['status'])
assert r.json()['status'] == 'pending_review'

# 5. reviewer 登录并审核通过
r = httpx.post(f'{base_api}/api/auth/login', data={'username': 'reviewer', 'password': 'reviewer123'})
print('login reviewer', r.status_code)
reviewer_token = r.json()['access_token']

r = httpx.post(f'{base_api}/api/materials/{mid}/reviews', json={'action': 'approve', 'comment': 'ok'}, headers={'Authorization': f'Bearer {reviewer_token}'})
print('approve', r.status_code, r.json()['status'])
assert r.json()['status'] == 'approved'

# 6. 下载 approved 资产
r = httpx.get(f'{base_api}/api/materials/{mid}/download', headers={'Authorization': f'Bearer {editor_token}'})
print('download', r.status_code, r.headers.get('content-type'))
assert r.status_code == 200
assert 'E2E 测试内容' in r.text

print('E2E smoke test passed')
