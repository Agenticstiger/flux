// =====================================================================
// FLUX — VuePress 2 client config
// =====================================================================
// Globally registers <MermaidLazy> so diagram pages can embed it without
// per-page imports, and overrides the theme's default 404 with the
// branded NotFound layout. MermaidLazy is async-loaded so it only
// downloads on the pages that use it.
// =====================================================================

import { defineClientConfig } from 'vuepress/client'
import { defineAsyncComponent } from 'vue'
import NotFound from './layouts/NotFound.vue'

const MermaidLazy = defineAsyncComponent(
  () => import('./components/MermaidLazy.vue'),
)

export default defineClientConfig({
  enhance({ app }) {
    app.component('MermaidLazy', MermaidLazy)
  },
  layouts: {
    NotFound,
  },
})
