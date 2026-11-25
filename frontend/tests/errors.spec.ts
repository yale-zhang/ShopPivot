import { describe, expect, it, vi, afterEach } from 'vitest'

import { login } from '../src/api/client'
import { zhCN } from '../src/i18n/zh-CN'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('登录错误映射', () => {
  it('后端未启动（代理 500 非错误信封）提示服务不可达', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response('Bad Gateway', { status: 500, statusText: 'Internal Server Error' }),
      ),
    )
    await expect(login('owner', 'owner123')).rejects.toMatchObject({
      code: 'E008',
      userMessage: zhCN.errors.unreachable,
      retryable: true,
    })
  })

  it('后端错误信封保持原样', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: 'E002',
            layer: 'SYS',
            message: '用户名或口令错误',
            user_message: '用户名或口令错误',
            retryable: false,
            details: {},
          }),
          { status: 401, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )
    await expect(login('owner', 'bad')).rejects.toMatchObject({
      code: 'E002',
      userMessage: '用户名或口令错误',
    })
  })
})
