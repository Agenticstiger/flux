<!--
  FLUX layout: the default theme's Layout plus a "Skip to content" link.

  The link is the first focusable element on every page and is visible only
  while it has focus. The theme's `page` slot is used to give the page's
  <main> element an id and tabindex="-1", which is what the link points at and
  what receives focus. The slot body repeats the theme's own `page` default
  (home or page, inside the same transition), nothing more.
-->
<script setup lang="ts">
import ParentLayout from '@vuepress/theme-default/layouts/Layout.vue'
import { useData } from '@theme/useData'
import { useScrollPromise } from '@theme/useScrollPromise'
import VPFadeSlideYTransition from '@theme/VPFadeSlideYTransition.vue'
import VPHome from '@theme/VPHome.vue'
import VPPage from '@theme/VPPage.vue'

const MAIN_ID = 'main-content'

const { frontmatter, page } = useData()

// Same scroll handling as the theme's default `page` slot.
const scrollPromise = useScrollPromise()
const onBeforeEnter = scrollPromise.resolve
const onBeforeLeave = scrollPromise.pending

// Move focus to <main> and scroll it into view. Without script the link still
// works as a plain in-page anchor.
const skipToContent = (): void => {
  const main = document.getElementById(MAIN_ID)
  if (!main) return
  main.focus()
  main.scrollIntoView()
}
</script>

<template>
  <a class="ff-skip-link" :href="`#${MAIN_ID}`" @click.prevent="skipToContent">Skip to content</a>

  <ParentLayout>
    <template #page>
      <VPFadeSlideYTransition @before-enter="onBeforeEnter" @before-leave="onBeforeLeave">
        <VPHome v-if="frontmatter.home" :id="MAIN_ID" tabindex="-1" />
        <VPPage v-else :id="MAIN_ID" tabindex="-1" :key="page.path" />
      </VPFadeSlideYTransition>
    </template>
  </ParentLayout>
</template>
