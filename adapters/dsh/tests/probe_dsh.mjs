/**
 * DSH 结构探针。不调模型，不需要 API key。
 *
 *   RW_DSH_RUNTIME_DIR=/path/to/dsh-install node adapters/dsh/tests/probe_dsh.mjs
 *
 * RW_DSH_RUNTIME_DIR 指向一个装了 @deepseek-ai/dsh 的 node 目录。
 * 没设就按 NODE_PATH / 当前目录的 node_modules 解析；解析不到就以
 * `{"skipped": true}` 退出码 0 结束，让 Python 测试标 skip 而不是伪装通过。
 *
 * 输出：一行 JSON，字段见 tests/test_dsh_adapter.py。
 */

import { createRequire } from 'node:module'
import { spawn } from 'node:child_process'
import { readFile, writeFile } from 'node:fs/promises'
import { pathToFileURL } from 'node:url'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const ADAPTER_DIR = resolve(HERE, '..')
const REPO_ROOT = resolve(ADAPTER_DIR, '..', '..')
const SKILLS_DIR = join(REPO_ROOT, 'skills')
const FIXTURE_SKILLS_DIR = join(ADAPTER_DIR, 'fixtures', 'skills')
const FIXTURE_SKILL_FILE = join(FIXTURE_SKILLS_DIR, 'rw-dsh-fixture-echo', 'SKILL.md')
const FIXTURE_MCP = join(ADAPTER_DIR, 'fixtures', 'mcp', 'rw_fixture_mcp_server.mjs')

const PUBLIC_ENTRIES = ['rw-research-router', 'rw-paper-extractor', 'rw-research-referee', 'rw-phd-write']

function runtimeRequire() {
  const dir = process.env.RW_DSH_RUNTIME_DIR
  const base = dir ? join(resolve(dir), 'package.json') : join(process.cwd(), 'package.json')
  return createRequire(pathToFileURL(base))
}

async function importDsh(require, specifier) {
  return await import(pathToFileURL(require.resolve(specifier)).href)
}

/** 起 fixture MCP server 的 http 模式，读它打出来的 URL。 */
function startHttpFixture() {
  return new Promise((resolvePromise, rejectPromise) => {
    const child = spawn(process.execPath, [FIXTURE_MCP, '--transport=http', '--port=0'], { stdio: ['ignore', 'pipe', 'pipe'] })
    const timer = setTimeout(() => {
      child.kill()
      rejectPromise(new Error('fixture MCP http server 10 秒内没报 URL'))
    }, 10_000)
    let buffered = ''
    child.stdout.on('data', (chunk) => {
      buffered += chunk.toString()
      const match = buffered.match(/RW_FIXTURE_MCP_URL=(\S+)/)
      if (match) {
        clearTimeout(timer)
        resolvePromise({ child, url: match[1] })
      }
    })
    child.on('error', (error) => { clearTimeout(timer); rejectPromise(error) })
  })
}

async function probeSkills(require) {
  const { Context } = await importDsh(require, '@deepseek-ai/cordis')
  const skillModule = await importDsh(require, '@deepseek-ai/dsh-skill')
  const SkillRegistry = skillModule.default ?? skillModule.SkillRegistry
  const skillFs = await importDsh(require, '@deepseek-ai/dsh-skill-filesystem')

  const ctx = new Context()
  await ctx.plugin(SkillRegistry)
  const mainFiber = await ctx.plugin(skillFs, {
    providerName: 'rw-research',
    includeDefaultRoots: false,
    customSkillDirs: [SKILLS_DIR],
    watch: false,
  })
  const fixtureFiber = await ctx.plugin(skillFs, {
    providerName: 'rw-research-fixture',
    includeDefaultRoots: false,
    customSkillDirs: [FIXTURE_SKILLS_DIR],
    watch: false,
  })

  const summaries = await ctx.skills.list({ cwd: REPO_ROOT })
  const discovered = summaries.filter(s => s.provider === 'rw-research')

  const entryBodies = {}
  for (const name of PUBLIC_ENTRIES) {
    const definition = await ctx.skills.get(name, { cwd: REPO_ROOT })
    entryBodies[name] = {
      loaded: definition !== undefined,
      bytes: definition?.content.length ?? 0,
      provider: definition?.provider,
      resource_base: definition?.resourceBase?.path,
    }
  }

  // 改主来源的正文，再加载一次。读到新正文就说明没有第二份副本。
  const original = await readFile(FIXTURE_SKILL_FILE, 'utf8')
  const marker = `RW_FIXTURE_BODY_MARKER=mutated-${process.pid}`
  let liveEdit
  try {
    await writeFile(FIXTURE_SKILL_FILE, original.replace('RW_FIXTURE_BODY_MARKER=baseline', marker), 'utf8')
    const reloaded = await ctx.skills.get('rw-dsh-fixture-echo', { cwd: REPO_ROOT })
    liveEdit = {
      reloaded_sees_new_body: reloaded?.content.includes(marker) === true,
      resource_base: reloaded?.resourceBase?.path,
    }
  } finally {
    await writeFile(FIXTURE_SKILL_FILE, original, 'utf8')
  }

  await fixtureFiber.dispose()
  await mainFiber.dispose()

  return {
    discovered_count: discovered.length,
    discovered_names: discovered.map(s => s.name).sort(),
    sources: [...new Set(discovered.map(s => s.source))],
    model_invocable_count: discovered.filter(s => s.invocation.modelInvocable).length,
    user_invocable_count: discovered.filter(s => s.invocation.userInvocable).length,
    entry_bodies: entryBodies,
    live_edit: liveEdit,
  }
}

async function probeMcp(require) {
  const { Context } = await importDsh(require, '@deepseek-ai/cordis')
  const toolsModule = await importDsh(require, '@deepseek-ai/dsh-tools')
  const ToolRuntime = toolsModule.default ?? toolsModule.ToolRuntime
  // ToolRuntime 声明 inject: ['systemPrompt']，少了它 ctx.tools 不会出现。
  const systemPromptModule = await importDsh(require, '@deepseek-ai/dsh-system-prompt')
  const SystemPrompt = systemPromptModule.default ?? systemPromptModule.SystemPrompt
  const mcpClient = await importDsh(require, '@deepseek-ai/dsh-mcp-client')

  const result = { stdio: null, streamable_http: null }

  {
    const ctx = new Context()
    await ctx.plugin(SystemPrompt)
    await ctx.plugin(ToolRuntime)
    const fiber = await ctx.plugin(mcpClient, {
      transport: 'stdio',
      serverName: 'rwfixture',
      command: process.execPath,
      args: [FIXTURE_MCP, '--transport=stdio'],
      failOnStartupError: true,
    })
    const names = ctx.tools.schemas().map(tool => tool.name).filter(name => name.startsWith('mcp__rwfixture__')).sort()
    const call = await ctx.tools.execute({
      callId: 'rw-probe-stdio',
      name: 'mcp__rwfixture__echo_claim',
      arguments: { claim: 'handover checklist reduces errors' },
      signal: new AbortController().signal,
    })
    result.stdio = { tool_names: names, is_error: call.isError === true, call_text: renderCall(call) }
    await fiber.dispose()
  }

  const http = await startHttpFixture()
  try {
    const ctx = new Context()
    await ctx.plugin(SystemPrompt)
    await ctx.plugin(ToolRuntime)
    const fiber = await ctx.plugin(mcpClient, {
      transport: 'streamable-http',
      serverName: 'rwfixturehttp',
      url: http.url,
      failOnStartupError: true,
    })
    const names = ctx.tools.schemas().map(tool => tool.name).filter(name => name.startsWith('mcp__rwfixturehttp__')).sort()
    const call = await ctx.tools.execute({
      callId: 'rw-probe-http',
      name: 'mcp__rwfixturehttp__count_sources',
      arguments: { sources: 'a\nb\nc' },
      signal: new AbortController().signal,
    })
    result.streamable_http = {
      url_scheme: new URL(http.url).protocol,
      tool_names: names,
      is_error: call.isError === true,
      call_text: renderCall(call),
    }
    await fiber.dispose()
  } finally {
    http.child.kill()
  }

  return result
}

/** 把 ToolExecutionResult 的 content 块拍平成文本，测试只断言里面的 marker。 */
function renderCall(result) {
  const content = result?.content
  if (Array.isArray(content)) {
    return content.map(block => block?.text ?? '').join('\n')
  }
  return JSON.stringify(result ?? null)
}

async function probeRecorder() {
  const recorder = await import(pathToFileURL(join(ADAPTER_DIR, 'plugins', 'rw-research-recorder.mjs')).href)
  const events = [
    { type: 'turn/start', seq: 1, time: 1, data: { turn: 1 } },
    { type: 'user/message', seq: 2, time: 2, data: { source: { kind: 'user' }, content: '帮我拆检索式' } },
    { type: 'tool/call', seq: 3, time: 3, data: { turn: 1, step: 1, callId: 'c1', name: 'skill', arguments: '{"name":"rw-search-strategy"}' } },
    { type: 'tool/result', seq: 4, time: 4, data: { turn: 1, step: 1, message: { callId: 'c1' } } },
    { type: 'tool/call', seq: 5, time: 5, data: { turn: 1, step: 2, callId: 'c2', name: 'mcp__rwfixture__count_sources', arguments: '{}' } },
    { type: 'tool/result', seq: 6, time: 6, data: { turn: 1, step: 2, message: { callId: 'c2' }, error: { name: 'E', code: 'BOOM' } } },
    { type: 'approval/asked', seq: 7, time: 7, data: { id: 'a1', toolName: 'write', reason: '阶段门' } },
    { type: 'approval/decided', seq: 8, time: 8, data: { id: 'a1', outcome: { kind: 'approved' } } },
    { type: 'assistant/chunk', seq: 9, time: 9, data: {} },
    { type: 'turn/end', seq: 10, time: 10, data: { turn: 1, reason: { kind: 'completed' } } },
  ]
  const projected = events.map(event => recorder.projectEvent('sess-1', event)).filter(Boolean)
  return {
    projected_count: projected.length,
    stages: projected.map(record => record.rw_stage),
    skill_selected: projected.find(r => r.rw_stage === 'skill_selected')?.skill,
    mcp_flagged: projected.filter(r => r.mcp === true).length,
    failed_tool_post: projected.filter(r => r.rw_stage === 'tool_post' && r.ok === false).length,
    stop_reason: projected.find(r => r.rw_stage === 'stop')?.stop_reason,
  }
}

async function main() {
  const require = runtimeRequire()
  try {
    require.resolve('@deepseek-ai/dsh-skill-filesystem')
  } catch {
    process.stdout.write(JSON.stringify({ skipped: true, reason: '解析不到 @deepseek-ai/dsh-skill-filesystem；设 RW_DSH_RUNTIME_DIR' }) + '\n')
    return
  }
  const dshVersion = require('@deepseek-ai/dsh-skill-filesystem/package.json').version
  const report = {
    skipped: false,
    dsh_package_version: dshVersion,
    skills: await probeSkills(require),
    mcp: await probeMcp(require),
    recorder: await probeRecorder(),
  }
  process.stdout.write(JSON.stringify(report) + '\n')
}

await main()
