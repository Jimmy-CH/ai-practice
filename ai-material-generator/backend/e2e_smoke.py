import time

import httpx

base_api = 'http://127.0.0.1:8001'
base_web = 'http://127.0.0.1:5173'

# 1. 前端 dev server 可访问（未启动时跳过）
try:
    r = httpx.get(base_web, timeout=5)
    print('web index', r.status_code, 'AI 运营物料智能生成助手' in r.text)
    assert r.status_code == 200
    assert 'AI 运营物料智能生成助手' in r.text
except httpx.HTTPError:
    print('web dev server not running, skip web check')

# 2. 后端健康检查
r = httpx.get(f'{base_api}/api/health')
print('health', r.status_code)
assert r.status_code == 200

suffix = str(int(time.time()))

# 3. editor 登录并创建资产（标题带时间戳避免与历史数据混淆）
r = httpx.post(f'{base_api}/api/auth/login', data={'username': 'editor', 'password': 'editor123'})
print('login editor', r.status_code)
editor_token = r.json()['access_token']
editor_headers = {'Authorization': f'Bearer {editor_token}'}

r = httpx.post(f'{base_api}/api/materials', json={
    'title': f'E2E 通过链路 {suffix}',
    'content': '# E2E 测试内容',
    'material_type': 'wechat',
    'audience': 'user'
}, headers=editor_headers)
print('create', r.status_code, r.json()['status'])
mid = r.json()['id']

# 4. 提交审核
r = httpx.post(f'{base_api}/api/materials/{mid}/submit', headers=editor_headers)
print('submit', r.status_code, r.json()['status'])
assert r.json()['status'] == 'pending_review'

# 5. reviewer 登录；先验证驳回必须填写原因
r = httpx.post(f'{base_api}/api/auth/login', data={'username': 'reviewer', 'password': 'reviewer123'})
print('login reviewer', r.status_code)
reviewer_token = r.json()['access_token']
reviewer_headers = {'Authorization': f'Bearer {reviewer_token}'}

r = httpx.post(f'{base_api}/api/materials/{mid}/reviews',
               json={'action': 'reject', 'comment': '   '}, headers=reviewer_headers)
print('reject without reason', r.status_code, r.json().get('detail'))
assert r.status_code == 400

# 6. 审核通过并断言审核台账字段
r = httpx.post(f'{base_api}/api/materials/{mid}/reviews',
               json={'action': 'approve', 'comment': 'ok'}, headers=reviewer_headers)
print('approve', r.status_code, r.json()['status'])
assert r.json()['status'] == 'approved'
assert r.json()['reviewed_by'] is not None
assert r.json()['reviewed_at'] is not None

# 7. 已审核列表返回审核人用户名与审核时间
r = httpx.get(f'{base_api}/api/materials/approved', headers=editor_headers)
item = next(m for m in r.json() if m['id'] == mid)
print('approved list reviewer', item['reviewer_username'], item['reviewed_at'])
assert item['reviewer_username'] == 'reviewer'

# 8. 驳回链路：新建资产 → 提交 → 带原因驳回
r = httpx.post(f'{base_api}/api/materials', json={
    'title': f'E2E 驳回链路 {suffix}',
    'content': '# E2E 驳回内容',
    'material_type': 'wechat',
    'audience': 'user'
}, headers=editor_headers)
mid2 = r.json()['id']
r = httpx.post(f'{base_api}/api/materials/{mid2}/submit', headers=editor_headers)
r = httpx.post(f'{base_api}/api/materials/{mid2}/reviews',
               json={'action': 'reject', 'comment': '内容缺少数据来源，请补充'}, headers=reviewer_headers)
print('reject', r.status_code, r.json()['status'])
assert r.json()['status'] == 'rejected'
assert r.json()['review_comment'] == '内容缺少数据来源，请补充'

# 9. 编辑者在资产列表可见驳回原因与审核人
r = httpx.get(f'{base_api}/api/materials', headers=editor_headers)
item2 = next(m for m in r.json() if m['id'] == mid2)
assert item2['review_comment'] == '内容缺少数据来源，请补充'
assert item2['reviewer_username'] == 'reviewer'
print('editor sees reject reason ok')

# 10. rejected 重新提交后审核台账字段清空
r = httpx.post(f'{base_api}/api/materials/{mid2}/submit', headers=editor_headers)
data = r.json()
assert data['status'] == 'pending_review'
assert data['review_comment'] is None
assert data['reviewed_by'] is None
assert data['reviewed_at'] is None
print('resubmit clears review fields ok')

# 11. 下载 approved 资产
r = httpx.get(f'{base_api}/api/materials/{mid}/download', headers=editor_headers)
print('download', r.status_code, r.headers.get('content-type'))
assert r.status_code == 200
assert 'E2E 测试内容' in r.text

# 12. 生成助手送审链路：from-generation 创建草稿 → 提交审核
r = httpx.post(f'{base_api}/api/materials/from-generation', json={
    'title': f'E2E 生成助手送审 {suffix}',
    'content': '# E2E 生成助手内容',
    'material_type': 'version_announcement',
    'audience': '网点管理员',
    'source_title': f'E2E 源文档 {suffix}',
    'analysis': '{}',
}, headers=editor_headers)
print('from-generation', r.status_code, r.json()['status'])
assert r.status_code == 200
assert r.json()['status'] == 'draft'
mid3 = r.json()['id']

r = httpx.post(f'{base_api}/api/materials/{mid3}/submit', headers=editor_headers)
print('submit from-generation', r.status_code, r.json()['status'])
assert r.status_code == 200
assert r.json()['status'] == 'pending_review'

# 13. 未审核资产不可下载（mid2 此时为 pending_review）
r = httpx.get(f'{base_api}/api/materials/{mid2}/download', headers=editor_headers)
print('download pending blocked', r.status_code, r.json().get('detail'))
assert r.status_code == 400

# 14. 生成助手送审的资产审核通过后可下载（完整闭环）
r = httpx.post(f'{base_api}/api/materials/{mid3}/reviews',
               json={'action': 'approve', 'comment': '生成助手链路通过'}, headers=reviewer_headers)
print('approve from-generation', r.status_code, r.json()['status'])
assert r.status_code == 200
assert r.json()['status'] == 'approved'

r = httpx.get(f'{base_api}/api/materials/{mid3}/download', headers=editor_headers)
print('download from-generation approved', r.status_code)
assert r.status_code == 200
assert 'E2E 生成助手内容' in r.text

print('E2E smoke test passed')
