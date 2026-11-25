/**
 * Capture every first-login onboarding wizard step into images/.
 * Uses Playwright against the local Vite app with mocked auth/API.
 */
import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const OUT = path.join(ROOT, 'images')
const BASE = process.env.ONBOARDING_URL || 'http://127.0.0.1:5173'

const IDENTITY = {
  id: 99,
  username: 'onboard_admin',
  role: 'admin',
  tenant_id: null,
  onboarding_approved: false,
  email: 'onboard@example.test',
  permissions: { manage_operations: true, manage_admins: true, view_inbox: true },
}

async function main() {
  await mkdir(OUT, { recursive: true })
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })

  await page.route('**/api/**', async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const p = url.pathname

    if (p === '/api/auth/status') {
      return route.fulfill({ json: { has_admins: true } })
    }
    if (p === '/api/auth/me') {
      return route.fulfill({ json: IDENTITY })
    }
    if (p === '/api/auth/login') {
      return route.fulfill({
        json: {
          token: 'b64',
          username: IDENTITY.username,
          session_id: 'shot_session',
          permissions: IDENTITY.permissions,
        },
      })
    }
    if (p === '/api/admin/tenants/list' || p === '/api/admin/tenants') {
      return route.fulfill({ json: { tenants: [], ok: true } })
    }
    if (p === '/api/admin/onboarding-kits/list') {
      return route.fulfill({ json: { templates: [] } })
    }
    if (p === '/api/tenant-change-requests/mine') {
      return route.fulfill({ json: { requests: [] } })
    }
    if (p === '/api/client-errors') {
      return route.fulfill({ json: { ok: true } })
    }
    return route.fulfill({ status: 200, json: { ok: true } })
  })

  await page.addInitScript(() => {
    localStorage.setItem('tenant-console.username', 'onboard_admin')
    localStorage.setItem('tenant-console.session_id', 'shot_session')
    localStorage.setItem('tenant-console.token', btoa('onboard_admin:shot_session'))
  })

  await page.goto(`${BASE}/#/register`, { waitUntil: 'networkidle' })
  await page.waitForSelector('text=Set up your chatbot', { timeout: 20000 })

  const shot = async (name) => {
    const file = path.join(OUT, name)
    await page.screenshot({ path: file, fullPage: true })
    console.log('wrote', file)
  }

  // 1 WhatsApp
  await page.getByLabel(/WhatsApp phone|phone number|WABA|Phone/i).first().fill('+91 98765 43210')
  // timezone already defaulted
  await shot('onboarding-01-whatsapp.png')
  await page.getByRole('button', { name: /Continue/i }).click()

  // 2 Company
  await page.waitForSelector('text=Company and business field')
  await page.getByLabel(/Company name/i).fill('Wanderly Travels')
  // pick Tours & travel vertical chip/button
  const tours = page.getByRole('button', { name: /Tours/i }).first()
  if (await tours.count()) await tours.click()
  else {
    // fallback: click text
    await page.locator('text=Tours').first().click()
  }
  await page.waitForTimeout(300)
  await shot('onboarding-02-company.png')
  await page.getByRole('button', { name: /Continue/i }).click()

  // 3 Brand
  await page.waitForSelector('text=Brand')
  await page.getByLabel(/Bot name/i).fill('Wanderly Bot')
  await page.getByLabel(/Support email/i).fill('support@wanderly.test')
  await page.getByLabel(/Support phone/i).fill('+91 98765 43210')
  await shot('onboarding-03-brand.png')
  await page.getByRole('button', { name: /Continue/i }).click()

  // 4 Domain / Your business (+ optional modules)
  await page.waitForSelector('text=Optional modules')
  await shot('onboarding-04-your-business-modules.png')
  await page.getByRole('button', { name: /Continue/i }).click()

  // 5 Notifications
  await page.waitForSelector('text=enquir', { timeout: 10000 }).catch(() => {})
  const sales = page.getByLabel(/Sales|enquir/i).first()
  if (await sales.count()) await sales.fill('sales@wanderly.test')
  await shot('onboarding-05-notifications.png')
  await page.getByRole('button', { name: /Continue/i }).click()

  // 6 Guardrails
  await page.waitForTimeout(400)
  await shot('onboarding-06-guardrails.png')
  await page.getByRole('button', { name: /Continue/i }).click()

  // 7 Review
  await page.waitForTimeout(400)
  await shot('onboarding-07-review.png')

  // Full stepper overview already on each page; also capture ecommerce modules for comparison
  // Jump back to company, switch vertical to ecommerce, go to domain for modules contrast
  await page.getByRole('button', { name: /^2\s*Company$|^Company$/i }).first().click().catch(() => {})
  // Prefer clicking the step chip "Company"
  const companyChip = page.locator('button', { hasText: 'Company' }).first()
  if (await companyChip.count()) await companyChip.click()
  await page.waitForTimeout(200)
  const ecom = page.getByRole('button', { name: /E-commerce|Retail/i }).first()
  if (await ecom.count()) {
    await ecom.click()
    // advance to domain for ecom modules
    for (const label of ['Continue', 'Continue', 'Continue']) {
      const btn = page.getByRole('button', { name: new RegExp(label, 'i') })
      if (await btn.count()) {
        const disabled = await btn.isDisabled()
        if (!disabled) await btn.click()
        await page.waitForTimeout(250)
      }
    }
    // fill brand again if needed
    if (await page.getByLabel(/Bot name/i).count()) {
      await page.getByLabel(/Bot name/i).fill('Shop Bot')
      await page.getByLabel(/Support email/i).fill('support@shop.test')
      await page.getByLabel(/Support phone/i).fill('+91 98765 43210')
      await page.getByRole('button', { name: /Continue/i }).click()
    }
    if (await page.locator('text=Optional modules').count()) {
      await shot('onboarding-04b-ecommerce-modules.png')
    }
  }

  await browser.close()
  console.log('done')
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
