import axios from 'axios'
import type { InternalAxiosRequestConfig } from 'axios'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 10000,
  withCredentials: true,
})

type RetryConfig = InternalAxiosRequestConfig & { retried?: boolean; sentSession?: number }
let getToken = () => ''
let getSession = () => 0
let renew = async (): Promise<boolean> => false

export function configureAuthTransport(token: () => string, refresh: () => Promise<boolean>, session: () => number) {
  getToken = token
  getSession = session
  renew = refresh
}
const accountChanged = () => new axios.CanceledError('Session changed')
apiClient.interceptors.request.use((config: RetryConfig) => {
  if (config.url?.startsWith('/auth/')) return config
  const session = getSession()
  if (config.retried && config.sentSession !== session) throw accountChanged()
  const token = getToken()
  if (!token && config.url === '/health') return config
  if (!token) throw accountChanged()
  config.sentSession = session
  config.headers.set('Authorization', `Bearer ${token}`)
  return config
}, error => { throw error }, { synchronous: true })
apiClient.interceptors.response.use(response => {
  const config = response.config as RetryConfig
  if (config.sentSession !== undefined && config.sentSession !== getSession()) throw accountChanged()
  return response
}, async error => {
  const config = error.config as RetryConfig | undefined
  if (config?.sentSession === undefined) throw error
  if (config.sentSession !== getSession()) throw accountChanged()
  if (error.response?.status === 401 && !config.retried) {
    config.retried = true
    const refreshed = await renew()
    if (config.sentSession !== getSession()) throw accountChanged()
    if (refreshed) return apiClient(config)
  }
  throw error
})

export function errorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) return '操作失败，请稍后重试。'
  const code = error.response?.data?.code
  if (code === 40320) return '云端日记已停止自动读取，请主动打开历史日记只读入口。'
  if (code === 40321) return '日记已改用本地保存，服务器不再接受日记写入或删除。'
  if (code === 42200 && error.config?.url?.startsWith('/statistics')) return '请选择有效的起止日期。'
  if (code === 40922) return '云端日记已改变，未清理副本。请重新核对本地文件和云端原件。'
  if (code === 42200 && error.config?.url?.startsWith('/problems')) return '问题内容为 1–10000 字符，不能为空；请检查分类、页码和版本。'
  if (code === 42200 && error.config?.url?.startsWith('/schedules')) return '请检查日程名称、时间、星期、日期、时区与修改版本。'
  if (code === 42200 && error.config?.url?.startsWith('/documents')) {
    return '请检查上传文件、标题（1–200 字符）、查询参数或文档版本。'
  }
  if (code === 42200 && error.config?.url?.startsWith('/notes')) {
    return '请检查笔记输入：标题为 1–200 字符，正文为 1–100000 字符且不全为空白。'
  }
  if (code === 42200 && error.config?.url?.startsWith('/journals')) {
    return '请检查日记输入：标题不超过 200 字，正文为 1–100000 字符且不全为空白，日期与查询范围需有效。'
  }
  if (code === 42200 && error.config?.url?.startsWith('/focus')) {
    return '请检查计时参数：普通时长为 1–1440 分钟；定时模式需填写含时区的起止时间，间隔为 1 分钟至 24 小时。'
  }
  if (code === 42200 && error.config?.url?.startsWith('/tasks')) {
    return '请检查任务输入：标题为 1–200 字，说明不超过 10000 字；预计耗时为 1–10080 的整数，日期和筛选条件需有效。'
  }
  if (code === 42200 && error.config?.url?.startsWith('/note-folders')) {
    return '文件夹名称需为 1–100 字符，不能使用斜杠、控制字符或仅用点号。'
  }
  const messages: Record<number, string> = {
    40340: '当前账号没有管理员权限，请使用独立管理员账号登录。',
    40408: '问题不存在或无权访问，请刷新列表。',
    40912: '问题已在其他页面修改，请刷新后重新编辑；当前输入仍保留。',
    41302: '每次最多导出 1000 条或 4 MB，请选择分类或搜索后缩小导出范围。',
    40407: '日程不存在或已被调整，请刷新周视图。',
    40909: '固定时段不能暂停；尚未开始的计时请使用取消。',
    40910: '日程已在其他页面修改，请刷新后重新编辑。',
    40911: '该日程尚未开始、已经结束、已跳过或未开启自动计时。',
    40409: '日程模板不存在，请刷新模板列表。',
    40913: '已存在同名日程模板，请换一个名字。',
    40914: '这一周的模板已在其他页面变更，请刷新后确认。',
    42209: '请检查目标周和模板数量。已过去的周无法应用模板；每个账号最多 50 个模板，每个模板最多 500 项。',
    42210: '请选择有效的起止日期，结束日期须晚于或等于开始日期，范围最多 366 天。',
    42208: '请检查日期范围：不能修改过去的日程，结束时间必须在未来，定时开始需在未来 31 天内；周计划最多 500 项。',
    41301: 'Office / PDF 不能超过 10 MB，MD / TXT 不能超过 512 KB。',
    41501: '支持 PDF、DOCX、PPTX、XLSX、XLS、Markdown 和 TXT；旧 DOC/PPT 请先转换。',
    42207: '文件损坏、加密、结构过大或无法预览。请另存为有效的非加密文件后重试，PDF 最多 300 页。',
    42206: '请上传有效 UTF-8 文本：正文为 1–100000 字符且不全为空白，文件名不超过 255 字符。',
    40406: '文档不存在或已被删除，请刷新资料列表。',
    40908: '文档标题已被其他页面修改，请重新载入后重试。',
    40101: '登录已过期，请重新登录。',
    40102: '用户名、邮箱或密码不正确。',
    40901: '用户名或邮箱已被注册。',
    40902: '已有计时或关联任务已变化，请同步当前计时后重试。',
    40402: '专注记录不存在，请同步后重试。',
    40403: '日记不存在或已被删除，请重新载入。',
    40405: '文件夹不存在或已被删除，请刷新文件夹。',
    40905: '同一层已有这个名称的文件夹，请换一个名称。',
    40906: '文件夹已被修改，请刷新文件夹后重试。',
    40907: '此文件夹包含子文件夹，请先处理子文件夹。',
    40404: '笔记不存在或已被删除。你的输入仍在，可以先复制保留。',
    40904: '笔记已在其他页面修改。你的输入仍在，请先复制保留，再重新载入最新内容。',
    40932: '保存方式已变化。请重新载入笔记，再使用“切换保存方式”。',
    42230: '加密内容校验失败。请联系平台检查该笔记及对应密钥版本。',
    42231: '内容超过加密保存支持的大小。',
    50330: '服务器内容密钥不可用，请联系平台配置或恢复密钥后重试。',
    40903: '日记已在其他页面修改或删除。你的输入仍在，请先复制保留，再重新载入最新内容。',
    40401: '任务不存在或已被删除，请刷新列表。',
    42200: '请检查输入：用户名为 3–32 位字母、数字或下划线，密码为 10–128 位；时区与网址需有效。',
    50302: '后端尚未配置登录密钥，请查看启动说明。',
  }
  return messages[code] || (error.response ? '请求未成功，请稍后重试。' : '无法连接服务，请检查后端是否启动。')
}
