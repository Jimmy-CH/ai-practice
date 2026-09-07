<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getUsers, updateUserRole, updateUserActive, deleteUser, getRoles, type UserOut, type RoleOut } from '../api/users'

const users = ref<UserOut[]>([])
const roles = ref<RoleOut[]>([])
const loading = ref(false)

onMounted(async () => {
  await loadData()
})

async function loadData() {
  loading.value = true
  try {
    const [usersData, rolesData] = await Promise.all([getUsers(), getRoles()])
    users.value = usersData
    roles.value = rolesData
  } catch {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

async function handleRoleChange(user: UserOut, roleId: number) {
  try {
    await updateUserRole(user.id, roleId)
    user.role_name = roles.value.find(r => r.id === roleId)?.name || ''
    ElMessage.success('角色已更新')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '更新失败')
  }
}

async function handleToggleActive(user: UserOut) {
  try {
    const newVal = !user.is_active
    await updateUserActive(user.id, newVal)
    user.is_active = newVal
    ElMessage.success(newVal ? '已启用' : '已禁用')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function handleDelete(user: UserOut) {
  try {
    await ElMessageBox.confirm(`确定删除用户 "${user.username}" 吗？`, '确认删除', { type: 'warning' })
    await deleteUser(user.id)
    users.value = users.value.filter(u => u.id !== user.id)
    ElMessage.success('用户已删除')
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}
</script>

<template>
  <div>
    <h2 style="margin: 0 0 16px 0;">用户管理</h2>
    <el-table :data="users" v-loading="loading" stripe border style="width: 100%">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="email" label="邮箱" width="160">
        <template #default="{ row }">{{ row.email || '-' }}</template>
      </el-table-column>
      <el-table-column prop="phone" label="手机号" width="130">
        <template #default="{ row }">{{ row.phone || '-' }}</template>
      </el-table-column>
      <el-table-column label="角色" width="140">
        <template #default="{ row }">
          <el-select :model-value="roles.find(r => r.name === row.role_name)?.id"
            @change="(roleId: number) => handleRoleChange(row, roleId)" size="small">
            <el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-switch :model-value="row.is_active" @change="handleToggleActive(row)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button type="danger" size="small" text @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
