<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuth } from '../composables/useAuth'
import { updateProfile, changePassword } from '../api/users'

const { user, fetchUser } = useAuth()

const profileForm = ref({ email: '', phone: '' })
const profileLoading = ref(false)

const pwdForm = ref({ oldPassword: '', newPassword: '', confirmPassword: '' })
const pwdLoading = ref(false)

onMounted(() => {
  if (user.value) {
    profileForm.value.email = user.value.email || ''
    profileForm.value.phone = user.value.phone || ''
  }
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
</script>

<template>
  <div style="max-width: 500px;">
    <h2 style="margin: 0 0 20px 0; color: var(--text-primary);">个人中心</h2>

    <!-- 用户信息展示 -->
    <el-card style="margin-bottom: 20px; background: var(--bg-card);">
      <div style="display: flex; align-items: center; gap: 16px;">
        <el-avatar :size="64" :src="user?.avatar_url || undefined">
          {{ user?.username?.charAt(0)?.toUpperCase() }}
        </el-avatar>
        <div>
          <div style="font-size: 18px; font-weight: 600; color: var(--text-primary);">{{ user?.username }}</div>
          <el-tag size="small" style="margin-top: 4px;">{{ user?.role_name }}</el-tag>
        </div>
      </div>
    </el-card>

    <!-- 编辑个人信息 -->
    <el-card style="margin-bottom: 20px; background: var(--bg-card);">
      <template #header><span style="color: var(--text-primary);">个人信息</span></template>
      <el-form label-width="80px">
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
    </el-card>

    <!-- 修改密码 -->
    <el-card style="background: var(--bg-card);">
      <template #header><span style="color: var(--text-primary);">修改密码</span></template>
      <el-form label-width="80px">
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
    </el-card>
  </div>
</template>
