export const STEP_NAMES = [
  '定位仓库与变更范围',
  '收集变更（diff 与统计）',
  'AST 解析变更结构',
  'LLM 业务化改写与产品说明书生成',
  '产物生成并归档',
]

export interface StepExplain {
  read: string
  write: string
  failure: string
}

export const STEP_EXPLAINS: StepExplain[] = [
  { read: '仓库路径、base/head 引用、提交历史', write: '解析后的版本锚点与提交统计', failure: '引用无效或仓库不可读，运行终止' },
  { read: 'base..head 的逐文件 diff 与 numstat', write: '变更文件集、增删行数、模块聚类', failure: '范围内无变更提交，运行终止' },
  { read: '变更前后的文件内容', write: '导出符号增删改对比与契约信号', failure: '单文件解析失败时降级为文件级信号，不中断' },
  { read: '结构性变更 + 术语表口径 + head 全量代码快照', write: '功能点 JSON（业务/技术双写）与九节产品说明书结构化数据', failure: '单块/单模块失败降级占位；改写全部失败则运行失败' },
  { read: '结构化结果与展示选项（口径/脱敏）', write: 'checklist.csv / product-doc.md / trace.json', failure: '归档不可写，运行失败' },
]
