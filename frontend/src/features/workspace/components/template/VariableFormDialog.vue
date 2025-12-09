<script setup lang="ts">
/**
 * 变量填写对话框
 *
 * Phase 4: 实例化模板时填写变量值
 */

import { ref, computed, watch } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, AlertCircle, Play } from 'lucide-vue-next'
import type { TemplateResponse, VariableSchema } from '../../types/template'
import { useTemplateStore } from '../../stores/templateStore'

const props = defineProps<{
  template: TemplateResponse | null
}>()

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  instantiated: [workflowId: string]
}>()

const store = useTemplateStore()

// 表单状态
const formValues = ref<Record<string, unknown>>({})
const newName = ref('')
const errors = ref<string[]>([])
const loading = ref(false)

// 变量列表
const variableList = computed(() => {
  if (!props.template) return []
  return Object.entries(props.template.variables).map(([name, schema]) => ({
    name,
    ...schema,
  }))
})

// 初始化表单值
watch(open, (isOpen) => {
  if (isOpen && props.template) {
    // 重置表单
    formValues.value = {}
    errors.value = []
    newName.value = ''

    // 设置默认值
    for (const [name, schema] of Object.entries(props.template.variables)) {
      if (schema.default !== undefined) {
        formValues.value[name] = schema.default
      } else if (schema.var_type === 'boolean') {
        formValues.value[name] = false
      } else if (schema.var_type === 'number') {
        formValues.value[name] = 0
      } else {
        formValues.value[name] = ''
      }
    }
  }
})

// 更新变量值
function updateValue(name: string, value: unknown) {
  formValues.value[name] = value
}

// 校验
async function validate(): Promise<boolean> {
  if (!props.template) return false

  const result = await store.validateVariables(
    props.template.template_id,
    formValues.value
  )

  errors.value = result.errors
  return result.valid
}

// 提交
async function handleSubmit() {
  if (!props.template) return

  // 校验
  const valid = await validate()
  if (!valid) return

  loading.value = true

  try {
    const workflowId = await store.instantiateTemplate(
      props.template.template_id,
      {
        variable_values: formValues.value,
        new_name: newName.value || undefined,
      }
    )

    if (workflowId) {
      emit('instantiated', workflowId)
      open.value = false
    } else {
      errors.value = [store.error || '实例化失败']
    }
  } finally {
    loading.value = false
  }
}

// 获取输入类型
function getInputType(varType: string): string {
  switch (varType) {
    case 'number':
      return 'number'
    default:
      return 'text'
  }
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent class="max-w-lg">
      <DialogHeader>
        <DialogTitle>使用模板</DialogTitle>
        <DialogDescription>
          填写变量值以创建新的工作流
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4 py-4">
        <!-- 工作流名称 -->
        <div class="space-y-2">
          <Label for="workflow-name">工作流名称</Label>
          <Input
            id="workflow-name"
            v-model="newName"
            :placeholder="template?.name ? `${template.name} (实例)` : '请输入名称'"
          />
        </div>

        <!-- 变量表单 -->
        <div v-if="variableList.length" class="space-y-4">
          <div class="text-sm font-medium">变量设置</div>

          <div
            v-for="variable in variableList"
            :key="variable.name"
            class="space-y-2"
          >
            <div class="flex items-center gap-2">
              <Label :for="variable.name">
                {{ variable.description || variable.name }}
              </Label>
              <Badge v-if="variable.required" variant="destructive" class="text-xs">
                必填
              </Badge>
              <Badge variant="outline" class="text-xs">
                {{ variable.var_type }}
              </Badge>
            </div>

            <!-- 布尔开关 -->
            <div v-if="variable.var_type === 'boolean'" class="flex items-center gap-2">
              <Switch
                :id="variable.name"
                :checked="!!formValues[variable.name]"
                @update:checked="updateValue(variable.name, $event)"
              />
              <span class="text-sm text-muted-foreground">
                {{ formValues[variable.name] ? '是' : '否' }}
              </span>
            </div>

            <!-- 枚举选择 -->
            <Select
              v-else-if="variable.enum_values?.length"
              :model-value="String(formValues[variable.name] || '')"
              @update:model-value="updateValue(variable.name, $event)"
            >
              <SelectTrigger :id="variable.name">
                <SelectValue :placeholder="`选择 ${variable.name}`" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem
                  v-for="opt in variable.enum_values"
                  :key="String(opt)"
                  :value="String(opt)"
                >
                  {{ opt }}
                </SelectItem>
              </SelectContent>
            </Select>

            <!-- 数字/字符串输入 -->
            <Input
              v-else
              :id="variable.name"
              :type="getInputType(variable.var_type)"
              :model-value="String(formValues[variable.name] || '')"
              :placeholder="variable.default !== undefined ? `默认: ${variable.default}` : '请输入'"
              @update:model-value="updateValue(variable.name, variable.var_type === 'number' ? Number($event) : $event)"
            />
          </div>
        </div>

        <!-- 无变量提示 -->
        <div v-else class="text-sm text-muted-foreground text-center py-4">
          此模板无需配置变量，直接创建即可
        </div>

        <!-- 错误提示 -->
        <Alert v-if="errors.length" variant="destructive">
          <AlertCircle class="h-4 w-4" />
          <AlertDescription>
            <ul class="list-disc list-inside">
              <li v-for="error in errors" :key="error">{{ error }}</li>
            </ul>
          </AlertDescription>
        </Alert>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="open = false">
          取消
        </Button>
        <Button @click="handleSubmit" :disabled="loading">
          <Loader2 v-if="loading" class="w-4 h-4 mr-1 animate-spin" />
          <Play v-else class="w-4 h-4 mr-1" />
          创建工作流
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
