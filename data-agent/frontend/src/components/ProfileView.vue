<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuth } from '../composables/useAuth'
import { useTheme } from '../composables/useTheme'
import { updateProfile, changePassword, getProfileStats, type ProfileStats } from '../api/users'
import { getSavedQueries, type SavedQueryOut } from '../api/query'
import { listShares } from '../api/share'

const router = useRouter()
const { user, fetchUser } = useAuth()
const { isDark, toggleTheme } = useTheme()

// 统计数据
const stats = ref<ProfileStats>({ total_queries: 0, saved_queries: 0, shared_links: 0, data_sources: 0 })

// 最近收藏
const recentSaved = ref<SavedQueryOut[]>([])

// 最近分享
const recentShares = ref<any[]>([])

// 表单
const profileForm = ref({ email: '', phone: '' })
const profileLoading = ref(false)
const pwdForm = ref({ oldPassword: '', newPassword: '', confirmPassword: '' })
const pwdLoading = ref(false)

// 当前激活的设置面板
const activeSetting = ref('profile')

onMounted(async () => {
  if (user.value) {
    profileForm.value.email = user.value.email || ''
    profileForm.value.phone = user.value.phone || ''
  }
  // 并行加载数据
  const [statsData, savedData, sharesData] = await Promise.allSettled([
    getProfileStats(),
    getSavedQueries(),
    listShares(),
  ])
  if (statsData.status === 'fulfilled') stats.value = statsData.value
  if (savedData.status === 'fulfilled') recentSaved.value = savedData.value.slice(0, 5)
  if (sharesData.status === 'fulfilled') recentShares.value = sharesData.value.slice(0, 5)
})

async function handleUpdateProfile() {
  profileLoading.value = true
  try {
    await updateProfile(profileForm.value.email || null, profileForm.value.phone || null)
    await fetchUser()
    ElMessage.success('个人信息已更新')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '更新失败')
  } finally {
    profileLoading.value = false
  }
}

async function handleChangePassword() {
  if (!pwdForm.value.oldPassword || !pwdForm.value.newPassword) {
    ElMessage.warning('请填写完整密码信息')
    return
  }
  if (pwdForm.value.newPassword.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  if (pwdForm.value.newPassword !== pwdForm.value.confirmPassword) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  pwdLoading.value = true
  try {
    await changePassword(pwdForm.value.oldPassword, pwdForm.value.newPassword)
    ElMessage.success('密码已修改')
    pwdForm.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '密码修改失败')
  } finally {
    pwdLoading.value = false
  }
}

function handleSavedClick(_sq: SavedQueryOut) {
  router.push('/')
  // 可以在这里触发自动发送问题
}
</script>

<template>
  <div class="profile-page">
    <!-- 顶部用户信息 -->
    <div class="user-header">
      <div class="user-info">
        <el-avatar :size="72" :src="user?.avatar_url || undefined">
          {{ user?.username?.charAt(0)?.toUpperCase() }}
        </el-avatar>
        <div class="user-meta">
          <h2>{{ user?.username }}</h2>
          <div class="user-tags">
            <el-tag size="small" type="primary">{{ user?.role_name }}</el-tag>
            <span class="join-date">注册于 {{ new Date(user?.created_at || '').toLocaleDateString() }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 数据统计卡片 -->
    <div class="stats-row">
      <div class="stat-card" @click="router.push('/')">
        <div class="stat-icon">🔍</div>
        <div class="stat-value">{{ stats.total_queries }}</div>
        <div class="stat-label">查询次数</div>
      </div>
      <div class="stat-card" @click="router.push('/')">
        <div class="stat-icon">⭐</div>
        <div class="stat-value">{{ stats.saved_queries }}</div>
        <div class="stat-label">收藏查询</div>
      </div>
      <div class="stat-card" @click="router.push('/')">
        <div class="stat-icon">🔗</div>
        <div class="stat-value">{{ stats.shared_links }}</div>
        <div class="stat-label">分享链接</div>
      </div>
      <div class="stat-card" @click="router.push('/datasource')">
        <div class="stat-icon">📁</div>
        <div class="stat-value">{{ stats.data_sources }}</div>
        <div class="stat-label">数据源</div>
      </div>
    </div>

    <!-- 最近收藏 & 分享 -->
    <div class="recent-section">
      <div class="recent-block">
        <div class="recent-header">
          <h3>⭐ 最近收藏</h3>
          <el-button text size="small" @click="router.push('/')">查看全部 →</el-button>
        </div>
        <div v-if="recentSaved.length === 0" class="empty-hint">暂无收藏</div>
        <div v-else class="recent-list">
          <div v-for="sq in recentSaved" :key="sq.id" class="recent-item" @click="handleSavedClick(sq)">
            <span class="recent-name">{{ sq.name }}</span>
            <span class="recent-time">{{ new Date(sq.created_at).toLocaleDateString() }}</span>
          </div>
        </div>
      </div>

      <div class="recent-block">
        <div class="recent-header">
          <h3>🔗 最近分享</h3>
          <el-button text size="small" @click="router.push('/')">查看全部 →</el-button>
        </div>
        <div v-if="recentShares.length === 0" class="empty-hint">暂无分享</div>
        <div v-else class="recent-list">
          <div v-for="sh in recentShares" :key="sh.token" class="recent-item">
            <span class="recent-name">{{ sh.question?.slice(0, 30) }}{{ sh.question?.length > 30 ? '...' : '' }}</span>
            <span class="recent-time">{{ new Date(sh.created_at).toLocaleDateString() }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 账号设置 -->
    <div class="settings-section">
      <h3>⚙️ 账号设置</h3>
      <el-tabs v-model="activeSetting">
        <el-tab-pane label="个人信息" name="profile">
          <el-form label-width="80px" style="max-width: 450px;">
            <el-form-item label="邮箱">
              <el-input v-model="profileForm.email" placeholder="请输入邮箱" />
            </el-form-item>
            <el-form-item label="手机号">
              <el-input v-model="profileForm.phone" placeholder="请输入手机号" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="profileLoading" @click="handleUpdateProfile">保存修改</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="修改密码" name="password">
          <el-form label-width="80px" style="max-width: 450px;">
            <el-form-item label="旧密码">
              <el-input v-model="pwdForm.oldPassword" type="password" show-password placeholder="请输入旧密码" />
            </el-form-item>
            <el-form-item label="新密码">
              <el-input v-model="pwdForm.newPassword" type="password" show-password placeholder="至少 6 位" />
            </el-form-item>
            <el-form-item label="确认密码">
              <el-input v-model="pwdForm.confirmPassword" type="password" show-password placeholder="再次输入新密码" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="pwdLoading" @click="handleChangePassword">修改密码</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="偏好设置" name="preferences">
          <div class="pref-item">
            <div>
              <div class="pref-title">主题模式</div>
              <div class="pref-desc">切换明亮/暗黑主题</div>
            </div>
            <el-switch :model-value="isDark" @change="toggleTheme"
              active-text="暗黑" inactive-text="明亮" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<style scoped>
.profile-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 0 4px;
}

/* 用户头部 */
.user-header {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 16px;
  border: 1px solid var(--border-color);
}
.user-info {
  display: flex;
  align-items: center;
  gap: 20px;
}
.user-meta h2 {
  margin: 0 0 6px;
  font-size: 22px;
  color: var(--text-primary);
}
.user-tags {
  display: flex;
  align-items: center;
  gap: 10px;
}
.join-date {
  font-size: 13px;
  color: var(--text-muted);
}

/* 统计卡片 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card {
  background: var(--bg-card);
  border-radius: 10px;
  padding: 16px;
  text-align: center;
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
.stat-icon { font-size: 24px; margin-bottom: 4px; }
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #3b82f6;
}
.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

/* 最近列表 */
.recent-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}
.recent-block {
  background: var(--bg-card);
  border-radius: 10px;
  padding: 16px;
  border: 1px solid var(--border-color);
}
.recent-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.recent-header h3 {
  margin: 0;
  font-size: 15px;
  color: var(--text-primary);
}
.empty-hint {
  color: var(--text-muted);
  font-size: 13px;
  padding: 12px 0;
}
.recent-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.recent-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.recent-item:hover {
  background: var(--bg-hover);
}
.recent-name {
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.recent-time {
  font-size: 12px;
  color: var(--text-muted);
  margin-left: 8px;
  white-space: nowrap;
}

/* 设置区 */
.settings-section {
  background: var(--bg-card);
  border-radius: 10px;
  padding: 20px;
  border: 1px solid var(--border-color);
}
.settings-section h3 {
  margin: 0 0 12px;
  font-size: 16px;
  color: var(--text-primary);
}
.pref-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-color);
}
.pref-item:last-child { border-bottom: none; }
.pref-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}
.pref-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

/* 响应式 */
@media (max-width: 768px) {
  .stats-row { grid-template-columns: repeat(2, 1fr); }
  .recent-section { grid-template-columns: 1fr; }
}
</style>
