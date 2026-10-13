<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ asset: any }>()
const emit = defineEmits<{ save: [content: any]; submit: [] }>()
const local = ref<any>({})

watch(() => props.asset, (a) => { local.value = JSON.parse(JSON.stringify(a.content || {})) }, { immediate: true })

function addFaq() {
  if (!local.value.items) local.value.items = []
  local.value.items.push({ question: '', answer: '', source_ids: [] })
}

function removeFaq(index: number) {
  local.value.items.splice(index, 1)
}
</script>

<template>
  <el-card>
    <template #header>
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span>状态：{{ asset.status }}</span>
        <el-space>
          <el-button size="small" @click="emit('save', local)">保存</el-button>
          <el-button v-if="asset.status === 'draft' || asset.status === 'rejected'" size="small" type="primary" @click="emit('submit')">提交审核</el-button>
        </el-space>
      </div>
    </template>

    <div v-if="asset.kind === 'announcement'">
      <el-form label-width="80px">
        <el-form-item label="标题"><el-input v-model="local.title" /></el-form-item>
        <el-form-item label="摘要"><el-input v-model="local.summary" type="textarea" /></el-form-item>
        <el-form-item label="正文"><el-input v-model="local.body" type="textarea" :rows="6" /></el-form-item>
        <el-form-item label="行动项">
          <div v-for="(_, i) in local.actions" :key="i" style="display:flex;gap:8px;margin-bottom:8px;width:100%">
            <el-input v-model="local.actions[i]" />
            <el-button size="small" @click="local.actions.splice(i, 1)">删除</el-button>
          </div>
          <el-button size="small" @click="local.actions.push('')">添加行动项</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div v-else-if="asset.kind === 'faq'">
      <el-button size="small" @click="addFaq">添加问答</el-button>
      <div v-for="(item, i) in local.items" :key="i" style="margin-top:12px;border:1px solid #e4e7ed;padding:12px;border-radius:4px">
        <el-form label-width="60px">
          <el-form-item label="问题"><el-input v-model="item.question" /></el-form-item>
          <el-form-item label="答案"><el-input v-model="item.answer" type="textarea" :rows="3" /></el-form-item>
        </el-form>
        <el-button size="small" type="danger" @click="removeFaq(i)">删除</el-button>
      </div>
    </div>

    <div v-else-if="asset.kind === 'poster'">
      <el-form label-width="80px">
        <el-form-item label="主标题"><el-input v-model="local.headline" /></el-form-item>
        <el-form-item label="副标题"><el-input v-model="local.subhead" /></el-form-item>
        <el-form-item label="卖点">
          <div v-for="(_, i) in local.selling_points" :key="i" style="display:flex;gap:8px;margin-bottom:8px;width:100%">
            <el-input v-model="local.selling_points[i]" />
            <el-button size="small" @click="local.selling_points.splice(i, 1)">删除</el-button>
          </div>
          <el-button size="small" @click="local.selling_points.push('')">添加卖点</el-button>
        </el-form-item>
        <el-form-item label="行动号召"><el-input v-model="local.cta" /></el-form-item>
      </el-form>
      <el-card style="margin-top:16px;background:#f5f7fa">
        <h3 style="margin:0">{{ local.headline }}</h3>
        <p style="color:#666">{{ local.subhead }}</p>
        <ul><li v-for="(p, i) in local.selling_points" :key="i">{{ p }}</li></ul>
        <p><strong>{{ local.cta }}</strong></p>
      </el-card>
    </div>
  </el-card>
</template>
