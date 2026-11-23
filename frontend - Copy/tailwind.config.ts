import type { Config } from 'tailwindcss'

/**
 * Remake semantic colours. Every value is a CSS variable from
 * `src/theme/tokens.css` — the ONLY place colour literals live. These
 * names are deliberately unlike the legacy palette below (`slate`,
 * `surface`, `accent`) so the token test can scan for exactly this set
 * and fail the build if one is ever used without a definition.
 */
const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`
const semantic = {
  canvas: v('canvas'),
  heading: v('heading'),
  tablehead: v('table-head'),
  tablestripe: v('table-stripe'),
  acchover: v('acc-hover'),
  paper: v('paper'),
  card: v('card'),
  sidebg: v('sidebg'),
  inputbg: v('input-bg'),
  tx: v('tx'),
  txmuted: v('tx-muted'),
  txfaint: v('tx-faint'),
  line: v('line'),
  linesoft: v('line-soft'),
  acc: v('acc'),
  accsoft: v('acc-soft'),
  onacc: v('on-acc'),
  attbg: v('att-bg'),
  attline: v('att-line'),
  attink: v('att-ink'),
  badbg: v('bad-bg'),
  badline: v('bad-line'),
  badink: v('bad-ink'),
  ok: v('ok'),
  oksoft: v('ok-soft'),
  chippdfbg: v('chip-pdf-bg'),
  chippdfink: v('chip-pdf-ink'),
  chipwebbg: v('chip-web-bg'),
  chipwebink: v('chip-web-ink'),
  chipmanbg: v('chip-man-bg'),
  chipmanink: v('chip-man-ink'),
  chipdefbg: v('chip-def-bg'),
  chipdefink: v('chip-def-ink'),
  bubblein: v('bubble-in'),
  switchoff: v('switch-off'),
}

/**
 * Send2Digital's light admin theme. Older components use an inverted slate
 * scale (100 is strongest text); aliases keep them on the same token palette
 * as the newer panels, including dialogs, onboarding, and legacy controls.
 */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ...semantic,
        slate: {
          100: v('tx'),
          200: v('tx'),
          300: v('tx-muted'),
          400: v('tx-muted'),
          500: v('tx-muted'),
          600: v('tx-faint'),
          700: v('line'),
        },
        surface: {
          DEFAULT: v('paper'),
          raised: v('card'),
          overlay: v('card'),
          panel: v('sidebg'),
          line: v('line'),
          // Aliases the markup was authored against (onboarding components
          // especially). Text steps come from the ink scale, background
          // steps from the surface scale above — same hues, no new colours.
          fg: v('tx'),
          muted: v('tx-muted'),
          bg: v('paper'),
          base: v('paper'),
          card: v('card'),
          elevated: v('acc-soft'),
        },
        ink: {
          DEFAULT: v('tx'),
          soft: v('tx-muted'),
          faint: v('tx-faint'),
        },
        accent: {
          50: v('acc-soft'),
          100: v('acc-soft'),
          200: v('line'),
          300: v('acc'),
          400: v('acc'),
          500: v('acc-hover'),
          600: v('acc'),
          700: v('acc-hover'),
          800: v('heading'),
          900: v('heading'),
        },
      },
      borderRadius: {
        panel: '12px',
      },
      fontFamily: {
        sans: ['Poppins', 'Segoe UI', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      // Compact Poppins typography matching the supplied admin reference.
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
        xs: ['0.8125rem', { lineHeight: '1.3rem' }],
        sm: ['0.9375rem', { lineHeight: '1.45rem' }],
        base: ['1.0625rem', { lineHeight: '1.65rem' }],
        lg: ['1.1875rem', { lineHeight: '1.8rem' }],
        xl: ['1.375rem', { lineHeight: '1.9rem' }],
        '2xl': ['1.625rem', { lineHeight: '2.1rem' }],
        '3xl': ['1.9375rem', { lineHeight: '2.3rem' }],
      },
      // Half steps the default scale skips. h-4.5 is the small Switch track
      // (Capabilities flags, permission matrix) and h-10.5 is the medium Button
      // height; without these the classes generate nothing and the elements
      // collapse.
      spacing: {
        '4.5': '1.125rem',
        '10.5': '2.625rem',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 160ms ease-out',
      },
    },
  },
  plugins: [],
} satisfies Config
