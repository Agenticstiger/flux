// =====================================================================
// FLUX — VuePress 2 client config
// =====================================================================
// Globally registers <MermaidLazy> so diagram pages can embed it without
// per-page imports. MermaidLazy is async-loaded so it only downloads on the
// pages that use it. Overrides the theme's default 404 with the branded
// NotFound layout, and wraps the theme's Layout to add a skip link.
// =====================================================================

import { defineClientConfig } from 'vuepress/client'
import { defineAsyncComponent } from 'vue'
import Layout from './layouts/Layout.vue'
import NotFound from './layouts/NotFound.vue'

const MermaidLazy = defineAsyncComponent(
  () => import('./components/MermaidLazy.vue'),
)

export default defineClientConfig({
  enhance({ app }) {
    app.component('MermaidLazy', MermaidLazy)
  },
  layouts: {
    Layout,
    NotFound,
  },
})
