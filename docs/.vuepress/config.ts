import { defineUserConfig } from 'vuepress'
import { defaultTheme } from '@vuepress/theme-default'
import { viteBundler } from '@vuepress/bundler-vite'
import { searchPlugin } from '@vuepress/plugin-search'
import { sitemapPlugin } from '@vuepress/plugin-sitemap'
import { markdownChartPlugin } from '@vuepress/plugin-markdown-chart'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const SITE = 'https://agenticstiger.github.io/flux/'

export default defineUserConfig({
  lang: 'en-US',
  title: 'FLUX',
  description: 'The open, declarative standard for governed synthetic customer universes — the discovery-side sibling of FLUID.',

  // LOCKED: matches the GitHub Pages project path. Every published schema
  // `$id` (https://agenticstiger.github.io/flux/schema/...) depends on this
  // base — do not change without rewriting the schema $id URLs.
  base: '/flux/',

  clientConfigFile: resolve(__dirname, './client.ts'),
  bundler: viteBundler(),

  shouldPrefetch: false,
  shouldPreload: false,

  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/flux/favicon.svg' }],
    ['meta', { name: 'theme-color', content: '#050813' }],

    ['meta', { property: 'og:title', content: 'FLUX — Governed Synthetic Universes, Declared' }],
    ['meta', { property: 'og:description', content: 'Declare the universe. Prove the rule. Ship the FLUID contract that was proven.' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:url', content: SITE }],
    ['meta', { property: 'og:site_name', content: 'FLUX' }],

    ['meta', { name: 'keywords', content: 'flux, fluid, digital twin, synthetic data, simulation, data products, data contract, deterministic, governance, json schema' }],
  ],

  theme: defaultTheme({
    colorMode: 'dark',
    colorModeSwitch: true,
    logo: '/logo-mark.svg',

    navbar: [
      {
        text: 'Guide',
        children: [
          { text: 'Introduction', link: '/guide/' },
          { text: 'Quickstart', link: '/guide/quickstart' },
        ],
      },
      {
        text: 'Concepts',
        children: [
          { text: 'Two Specs, One Substrate', link: '/concepts/' },
          { text: 'The Six Families', link: '/concepts/families' },
          { text: 'The FLUID Seam', link: '/concepts/seam' },
          { text: 'Deterministic & Governed', link: '/concepts/determinism-governance' },
          { text: 'Runtime & Evidence', link: '/concepts/runtime' },
        ],
      },
      {
        text: 'Schema',
        children: [
          { text: 'Anatomy', link: '/schema/anatomy' },
          { text: 'The Nineteen Kinds', link: '/schema/kinds' },
          { text: 'Versions', link: '/schema/versions' },
          { text: 'Changelog', link: '/schema/changelog' },
          { text: 'JSON Schema 0.5.0 ↗', link: 'https://agenticstiger.github.io/flux/schema/flux-schema-0.5.0.json', target: '_blank' },
          { text: 'UI Hints 0.5.0 ↗', link: 'https://agenticstiger.github.io/flux/schema/flux-ui-hints-0.5.0.json', target: '_blank' },
          { text: 'Enforcement Contract 0.5.0 ↗', link: 'https://agenticstiger.github.io/flux/schema/flux-enforcement-0.5.0.json', target: '_blank' },
          { text: 'Bundle Manifest 0.5.0 ↗', link: 'https://agenticstiger.github.io/flux/schema/flux-manifest-0.5.0.json', target: '_blank' },
        ],
      },
      {
        text: 'Roadmap',
        children: [
          { text: 'The vNext Plan', link: '/roadmap/' },
          { text: 'The Nine RFCs', link: '/roadmap/rfcs' },
          { text: 'Conformance Profiles', link: '/roadmap/profiles' },
        ],
      },
      { text: 'Examples', link: '/examples/' },
      { text: "What's New", link: '/releases/' },
      { text: 'FLUID ↗', link: 'https://open-data-protocol.github.io/fluid/' },
      { text: 'GitHub', link: 'https://github.com/Agenticstiger/flux' },
    ],

    sidebar: {
      '/guide/': [
        {
          text: 'Guide',
          children: ['/guide/README.md', '/guide/quickstart.md'],
        },
      ],
      '/concepts/': [
        {
          text: 'Concepts',
          children: [
            '/concepts/README.md',
            '/concepts/families.md',
            '/concepts/seam.md',
            '/concepts/determinism-governance.md',
            '/concepts/runtime.md',
          ],
        },
      ],
      '/schema/': [
        {
          text: 'Schema Reference',
          children: [
            '/schema/README.md',
            '/schema/anatomy.md',
            '/schema/kinds.md',
            '/schema/versions.md',
            '/schema/changelog.md',
          ],
        },
      ],
      '/roadmap/': [
        {
          text: 'Roadmap',
          children: ['/roadmap/README.md', '/roadmap/rfcs.md', '/roadmap/profiles.md'],
        },
      ],
      '/examples/': [
        {
          text: 'Examples',
          children: ['/examples/README.md'],
        },
      ],
      '/releases/': [
        {
          text: "What's New",
          children: ['/releases/README.md', '/releases/0.5.0.md', '/releases/0.4.1.md', '/releases/0.4.0.md', '/releases/0.3.0.md'],
        },
      ],
      '/contributing/': [
        {
          text: 'Project',
          children: ['/contributing/README.md'],
        },
      ],
    },

    repo: 'Agenticstiger/flux',
    docsRepo: 'Agenticstiger/flux',
    docsDir: 'docs',
    docsBranch: 'main',
    editLink: true,
    editLinkText: 'Edit this page on GitHub',
    lastUpdated: true,
    contributors: false,
  }),

  plugins: [
    searchPlugin({
      maxSuggestions: 12,
      hotKeys: ['s', '/'],
    }),
    sitemapPlugin({
      hostname: SITE,
    }),
    markdownChartPlugin({ mermaid: true }),
  ],
})
