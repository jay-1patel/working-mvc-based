/**
 * The vertical catalog — the single place the UI decides "what should I ask,
 * and what should I show".
 *
 * Each entry describes one business field (software & IT, tours & travel, ...)
 * and drives:
 *   - which onboarding questions appear,
 *   - which Optional modules are offered (and which start on),
 *   - the vocabulary the bot will use ("services" vs "products" vs "packages"),
 *   - the preview shown before the tenant is created.
 *
 * Feature defaults still live on the server (`shared/tenancy/defaults.py`).
 * This file does not duplicate them for behaviour — only for presentation: the
 * values here are seeded into the draft and the server remains the authority.
 */

import { FEATURE_FLAGS, type FeatureFlag, type Vertical } from './types'

export type QuestionKind = 'text' | 'textarea' | 'chips' | 'select'

export interface VerticalQuestion {
  key: string
  label: string
  kind: QuestionKind
  placeholder?: string
  help?: string
  required?: boolean
  options?: string[]
  /** Suggested chips offered as one-tap additions. */
  suggestions?: string[]
}

export interface VerticalContent {
  /** Panel + sidebar title, e.g. "Services". */
  label: string
  /** One item, e.g. "Add a service". */
  singular: string
  /** Suggested groups offered as one-tap chips when adding. */
  categories: string[]
  /** Detail fields this vertical cares about, stored in `attrs`. */
  extraFields: { key: string; label: string; placeholder?: string }[]
  /** Price field label. `null` hides price - a consultancy has no list price. */
  priceLabel: string | null
}

/** One toggle on the onboarding "Optional modules" panel for this vertical. */
export interface OptionalModule {
  flag: FeatureFlag
  label: string
  description: string
  /** Pre-selected when this vertical is chosen. */
  defaultOn: boolean
}

/**
 * Always enabled for every tenant (not shown as Optional modules toggles).
 * FAQ / KB / handoff / talk-to-human stay on so support substrate never disappears.
 */
export const SUBSTRATE_FEATURES: FeatureFlag[] = [
  'faq',
  'kb',
  'handoff',
  'human_handover',
]

export interface VerticalMeta {
  id: Vertical
  label: string
  /** Short form for chips and summaries. */
  short: string
  blurb: string
  /** Lucide icon name from `lucide-react`. */
  icon: string
  /** Feeds `prompt.industry`. */
  industry: string
  /** Feeds `prompt.listing_type`. */
  listingType: string
  /** Feeds `prompt.domain_specific_queries`. */
  domainQueries: string
  /** Feeds `prompt.tone`. */
  tone: string
  nouns: {
    item: string
    itemSingular: string
    browse: string
    catalog: string
    lead: string
    leadAction: string
  }
  /**
   * What the admin adds, edits and deletes on this tenant's content panel.
   * The panel is the same offering record for every vertical; only the words,
   * the suggested groups and the extra detail fields differ.
   */
  content: VerticalContent
  /**
   * Vertical-specific Optional modules list. Only these flags appear as
   * toggles; commerce flags are omitted for non-shop verticals, etc.
   */
  optionalModules: OptionalModule[]
  /** Capability groups to hide entirely for this vertical. */
  hiddenGroups: string[]
  /** Plain-language "your bot will be able to..." bullets. */
  capabilities: string[]
  questions: VerticalQuestion[]
}

/** Seeded feature flags: substrate + every optional module marked defaultOn. */
export function defaultFeaturesFor(meta: Pick<VerticalMeta, 'optionalModules'>): FeatureFlag[] {
  const on = new Set<FeatureFlag>(SUBSTRATE_FEATURES)
  for (const mod of meta.optionalModules) {
    if (mod.defaultOn) on.add(mod.flag)
  }
  return FEATURE_FLAGS.filter((flag) => on.has(flag))
}

export const FEATURE_GROUPS: {
  id: string
  label: string
  description: string
  flags: FeatureFlag[]
}[] = [
  {
    id: 'commerce',
    label: 'Selling online',
    description: 'Cart, checkout and everything that follows an order.',
    flags: ['cart', 'buy_now', 'orders', 'track_order', 'returns', 'distributors'],
  },
  {
    id: 'catalogue',
    label: 'Brochure',
    description: 'What you sell or offer, and the brochure that lists it.',
    flags: ['offerings', 'offering_details', 'services', 'products', 'products_schemes', 'brochure_pdf'],
  },
  {
    id: 'enquiry',
    label: 'Enquiries and bookings',
    description: 'Turning a conversation into a lead, a quote or an appointment.',
    flags: ['lead_capture', 'quote', 'callback', 'book_appointment'],
  },
  {
    id: 'support',
    label: 'Self-service support',
    description: 'The bot answers from your own knowledge base.',
    flags: ['faq', 'kb', 'complaints', 'campaigns'],
  },
  {
    id: 'intelligence',
    label: 'Message intelligence',
    description: 'Sentiment, complaint type, topic tags, safety and repeat detection.',
    flags: [
      'message_intelligence',
      'topic_tagging',
      'safety_escalation',
      'repeat_issue_detection',
    ],
  },
  {
    id: 'human',
    label: 'Human handover',
    description: 'When the bot should stop and get a person.',
    flags: ['handoff', 'human_handover'],
  },
]

export const FEATURE_LABELS: Record<FeatureFlag, { label: string; help: string }> = {
  cart: { label: 'Cart', help: 'Customers collect items before checking out.' },
  buy_now: { label: 'Buy now', help: 'One-tap purchase from a product page.' },
  orders: { label: 'Orders', help: 'Order records and order status.' },
  payments: { label: 'Payments', help: 'Collect online payments via Razorpay or Stripe checkout links.' },
  track_order: { label: 'Track order', help: 'Customers look up an order with a number.' },
  returns: { label: 'Returns', help: 'Return / refund requests and policy.' },
  brochure_pdf: { label: 'Brochure PDF', help: 'Send a downloadable brochure.' },
  distributors: { label: 'Distributors', help: 'A separate reseller price list.' },
  offerings: { label: 'Offerings', help: 'Browse what you sell or offer.' },
  offering_details: { label: 'Offering details', help: 'Price, specs and images per item.' },
  services: { label: 'Services', help: 'Browse the services you deliver.' },
  products: { label: 'Products', help: 'Browse the products you sell.' },
  products_schemes: { label: 'Products & Schemes', help: 'Browse the products and schemes you offer.' },
  lead_capture: { label: 'Lead capture', help: 'Collect name, phone and email.' },
  quote: { label: 'Quotes', help: 'Collect requirements and send a quote request.' },
  callback: { label: 'Callback', help: 'Offer to call the customer back.' },
  book_appointment: { label: 'Appointments', help: 'Book a slot with the team.' },
  handoff: { label: 'Handoff', help: 'Pause the bot and alert a human.' },
  faq: { label: 'FAQ', help: 'Answer from an uploaded FAQ file.' },
  kb: { label: 'Knowledge base', help: 'Answer from indexed documents.' },
  complaints: { label: 'Complaints', help: 'Register and track complaints.' },
  campaigns: { label: 'Campaigns', help: 'Scheduled broadcast messages.' },
  human_handover: { label: 'Human handover', help: 'Always allow a person to take over.' },
  message_intelligence: {
    label: 'Sentiment & type',
    help: 'UC-01/02: classify sentiment and complaint / question / praise / service request.',
  },
  topic_tagging: {
    label: 'Topic tagging',
    help: 'UC-03: tag component or topic (engine, battery, …) from the tenant taxonomy.',
  },
  safety_escalation: {
    label: 'Safety escalation',
    help: 'UC-04: detect safety issues and hand off to a human.',
  },
  repeat_issue_detection: {
    label: 'Repeat / surge detection',
    help: 'UC-05: flag repeated issues from the same customer or asset, and topic surges.',
  },
}

export const VERTICAL_CATALOG: VerticalMeta[] = [
  {
    id: 'ecommerce',
    label: 'E-commerce & retail',
    short: 'E-commerce',
    blurb: 'A shop: brochure, cart, checkout, orders and returns.',
    icon: 'ShoppingBag',
    content: {
      label: 'Products',
      singular: 'product',
      categories: ['Fashion', 'Electronics', 'Home', 'Beauty', 'Sports', 'Grocery'],
      extraFields: [
        { key: 'sku', label: 'SKU', placeholder: 'TG-1042' },
        { key: 'stock', label: 'In stock', placeholder: '42 units' },
        { key: 'warranty', label: 'Warranty', placeholder: '12 months' },
      ],
      priceLabel: 'Price',
    },
    industry: 'retail and e-commerce',
    listingType: 'products',
    domainQueries: 'products, prices, stock, delivery, returns, or payment',
    tone: 'friendly and helpful',
    nouns: {
      item: 'products',
      itemSingular: 'product',
      browse: 'Browse Products',
      catalog: 'View Brochure',
      lead: 'enquiry',
      leadAction: 'Enquire',
    },
    optionalModules: [
      { flag: 'products', label: 'Products Menu', description: 'Show the Products menu entry and answer questions about what you sell.', defaultOn: true },
      { flag: 'offerings', label: 'Browse products', description: 'Let customers browse your product catalogue on WhatsApp.', defaultOn: true },
      { flag: 'offering_details', label: 'Product details', description: 'Share price, specs and images for each product.', defaultOn: true },
      { flag: 'brochure_pdf', label: 'Brochure PDF', description: 'Offer downloadable brochure or catalog PDFs in chat.', defaultOn: true },
      { flag: 'cart', label: 'Cart', description: 'Allow customers to add multiple items to a cart before checkout.', defaultOn: true },
      { flag: 'buy_now', label: 'Buy now', description: 'One-tap purchase from a product card.', defaultOn: true },
      { flag: 'orders', label: 'Orders Management', description: 'Accept and process customer orders through WhatsApp.', defaultOn: true },
      { flag: 'payments', label: 'Online Payments', description: 'Generate Razorpay or Stripe checkout links for WhatsApp orders.', defaultOn: true },
      { flag: 'track_order', label: 'Order Tracking', description: 'Allow customers to look up order status and shipment AWB on WhatsApp.', defaultOn: true },
      { flag: 'returns', label: 'Returns', description: 'Accept return and refund requests from chat.', defaultOn: true },
      { flag: 'distributors', label: 'Distributors', description: 'Manage reseller/distributor network and wholesale pricing tiers.', defaultOn: true },
      { flag: 'lead_capture', label: 'Lead / Enquire', description: 'Collect name, phone and email from interested buyers.', defaultOn: true },
      { flag: 'quote', label: 'Request a Quote', description: 'Collect custom requirements and generate quote requests.', defaultOn: false },
      { flag: 'callback', label: 'Request a Callback', description: 'Allow users to request a phone callback from sales or support.', defaultOn: false },
      { flag: 'book_appointment', label: 'Book Appointments', description: 'Allow booking appointments and scheduled meetings.', defaultOn: false },
      { flag: 'complaints', label: 'Complaints & Support', description: 'Register customer grievances and track complaint tickets.', defaultOn: true },
      { flag: 'campaigns', label: 'Campaigns', description: 'Broadcast messages to customer segments from the console.', defaultOn: true },
    ],
    hiddenGroups: [],
    capabilities: [
      'Share your brochure on WhatsApp and answer product questions',
      'Take a cart through checkout and create an order',
      'Let customers track an order and raise a return',
      'Escalate to a human when the customer asks',
    ],
    questions: [
      {
        key: 'categories',
        label: 'Product categories',
        kind: 'chips',
        help: 'Becomes the menu sections and classifier keywords.',
        suggestions: ['Fashion', 'Electronics', 'Home', 'Beauty', 'Sports', 'Grocery'],
      },
      {
        key: 'payment_methods',
        label: 'Payment methods you accept',
        kind: 'chips',
        suggestions: ['UPI', 'Card', 'Net banking', 'Cash on delivery', 'Pay later'],
      },
      {
        key: 'delivery',
        label: 'Delivery & returns policy in one line',
        kind: 'text',
        placeholder: 'Free delivery above ₹999, 7-day returns',
      },
      {
        key: 'order_prefix',
        label: 'Order reference prefix',
        kind: 'text',
        placeholder: 'TG',
        help: 'Order numbers will look like TG-1042.',
      },
    ],
  },
  {
    id: 'it_software',
    label: 'Software & IT services',
    short: 'Software & IT',
    blurb: 'An engineering studio: services, tech stack, quotes and callbacks.',
    icon: 'Code2',
    content: {
      label: 'Services',
      singular: 'service',
      categories: [
        'Web development',
        'Mobile apps',
        'Cloud & DevOps',
        'UI/UX design',
        'Consulting',
        'Maintenance',
      ],
      extraFields: [
        { key: 'tech_stack', label: 'Tech stack', placeholder: 'React, Node.js, AWS' },
        { key: 'timeline', label: 'Typical timeline', placeholder: '8–10 weeks' },
        { key: 'engagement', label: 'Engagement model', placeholder: 'Fixed price' },
      ],
      priceLabel: 'Starting price',
    },
    industry: 'software and IT services',
    listingType: 'services or solutions',
    domainQueries: 'services, technologies, timelines, pricing, or support',
    tone: 'professional and confident',
    nouns: {
      item: 'services',
      itemSingular: 'service',
      browse: 'Our Services',
      catalog: 'Service Brochure',
      lead: 'enquiry',
      leadAction: 'Enquire',
    },
    optionalModules: [
      { flag: 'services', label: 'Services Menu', description: 'Show the Services menu entry and answer questions about what you deliver.', defaultOn: true },
      { flag: 'offerings', label: 'Browse services', description: 'Let customers explore your service catalogue on WhatsApp.', defaultOn: true },
      { flag: 'offering_details', label: 'Service details', description: 'Share scope, stack and pricing cues per service.', defaultOn: true },
      { flag: 'brochure_pdf', label: 'Service Brochure PDF', description: 'Offer a downloadable service brochure in chat.', defaultOn: true },
      { flag: 'lead_capture', label: 'Project enquiry', description: 'Collect project details and raise an enquiry to your team.', defaultOn: true },
      { flag: 'quote', label: 'Request a Quote', description: 'Collect requirements and generate quote requests.', defaultOn: true },
      { flag: 'callback', label: 'Request a Callback', description: 'Allow users to request a phone callback from sales or support.', defaultOn: true },
      { flag: 'book_appointment', label: 'Book Discovery Call', description: 'Allow booking a discovery or consultation call.', defaultOn: true },
      { flag: 'complaints', label: 'Complaints & Support', description: 'Register customer grievances and track complaint tickets.', defaultOn: true },
      { flag: 'campaigns', label: 'Campaigns', description: 'Broadcast messages to customer segments from the console.', defaultOn: false },
    ],
    hiddenGroups: ['commerce'],
    capabilities: [
      'Explain your services and technology stack in plain language',
      'Collect project requirements and raise a quote request',
      'Offer a callback or a discovery call instead of a live handoff',
      'Answer support questions from your documents',
    ],
    questions: [
      {
        key: 'tech_stack',
        label: 'Technologies you work with',
        kind: 'chips',
        help: 'These are the words your customers will use, and the bot will understand them.',
        suggestions: ['React', 'Node.js', 'Python', 'AWS', 'Azure', 'Mobile apps', 'DevOps', 'AI/ML'],
      },
      {
        key: 'engagements',
        label: 'How you work with clients',
        kind: 'select',
        options: [
          'Fixed-price projects',
          'Time and materials',
          'Retainers / support plans',
          'Mixed model',
        ],
      },
      {
        key: 'min_project',
        label: 'Typical engagement size',
        kind: 'text',
        placeholder: 'Projects from ₹2,00,000 · retainers from ₹25,000/month',
      },
      {
        key: 'after_sales',
        label: 'After-sales support',
        kind: 'textarea',
        placeholder: 'Free support window, AMC plans, SLA commitments…',
      },
    ],
  },
  {
    id: 'tours_travel',
    label: 'Tours & travel',
    short: 'Tours & travel',
    blurb: 'Packages and destinations: itineraries, availability and bookings.',
    icon: 'Plane',
    content: {
      label: 'Packages',
      singular: 'package',
      categories: [
        'Honeymoon',
        'Family',
        'Group',
        'Adventure',
        'Corporate',
        'Destination tours',
      ],
      extraFields: [
        { key: 'duration', label: 'Duration', placeholder: '5 nights / 6 days' },
        { key: 'destinations', label: 'Destinations', placeholder: 'Kerala, Munnar' },
        { key: 'includes', label: 'Includes', placeholder: 'Hotel, transfers, guide' },
      ],
      priceLabel: 'Package price',
    },
    industry: 'travel and tourism',
    listingType: 'packages, tours, or destinations',
    domainQueries: 'destinations, packages, dates, prices, or availability',
    tone: 'warm and helpful',
    nouns: {
      item: 'packages',
      itemSingular: 'package',
      browse: 'Explore Packages',
      catalog: 'Trip Brochure',
      lead: 'booking enquiry',
      leadAction: 'Enquire',
    },
    optionalModules: [
      { flag: 'offerings', label: 'Tour packages menu', description: 'Show Destinations and Packages so travellers can browse trips.', defaultOn: true },
      { flag: 'offering_details', label: 'Itinerary & inclusions', description: 'Share duration, inclusions and destination details per package.', defaultOn: true },
      { flag: 'brochure_pdf', label: 'Travel Brochure PDF', description: 'Offer downloadable travel brochure or itinerary PDFs in chat.', defaultOn: true },
      { flag: 'lead_capture', label: 'Trip enquiry', description: 'Collect traveller details and raise a booking enquiry.', defaultOn: true },
      { flag: 'quote', label: 'Custom trip quote', description: 'Collect custom itinerary requirements and generate quote requests.', defaultOn: true },
      { flag: 'callback', label: 'Request a Callback', description: 'Allow travellers to request a phone callback from your team.', defaultOn: true },
      { flag: 'book_appointment', label: 'Book consultation', description: 'Allow booking a travel consultation or planning call.', defaultOn: true },
      { flag: 'complaints', label: 'Complaints & Support', description: 'Register booking issues and track support tickets.', defaultOn: true },
      { flag: 'campaigns', label: 'Campaigns', description: 'Broadcast offers to traveller segments from the console.', defaultOn: true },
    ],
    hiddenGroups: ['commerce'],
    capabilities: [
      'Share packages, durations and destinations',
      'Answer itinerary and availability questions from your documents',
      'Collect traveller details and raise a booking enquiry',
      'Offer a callback outside working hours',
    ],
    questions: [
      {
        key: 'destinations',
        label: 'Destinations you sell',
        kind: 'chips',
        suggestions: ['Kerala', 'Goa', 'Kashmir', 'Rajasthan', 'Andaman', 'Dubai', 'Europe', 'Bali'],
      },
      {
        key: 'trip_types',
        label: 'Trip types',
        kind: 'chips',
        suggestions: ['Honeymoon', 'Family', 'Group', 'Solo', 'Corporate', 'Adventure'],
      },
      {
        key: 'booking_policy',
        label: 'Booking and cancellation policy',
        kind: 'textarea',
        placeholder: 'Advance booking, cancellation windows, payment terms…',
      },
      {
        key: 'season',
        label: 'Seasonality',
        kind: 'select',
        options: ['Year-round', 'Oct–Mar peak', 'Apr–Jun peak', 'Nov–Feb peak', 'Seasonal'],
      },
    ],
  },
  {
    id: 'banking',
    label: 'Banking & insurance',
    short: 'Banking',
    blurb: 'Accounts, cards and claims — answers only, never transactions.',
    icon: 'Landmark',
    content: {
      label: 'Products & schemes',
      singular: 'scheme',
      categories: ['Accounts', 'Cards', 'Loans', 'Insurance', 'Deposits'],
      extraFields: [
        { key: 'eligibility', label: 'Eligibility', placeholder: 'Salaried, 21–60 years' },
        { key: 'charges', label: 'Charges', placeholder: 'Zero annual fee' },
      ],
      priceLabel: 'Interest / fee',
    },
    industry: 'banking and insurance',
    listingType: 'products or schemes',
    domainQueries: 'accounts, cards, charges, claims, or eligibility',
    tone: 'formal and compliant',
    nouns: {
      item: 'schemes',
      itemSingular: 'scheme',
      browse: 'Our Products',
      catalog: 'Product Brochure',
      lead: 'enquiry',
      leadAction: 'Enquire',
    },
    optionalModules: [
      { flag: 'products_schemes', label: 'Products & Schemes', description: 'Show accounts, cards, loans and schemes in the WhatsApp menu.', defaultOn: true },
      { flag: 'offerings', label: 'Browse products', description: 'Let customers browse banking products and schemes.', defaultOn: true },
      { flag: 'offering_details', label: 'Product details', description: 'Share eligibility, charges and product specifics.', defaultOn: true },
      { flag: 'brochure_pdf', label: 'Product Brochure', description: 'Offer downloadable product brochure PDFs in chat.', defaultOn: false },
      { flag: 'lead_capture', label: 'Apply / Enquire', description: 'Collect details for product applications and enquiries.', defaultOn: true },
      { flag: 'quote', label: 'Check Eligibility', description: 'Collect details to check product eligibility.', defaultOn: false },
      { flag: 'callback', label: 'Request a Callback', description: 'Allow users to request a phone callback from the bank.', defaultOn: true },
      { flag: 'book_appointment', label: 'Book Appointments', description: 'Allow booking a branch or advisor appointment.', defaultOn: true },
      { flag: 'complaints', label: 'Complaints & Support', description: 'Register grievances and track complaint tickets.', defaultOn: true },
      { flag: 'campaigns', label: 'Campaigns', description: 'Broadcast messages to customer segments from the console.', defaultOn: true },
    ],
    hiddenGroups: ['commerce'],
    capabilities: [
      'Explain accounts, cards and schemes',
      'Answer charges and eligibility from your documents',
      'Register a complaint and route it to the right desk',
      'Hand off anything involving a customer’s money or identity',
    ],
    questions: [
      {
        key: 'products',
        label: 'Products on offer',
        kind: 'chips',
        suggestions: ['Savings account', 'Current account', 'Fixed deposit', 'Loans', 'Cards', 'Insurance'],
      },
      {
        key: 'regulated',
        label: 'Regulatory note',
        kind: 'textarea',
        placeholder: 'How the bot must phrase regulated information, and what it must never state.',
      },
    ],
  },
  {
    id: 'finance',
    label: 'Finance & accounting',
    short: 'Finance',
    blurb: 'Advisory, tax and compliance services, booked by appointment.',
    icon: 'Calculator',
    content: {
      label: 'Services',
      singular: 'service',
      categories: ['Tax filing', 'Audit', 'Registration', 'Payroll', 'Advisory'],
      extraFields: [
        { key: 'deadline', label: 'Next deadline', placeholder: 'ITR due 31 July' },
        { key: 'documents', label: 'Documents needed', placeholder: 'PAN, ITR, bank statement' },
      ],
      priceLabel: 'Fee',
    },
    industry: 'finance and accounting',
    listingType: 'services',
    domainQueries: 'fees, filings, deadlines, or compliance',
    tone: 'precise and professional',
    nouns: {
      item: 'services',
      itemSingular: 'service',
      browse: 'Our Services',
      catalog: 'Fee Schedule',
      lead: 'consultation',
      leadAction: 'Request a Callback',
    },
    optionalModules: [
      { flag: 'services', label: 'Services Menu', description: 'Show the Services menu entry for tax, audit and advisory work.', defaultOn: true },
      { flag: 'offerings', label: 'Browse services', description: 'Let clients explore your finance services on WhatsApp.', defaultOn: true },
      { flag: 'offering_details', label: 'Service details', description: 'Share fees, deadlines and documents needed per service.', defaultOn: true },
      { flag: 'brochure_pdf', label: 'Fee schedule / Brochure', description: 'Offer a downloadable fee schedule or services brochure.', defaultOn: true },
      { flag: 'lead_capture', label: 'Consultation enquiry', description: 'Collect client details and raise a consultation enquiry.', defaultOn: true },
      { flag: 'quote', label: 'Request a Proposal', description: 'Collect requirements and generate a proposal request.', defaultOn: true },
      { flag: 'callback', label: 'Book a Callback', description: 'Allow clients to request a phone callback.', defaultOn: true },
      { flag: 'book_appointment', label: 'Book consultation', description: 'Allow booking a consultation appointment.', defaultOn: true },
      { flag: 'complaints', label: 'Complaints & Support', description: 'Register client grievances and track tickets.', defaultOn: true },
      { flag: 'campaigns', label: 'Campaigns', description: 'Broadcast messages to client segments from the console.', defaultOn: true },
    ],
    hiddenGroups: ['commerce'],
    capabilities: [
      'Explain services, fees and compliance deadlines',
      'Book a consultation call',
      'Collect details and push them to your team',
      'Escalate anything that is advice, not information',
    ],
    questions: [
      {
        key: 'services',
        label: 'Services you offer',
        kind: 'chips',
        suggestions: ['ITR filing', 'GST', 'Audit', 'Company setup', 'Payroll', 'Advisory'],
      },
      {
        key: 'deadlines',
        label: 'Key deadlines the bot should mention',
        kind: 'text',
        placeholder: 'ITR due 31 July · GST monthly by the 20th',
      },
    ],
  },
  {
    id: 'healthcare',
    label: 'Healthcare & clinics',
    short: 'Healthcare',
    blurb: 'Departments, appointments and enquiries — no diagnosis.',
    icon: 'Stethoscope',
    content: {
      label: 'Departments',
      singular: 'department',
      categories: [
        'General medicine',
        'Dental',
        'Paediatrics',
        'Orthopaedics',
        'Dermatology',
        'Diagnostics',
      ],
      extraFields: [
        { key: 'timings', label: 'Timings', placeholder: 'Mon–Sat, 9:00–18:00' },
        { key: 'lead', label: 'Department head', placeholder: 'Dr. …' },
      ],
      priceLabel: 'Consultation fee',
    },
    industry: 'healthcare',
    listingType: 'departments or services',
    domainQueries: 'departments, timings, appointments, or fees',
    tone: 'calm and empathetic',
    nouns: {
      item: 'departments',
      itemSingular: 'department',
      browse: 'Our Departments',
      catalog: 'Services List',
      lead: 'appointment request',
      leadAction: 'Book Appointment',
    },
    optionalModules: [
      { flag: 'offerings', label: 'Departments menu', description: 'Show departments and treatments patients can browse.', defaultOn: true },
      { flag: 'offering_details', label: 'Specialities', description: 'Share department timings, leads and consultation details.', defaultOn: true },
      { flag: 'brochure_pdf', label: 'Services list PDF', description: 'Offer a downloadable services or departments PDF.', defaultOn: false },
      { flag: 'lead_capture', label: 'Patient enquiry', description: 'Collect patient details and raise an enquiry to reception.', defaultOn: true },
      { flag: 'quote', label: 'Cost estimate', description: 'Collect details for a treatment cost estimate.', defaultOn: false },
      { flag: 'callback', label: 'Request a Callback', description: 'Allow patients to request a phone callback.', defaultOn: true },
      { flag: 'book_appointment', label: 'Book Appointment', description: 'Allow booking appointments with the clinic.', defaultOn: true },
      { flag: 'complaints', label: 'Feedback / Complaints', description: 'Register feedback and grievances as tracked tickets.', defaultOn: true },
      { flag: 'campaigns', label: 'Campaigns', description: 'Broadcast messages to patient segments from the console.', defaultOn: false },
    ],
    hiddenGroups: ['commerce'],
    capabilities: [
      'Share departments, doctors and timings',
      'Collect an appointment request and push it to reception',
      'Answer fees and process questions from your documents',
      'Hand off anything clinical to a person immediately',
    ],
    questions: [
      {
        key: 'departments',
        label: 'Departments',
        kind: 'chips',
        suggestions: ['General medicine', 'Dental', 'Paediatrics', 'Orthopaedics', 'Dermatology', 'Diagnostics'],
      },
      {
        key: 'triage',
        label: 'Triage and escalation rule',
        kind: 'textarea',
        placeholder: 'The bot must never give a diagnosis; emergencies go straight to reception.',
        required: true,
      },
    ],
  },
  {
    id: 'real_estate',
    label: 'Real estate & property',
    short: 'Real Estate',
    blurb: 'Residences, commercial spaces, brochures, pricing plans and site visits.',
    icon: 'Building2',
    content: {
      label: 'Properties',
      singular: 'property',
      categories: [
        'Residential Apartments',
        'Luxury Villas',
        'Commercial Offices',
        'Retail Shops',
        'Plots & Land',
        'Penthouses',
      ],
      extraFields: [
        { key: 'bhk', label: 'Configuration', placeholder: '2 BHK / 3 BHK / 4 BHK' },
        { key: 'carpet_area', label: 'Carpet Area', placeholder: '1,250 sq.ft.' },
        { key: 'location', label: 'Location', placeholder: 'Prime Avenue, City Center' },
        { key: 'possession', label: 'Possession Date', placeholder: 'Ready to Move / Dec 2026' },
      ],
      priceLabel: 'Starting price',
    },
    industry: 'real estate & property development',
    listingType: 'properties or projects',
    domainQueries: 'properties, floor plans, pricing, possession dates, or site visits',
    tone: 'reassuring, consultative, and knowledgeable',
    nouns: {
      item: 'properties',
      itemSingular: 'property',
      browse: 'Featured Properties',
      catalog: 'Project Brochure',
      lead: 'site visit request',
      leadAction: 'Schedule Site Visit',
    },
    optionalModules: [
      { flag: 'offerings', label: 'Properties menu', description: 'Show residential and commercial listings customers can browse.', defaultOn: true },
      { flag: 'offering_details', label: 'Projects & specs', description: 'Share floor plans, amenities and project specifications.', defaultOn: true },
      { flag: 'brochure_pdf', label: 'Project Brochure PDF', description: 'Offer downloadable project brochures and floor plans.', defaultOn: true },
      { flag: 'lead_capture', label: 'Site-visit / enquiry', description: 'Collect buyer details and raise a site-visit enquiry.', defaultOn: true },
      { flag: 'quote', label: 'Price & payment plan', description: 'Collect details for pricing and payment-plan requests.', defaultOn: true },
      { flag: 'callback', label: 'Request a Callback', description: 'Allow buyers to request a callback from a property advisor.', defaultOn: true },
      { flag: 'book_appointment', label: 'Schedule Site Visit', description: 'Allow booking a guided site visit.', defaultOn: true },
      { flag: 'complaints', label: 'Customer Support', description: 'Register buyer support requests and track tickets.', defaultOn: true },
      { flag: 'campaigns', label: 'Campaigns', description: 'Broadcast offers to buyer segments from the console.', defaultOn: true },
    ],
    hiddenGroups: ['commerce'],
    capabilities: [
      'Showcase residential and commercial property listings',
      'Schedule on-site visits and consultation meetings',
      'Share floor plans, amenities, and project brochures',
      'Explain pricing, payment schemes, and home loan tie-ups',
      'Verify RERA registration and legal compliance details',
    ],
    questions: [
      {
        key: 'project_types',
        label: 'Property Types',
        kind: 'chips',
        suggestions: ['2 BHK Apartments', '3 BHK Luxury Flats', 'Villas', 'Commercial Offices', 'Plots'],
      },
      {
        key: 'rera',
        label: 'RERA Registration Details',
        kind: 'text',
        placeholder: 'RERA Registration No. PR/GJ/AHMEDABAD/...',
      },
    ],
  },
  {
    id: 'automotive',
    label: 'Automotive OEM & dealers',
    short: 'Automotive',
    blurb: 'Cars, brochure, test drive, on-road price, sales and customer care.',
    icon: 'Car',
    content: {
      label: 'Cars',
      singular: 'car',
      categories: ['Hatchback', 'Sedan', 'SUV', 'MUV', 'EV'],
      extraFields: [
        { key: 'fuel', label: 'Fuel', placeholder: 'Petrol / Diesel / Hybrid / EV' },
        { key: 'variant', label: 'Variant', placeholder: 'VX / ZX / Absolute' },
        { key: 'engine', label: 'Engine', placeholder: '1.5L i-VTEC' },
      ],
      priceLabel: 'Starting price',
    },
    industry: 'automotive OEM and dealer support',
    listingType: 'cars or models',
    domainQueries: 'vehicle models, test drive, on-road price, warranty, spare parts, or roadside help',
    tone: 'professional, calm, and safety-first',
    nouns: {
      item: 'cars',
      itemSingular: 'car',
      browse: 'Our Cars',
      catalog: 'Brochure',
      lead: 'sales enquiry',
      leadAction: 'Test Drive',
    },
    optionalModules: [
      { flag: 'offerings', label: 'Our Cars menu', description: 'Show models customers can browse on WhatsApp.', defaultOn: true },
      { flag: 'offering_details', label: 'Specs & variants', description: 'Share fuel, variant and engine details per model.', defaultOn: true },
      { flag: 'brochure_pdf', label: 'Model Brochure PDF', description: 'Offer downloadable model brochures in chat.', defaultOn: true },
      { flag: 'lead_capture', label: 'Sales enquiry', description: 'Collect buyer details and raise a sales enquiry.', defaultOn: true },
      { flag: 'quote', label: 'On-Road Price', description: 'Collect city and model details for an on-road price quote.', defaultOn: true },
      { flag: 'callback', label: 'Test Drive / Callback', description: 'Allow customers to request a test drive or sales callback.', defaultOn: true },
      { flag: 'book_appointment', label: 'Book Appointments', description: 'Allow booking showroom visits or service appointments.', defaultOn: true },
      { flag: 'complaints', label: 'Customer Care', description: 'Register service and sales complaints as tracked tickets.', defaultOn: true },
      { flag: 'campaigns', label: 'Campaigns', description: 'Broadcast offers to customer segments from the console.', defaultOn: true },
      { flag: 'message_intelligence', label: 'Message intelligence', description: 'Classify sentiment and message type (complaint, question, praise).', defaultOn: true },
      { flag: 'topic_tagging', label: 'Component / topic tags', description: 'Tag vehicle components and topics from each message.', defaultOn: true },
      { flag: 'safety_escalation', label: 'Safety escalation', description: 'Detect safety issues and hand off to a human immediately.', defaultOn: true },
      { flag: 'repeat_issue_detection', label: 'Repeat issue detection', description: 'Flag repeated issues and topic surges across customers.', defaultOn: true },
    ],
    hiddenGroups: ['commerce'],
    capabilities: [
      'Classify sentiment and complaint vs question vs praise',
      'Tag vehicle components (engine, battery, brakes, …)',
      'Escalate safety cases (brake failure, fire, steering) to a human',
      'Detect repeat complaints and topic surges across customers',
    ],
    // Models come from Offerings / brochure uploads; safety handoff is AI-driven
    // from the customer message + intelligence defaults (no manual rule text).
    questions: [],
  },
  {
    id: 'generic',
    label: 'Something else',
    short: 'Generic',
    blurb: 'Start from scratch: brochure, enquiries and support only.',
    icon: 'Building2',
    content: {
      label: 'Offerings',
      singular: 'item',
      categories: ['Products', 'Services', 'Courses', 'Memberships', 'Subscriptions'],
      extraFields: [
        { key: 'availability', label: 'Availability', placeholder: 'In stock / On request' },
        { key: 'lead_time', label: 'Lead time', placeholder: '2–3 working days' },
      ],
      priceLabel: 'Price',
    },
    industry: 'business',
    listingType: 'products, services, or information',
    domainQueries: 'products, services, pricing, or support',
    tone: 'helpful',
    nouns: {
      item: 'products',
      itemSingular: 'product',
      browse: 'Browse',
      catalog: 'Brochure',
      lead: 'enquiry',
      leadAction: 'Enquire',
    },
    optionalModules: [
      { flag: 'offerings', label: 'Browse offerings', description: 'Let customers browse what you sell or offer.', defaultOn: true },
      { flag: 'offering_details', label: 'Item details', description: 'Share details and images for each offering.', defaultOn: true },
      { flag: 'brochure_pdf', label: 'Brochure PDF', description: 'Offer downloadable brochure PDFs in chat.', defaultOn: false },
      { flag: 'lead_capture', label: 'Enquire', description: 'Collect name, phone and email from interested customers.', defaultOn: true },
      { flag: 'quote', label: 'Request a Quote', description: 'Collect custom requirements and generate quote requests.', defaultOn: false },
      { flag: 'callback', label: 'Request a Callback', description: 'Allow users to request a phone callback.', defaultOn: true },
      { flag: 'book_appointment', label: 'Book Appointments', description: 'Allow booking appointments and scheduled meetings.', defaultOn: false },
      { flag: 'complaints', label: 'Complaints', description: 'Register customer grievances and track tickets.', defaultOn: true },
      { flag: 'campaigns', label: 'Campaigns', description: 'Broadcast messages to customer segments from the console.', defaultOn: false },
    ],
    hiddenGroups: ['commerce'],
    capabilities: [
      'Answer questions from your FAQ and documents',
      'Share what you offer',
      'Collect enquiries and pass them on',
      'Hand off to a person on request',
    ],
    questions: [
      {
        key: 'offerings',
        label: 'What do you sell or offer?',
        kind: 'chips',
        suggestions: ['Products', 'Services', 'Courses', 'Memberships', 'Subscriptions'],
      },
    ],
  },
]

export const VERTICAL_MAP: Record<string, VerticalMeta> = Object.fromEntries(
  VERTICAL_CATALOG.map((v) => [v.id, v]),
)

export function getVertical(id: string | null | undefined): VerticalMeta {
  return VERTICAL_MAP[id ?? ''] ?? VERTICAL_MAP.generic
}
