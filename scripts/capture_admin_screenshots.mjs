/**
 * Capture admin console screenshots from http://localhost:5173 (?mock=1).
 * Stubs /api/* so 401s do not wipe mock identity.
 */
import { chromium } from 'playwright'
import path from 'node:path'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const OUT = path.join(ROOT, 'images')
const BASE = process.env.UI_BASE || 'http://localhost:5173'
const TENANT = '15'

fs.mkdirSync(OUT, { recursive: true })

const pages = [
  { file: 'admin-login.png', url: `${BASE}/#/login`, mock: false },
  { file: 'admin-dashboard.png', url: `${BASE}/?mock=1#/tenants/${TENANT}/overview`, mock: true },
  { file: 'admin-chats.png', url: `${BASE}/?mock=1#/tenants/${TENANT}/inbox`, mock: true },
  { file: 'admin-profile.png', url: `${BASE}/?mock=1#/tenants/${TENANT}/profile`, mock: true },
  { file: 'admin-whatsapp-menu.png', url: `${BASE}/?mock=1#/tenants/${TENANT}/menu`, mock: true },
  { file: 'admin-profile-menu.png', url: `${BASE}/?mock=1#/tenants/${TENANT}/profile-menu`, mock: true },
  { file: 'admin-whatsapp-settings.png', url: `${BASE}/?mock=1#/tenants/${TENANT}/settings`, mock: true },
  { file: 'admin-website-crawler.png', url: `${BASE}/?mock=1#/tenants/${TENANT}/website-crawler`, mock: true },
  { file: 'admin-customers.png', url: `${BASE}/?mock=1#/tenants/${TENANT}/customers`, mock: true },
]

function stubBody(urlPath) {
  if (urlPath.includes('/auth/status')) return { has_admins: true }
  if (urlPath.includes('/auth/me')) {
    return {
      id: 0,
      username: 'simple_admin',
      role: 'admin',
      tenant_id: '15',
      onboarding_approved: true,
      permissions: { manage_operations: true, view_inbox: true, view_customers: true },
    }
  }
  if (urlPath.includes('/tenants/list') || urlPath.endsWith('/tenants')) {
    return {
      tenants: [
        {
          id: '15',
          slug: 'demo-retail',
          vertical: 'ecommerce',
          display_name: 'Demo Retail',
          status: 'active',
          current_version: 1,
        },
      ],
    }
  }
  if (urlPath.includes('/resolved')) {
    return {
      tenant_id: '15',
      brand: { name: 'Demo Retail', tagline: 'Mock shop' },
      features: { offerings: true },
      menu: { greeting: 'Hi!' },
      source: 'mock',
    }
  }
  if (urlPath.includes('/detail')) {
    return { draft: {}, live: {}, pending: null }
  }
  if (urlPath.includes('/inbox') && !urlPath.includes('/inbox/')) {
    return { queue: [], count: 0, handoff_count: 0 }
  }
  if (urlPath.includes('/conversations')) return { conversations: [], count: 0 }
  if (urlPath.includes('/chat/thread')) return { wa_id: '919876543210', messages: [] }
  if (urlPath.includes('/agents')) return { agents: [] }
  if (urlPath.includes('/chat-history')) return { history: [], count: 0 }
  if (urlPath.includes('/crawl-runs/staged')) return { pages: [], count: 0 }
  if (urlPath.includes('/crawl-runs')) return { runs: [], count: 0 }
  if (urlPath.includes('/customers')) return { customers: [], count: 0 }
  if (urlPath.includes('/files')) return { files: [], count: 0 }
  if (urlPath.includes('/knowledge-gaps')) {
    return { gaps: [], count: 0, summary: { top_queries: [], unresolved: 0, resolved: 0 } }
  }
  if (urlPath.includes('/offerings/list')) return { offerings: [], count: 0 }
  if (urlPath.includes('/errors')) return { errors: [], count: 0, total: 0 }
  if (urlPath.includes('/send2-credentials')) return { configured: false, masked: null }
  if (urlPath.includes('/tenant-change-requests')) return { requests: [], count: 0 }
  if (urlPath.includes('/profile')) return { ok: true, draft: {} }
  return { ok: true, status: 'ok' }
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await context.newPage()
  page.setDefaultTimeout(45000)

  // Stub APIs so 401 cannot clear mock identity
  await page.route('**/api/**', async (route) => {
    const req = route.request()
    if (req.resourceType() === 'websocket') return route.continue()
    const u = new URL(req.url())
    const body = stubBody(u.pathname)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    })
  })

  for (const item of pages) {
    console.log(`Capturing ${item.file}`)
    await page.goto(item.url, { waitUntil: 'domcontentloaded', timeout: 45000 })
    try {
      if (item.mock) {
        await page.waitForFunction(
          () =>
            document.body.innerText.includes('Dashboard') ||
            document.body.innerText.includes('Chats') ||
            document.body.innerText.includes('Website crawler') ||
            document.body.innerText.includes('Settings'),
          { timeout: 12000 },
        )
      } else {
        await page.waitForFunction(() => document.body.innerText.includes('Sign in'), { timeout: 10000 })
      }
    } catch {
      console.log('  (wait timed out — capturing anyway)')
    }
    await page.waitForTimeout(1800)
    const outPath = path.join(OUT, item.file)
    await page.screenshot({ path: outPath, fullPage: true })
    const sample = await page.evaluate(() =>
      document.body.innerText.slice(0, 140).replace(/\s+/g, ' '),
    )
    console.log(`  -> ${outPath}`)
    console.log(`  text: ${sample}`)
  }

  await browser.close()
  console.log('Done.')
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
