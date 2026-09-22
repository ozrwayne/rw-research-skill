#!/usr/bin/env node
/**
 * 本地 fixture MCP server，零依赖，同时支持 stdio 和 streamable-http。
 *
 *   node rw_fixture_mcp_server.mjs --transport=stdio
 *   node rw_fixture_mcp_server.mjs --transport=http [--port=0]
 *
 * http 模式启动后会往 stdout 打一行 `RW_FIXTURE_MCP_URL=http://127.0.0.1:<port>/mcp`，
 * 测试脚本读这一行再注入给 DSH 的 mcp-client。
 *
 * 只实现验证工具发现、命名、调用和结果记录需要的部分：
 * initialize / notifications/initialized / tools/list / tools/call。
 * Resources 和 Prompts 不实现——DSH 当前也不接。
 */

import { createServer } from 'node:http'
import { createInterface } from 'node:readline'

const TOOLS = [
  {
    name: 'echo_claim',
    description: 'Echo a research claim back with a fixed marker so a test can assert the round trip.',
    inputSchema: {
      type: 'object',
      properties: { claim: { type: 'string', description: 'The claim to echo.' } },
      required: ['claim'],
      additionalProperties: false,
    },
  },
  {
    name: 'count_sources',
    description: 'Count the sources in a newline-separated list.',
    inputSchema: {
      type: 'object',
      properties: { sources: { type: 'string', description: 'Newline-separated source list.' } },
      required: ['sources'],
      additionalProperties: false,
    },
  },
]

function callTool(name, args) {
  if (name === 'echo_claim') {
    return { content: [{ type: 'text', text: `RW_FIXTURE_ECHO:${String(args?.claim ?? '')}` }] }
  }
  if (name === 'count_sources') {
    const lines = String(args?.sources ?? '').split('\n').map(line => line.trim()).filter(Boolean)
    return { content: [{ type: 'text', text: `RW_FIXTURE_COUNT:${lines.length}` }] }
  }
  return { content: [{ type: 'text', text: `unknown tool ${name}` }], isError: true }
}

/**
 * 处理一条 JSON-RPC 请求。返回 undefined 表示这是通知，不回。
 * protocolVersion 原样回客户端要的那个版本，避免和 SDK 的版本协商打架。
 */
function handle(message) {
  const { id, method, params } = message
  if (id === undefined) return undefined
  switch (method) {
    case 'initialize':
      return {
        jsonrpc: '2.0',
        id,
        result: {
          protocolVersion: params?.protocolVersion ?? '2025-06-18',
          capabilities: { tools: { listChanged: false } },
          serverInfo: { name: 'rw-fixture-mcp', version: '0.1.0' },
        },
      }
    case 'ping':
      return { jsonrpc: '2.0', id, result: {} }
    case 'tools/list':
      return { jsonrpc: '2.0', id, result: { tools: TOOLS } }
    case 'tools/call':
      return { jsonrpc: '2.0', id, result: callTool(params?.name, params?.arguments) }
    default:
      return { jsonrpc: '2.0', id, error: { code: -32601, message: `method not found: ${method}` } }
  }
}

function runStdio() {
  const rl = createInterface({ input: process.stdin })
  rl.on('line', (line) => {
    const trimmed = line.trim()
    if (!trimmed) return
    let message
    try {
      message = JSON.parse(trimmed)
    } catch {
      return
    }
    const response = handle(message)
    if (response !== undefined) process.stdout.write(JSON.stringify(response) + '\n')
  })
}

function runHttp(port) {
  const server = createServer((req, res) => {
    if (req.method === 'DELETE') {
      res.writeHead(200).end()
      return
    }
    if (req.method !== 'POST') {
      res.writeHead(405, { Allow: 'POST, DELETE' }).end()
      return
    }
    const chunks = []
    req.on('data', chunk => chunks.push(chunk))
    req.on('end', () => {
      let payload
      try {
        payload = JSON.parse(Buffer.concat(chunks).toString('utf8'))
      } catch {
        res.writeHead(400, { 'content-type': 'application/json' })
        res.end(JSON.stringify({ jsonrpc: '2.0', id: null, error: { code: -32700, message: 'parse error' } }))
        return
      }
      const batch = Array.isArray(payload) ? payload : [payload]
      const responses = batch.map(handle).filter(entry => entry !== undefined)
      if (responses.length === 0) {
        // 纯通知（notifications/initialized）没有回复体。
        res.writeHead(202).end()
        return
      }
      res.writeHead(200, { 'content-type': 'application/json' })
      res.end(JSON.stringify(Array.isArray(payload) ? responses : responses[0]))
    })
  })
  server.listen(port, '127.0.0.1', () => {
    const address = server.address()
    process.stdout.write(`RW_FIXTURE_MCP_URL=http://127.0.0.1:${address.port}/mcp\n`)
  })
}

const args = process.argv.slice(2)
const transport = (args.find(a => a.startsWith('--transport=')) ?? '--transport=stdio').split('=')[1]
const port = Number((args.find(a => a.startsWith('--port=')) ?? '--port=0').split('=')[1])

if (transport === 'stdio') runStdio()
else if (transport === 'http') runHttp(port)
else {
  process.stderr.write(`unknown transport ${transport}\n`)
  process.exit(2)
}
