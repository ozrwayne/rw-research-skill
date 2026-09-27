/**
 * RW Research Recorder — DSH 原生 Cordis 插件。
 *
 * 挂在 `session/event` 火管上，把 RW 关心的研究阶段投影成一行一条的 JSONL。
 * 不用 Claude Code／Codex Hook 桥，不起子进程，不改 DSH 上游源码。
 *
 * 覆盖的 RW 阶段（对应关系见 ../EVENT_MAP.md）：
 *   task_entry     ← user/message（source.kind 判断是人写的还是注入的）
 *   skill_selected ← tool/call，name === 'skill'
 *   tool_pre       ← tool/call
 *   tool_post      ← tool/result
 *   stage_gate     ← approval/asked、approval/decided
 *   stop           ← turn/end
 *
 * 会话开始没有对应的 durable session event，用 `session/created` Cordis 事件补。
 * 这一条是 Cordis 事件不是 session 日志事件，EVENT_MAP.md 里单列。
 */

import { appendFileSync, mkdirSync } from 'node:fs'
import { dirname } from 'node:path'

export const name = 'rw-research-recorder'

/** 只订阅 session 服务；缺了它这个插件没有意义。 */
export const inject = ['session']

const RECORDED = new Set([
  'user/message',
  'tool/call',
  'tool/result',
  'approval/asked',
  'approval/decided',
  'turn/start',
  'turn/end',
])

/**
 * 把一条 DSH session event 投影成 RW 研究记录。
 * 纯函数，测试直接调它，不需要起 DSH。
 * @param {string} sessionId
 * @param {{type: string, seq: number, time: number, data: any}} event
 * @returns {object|undefined} 不关心的事件返回 undefined
 */
export function projectEvent(sessionId, event) {
  if (!RECORDED.has(event.type)) return undefined
  const base = {
    session: sessionId,
    seq: event.seq,
    time: event.time,
    dsh_event: event.type,
  }
  const data = event.data ?? {}
  switch (event.type) {
    case 'user/message': {
      const kind = data.source?.kind ?? 'user'
      return {
        ...base,
        rw_stage: kind === 'user' ? 'task_entry' : 'context_injected',
        source_kind: kind,
        ...kind === 'skill-invocation' ? { skill: data.source?.name } : {},
        chars: textLength(data.content),
      }
    }
    case 'tool/call': {
      const isSkillLoad = data.name === 'skill'
      return {
        ...base,
        rw_stage: isSkillLoad ? 'skill_selected' : 'tool_pre',
        turn: data.turn,
        step: data.step,
        call_id: data.callId,
        tool: data.name,
        ...isSkillLoad ? { skill: skillNameFromArguments(data.arguments) } : {},
        mcp: typeof data.name === 'string' && data.name.startsWith('mcp__'),
      }
    }
    case 'tool/result':
      return {
        ...base,
        rw_stage: 'tool_post',
        turn: data.turn,
        step: data.step,
        call_id: data.message?.callId,
        ok: data.error === undefined,
        ...data.error !== undefined ? { error_code: data.error.code } : {},
      }
    case 'approval/asked':
      return { ...base, rw_stage: 'stage_gate_open', approval: data.id, tool: data.toolName, reason: data.reason }
    case 'approval/decided':
      return { ...base, rw_stage: 'stage_gate_closed', approval: data.id, outcome: outcomeLabel(data.outcome) }
    case 'turn/start':
      return { ...base, rw_stage: 'turn_start', turn: data.turn }
    case 'turn/end':
      return { ...base, rw_stage: 'stop', turn: data.turn, stop_reason: data.reason?.kind }
    default:
      return undefined
  }
}

/** `skill` 工具的 arguments 是模型原样产出的 JSON 字符串，可能坏。 */
function skillNameFromArguments(raw) {
  if (typeof raw !== 'string') return undefined
  try {
    const parsed = JSON.parse(raw)
    return typeof parsed?.name === 'string' ? parsed.name : undefined
  } catch {
    return undefined
  }
}

function outcomeLabel(outcome) {
  if (typeof outcome === 'string') return outcome
  return outcome?.kind ?? outcome?.decision ?? undefined
}

function textLength(content) {
  if (typeof content === 'string') return content.length
  if (!Array.isArray(content)) return undefined
  let total = 0
  for (const block of content) {
    if (typeof block?.text === 'string') total += block.text.length
  }
  return total
}

/**
 * @param {import('@deepseek-ai/cordis').Context} ctx
 * @param {{logPath?: string}} config
 */
export function apply(ctx, config = {}) {
  const logPath = config.logPath ?? process.env.RW_DSH_RUN_LOG
  if (!logPath) {
    ctx.logger.warn('rw-research-recorder: 没有 logPath，也没有 RW_DSH_RUN_LOG，什么都不记录')
    return
  }
  mkdirSync(dirname(logPath), { recursive: true })

  const write = (record) => {
    try {
      appendFileSync(logPath, JSON.stringify(record) + '\n', 'utf8')
    } catch (error) {
      ctx.logger.warn(`rw-research-recorder: 写 ${logPath} 失败: ${error?.message ?? error}`)
    }
  }

  ctx.on('session/created', (session) => {
    write({ session: session.id, time: Date.now(), dsh_event: 'session/created', rw_stage: 'session_start', cwd: session.header?.cwd })
  })

  ctx.on('session/event', (session, event) => {
    const record = projectEvent(session.id, event)
    if (record !== undefined) write(record)
  })
}
