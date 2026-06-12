<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useData } from 'vitepress'

type Locale = 'zh' | 'en' | 'ja'
type PreviewImage = {
  alt: string
  scrollable: boolean
  src: string
  title: string
}

const { lang } = useData()
const locale = computed<Locale>(() => {
  if (lang.value.startsWith('en')) return 'en'
  if (lang.value.startsWith('ja')) return 'ja'
  return 'zh'
})

const imageSlots = {
  home: 'https://img.qunq.de/file/1781290757509_home-2.png',
  homeMobile: 'https://img.qunq.de/file/1781287851954_home.png',
  browser: 'https://img.qunq.de/file/1781287849957_browser.png',
  favorites: 'https://img.qunq.de/file/1781287855095_favorites.png',
  detail: 'https://img.qunq.de/file/1781287855252_detail.png',
  settings: 'https://img.qunq.de/file/1781287856067_settings.png'
}

const copy = {
  zh: {
    eyebrow: 'MediaTree',
    title: '私人媒体库，清晰上手。',
    titleLines: ['私人媒体库，', '清晰上手。'],
    subtitle: '从部署到播放，一切更直观。让散落的本地影片，变成属于你的媒体空间。',
    subtitleLines: ['从部署到播放，一切更直观。', '让散落的本地影片，成为你的媒体空间。'],
    primary: '开始使用',
    secondary: '在 GitHub 查看',
    heroAlt: 'MediaTree 首页截图',
    heroHint: '首页展示位',
    heroHintSub: '替换 imageSlots.home 为图床 URL',
    stats: [
      ['轻松部署', 'Docker 即刻启动'],
      ['自动整理', '海报与信息自然呈现'],
      ['灵活更新', '升级与回滚清晰可控']
    ],
    sections: [
      {
        label: '浏览页',
        title: '一眼看见你的所有影片。',
        text: '海报、标题与分类自然铺开。想看的内容，更快出现。',
        link: '/guide/scrapers',
        linkText: '了解媒体整理',
        imageKey: 'browser',
        imageAlt: '浏览页截图',
        hint: '浏览页截图位'
      },
      {
        label: '收藏页',
        title: '喜欢的内容，始终触手可及。',
        text: '把常看的影片收在一起。下一次播放，只需一次点击。',
        link: '/guide/faq',
        linkText: '查看使用提示',
        imageKey: 'favorites',
        imageAlt: '收藏页截图',
        hint: '收藏页截图位'
      },
      {
        label: '播放页',
        title: '画面、字幕、外部播放，自然衔接。',
        text: '在网页中沉浸播放，也能交给 IINA、mpv 或 VLC。每一种观看方式，都顺手。',
        link: '/guide/external-clients',
        linkText: '了解播放方式',
        imageKey: 'detail',
        imageAlt: '播放页截图',
        hint: '播放页截图位'
      },
      {
        label: '设置页',
        title: '设置清晰，维护更轻松。',
        text: '媒体库、刮削器、更新与备份放在一处。日常管理，更从容。',
        link: '/guide/configuration',
        linkText: '查看配置',
        imageKey: 'settings',
        imageAlt: '设置页截图',
        hint: '设置页截图位'
      }
    ],
    featuresTitle: '从第一次部署，到长期使用。',
    featuresText: '关键步骤被整理成清晰路径。少一些摸索，多一些掌控。',
    features: [
      ['安装', '准备环境，启动服务，打开你的媒体库。'],
      ['整理', '自动补全信息，让文件夹变得清晰好看。'],
      ['播放', '网页播放与外部播放器，各有各的顺手。'],
      ['维护', '更新、备份、回滚，都有明确路径。']
    ],
    ctaTitle: '现在，开始整理你的媒体库。',
    ctaText: '跟随快速开始，几步完成部署。',
    ctaButton: '开始'
  },
  en: {
    eyebrow: 'MediaTree',
    title: 'Your media library, made clear.',
    titleLines: ['Your media library,', 'made clear.'],
    subtitle: 'From setup to playback, everything feels clearer. Turn scattered local videos into a space of your own.',
    subtitleLines: ['From setup to playback, everything feels clearer.', 'Turn scattered local videos into a space of your own.'],
    primary: 'Get started',
    secondary: 'View on GitHub',
    heroAlt: 'MediaTree home screenshot',
    heroHint: 'Home page image slot',
    heroHintSub: 'Replace imageSlots.home with an image URL',
    stats: [
      ['Easy setup', 'Start with Docker'],
      ['Smart organization', 'Posters and details appear naturally'],
      ['Clear updates', 'Upgrade and roll back with confidence']
    ],
    sections: [
      {
        label: 'Browse Page',
        title: 'See your whole library at a glance.',
        text: 'Posters, titles, and categories fall into place. What you want to watch is easier to find.',
        link: '/en/guide/scrapers',
        linkText: 'Explore organization',
        imageKey: 'browser',
        imageAlt: 'Browse page screenshot',
        hint: 'Browse page screenshot slot'
      },
      {
        label: 'Favorites Page',
        title: 'Keep your favorites close.',
        text: 'Collect the titles you return to most. Next time, they are right where you expect them.',
        link: '/en/guide/faq',
        linkText: 'View tips',
        imageKey: 'favorites',
        imageAlt: 'Favorites page screenshot',
        hint: 'Favorites page screenshot slot'
      },
      {
        label: 'Player Page',
        title: 'Playback, subtitles, and handoff. All in flow.',
        text: 'Watch in the browser, or hand off to IINA, mpv, or VLC. Every way to play stays within reach.',
        link: '/en/guide/external-clients',
        linkText: 'Explore playback',
        imageKey: 'detail',
        imageAlt: 'Player page screenshot',
        hint: 'Player page screenshot slot'
      },
      {
        label: 'Settings Page',
        title: 'Settings that stay understandable.',
        text: 'Libraries, scrapers, updates, and backups live together. Everyday maintenance feels simple.',
        link: '/en/guide/configuration',
        linkText: 'View settings',
        imageKey: 'settings',
        imageAlt: 'Settings page screenshot',
        hint: 'Settings page screenshot slot'
      }
    ],
    featuresTitle: 'From first launch to everyday use.',
    featuresText: 'The essentials are arranged as clear paths, so you spend less time figuring things out.',
    features: [
      ['Install', 'Prepare the environment, start the service, open your library.'],
      ['Organize', 'Bring posters and details to your folders, automatically.'],
      ['Play', 'Use the web player or hand off to the player you prefer.'],
      ['Maintain', 'Update, back up, and roll back with a clear path.']
    ],
    ctaTitle: 'Start building your library.',
    ctaText: 'Follow the quick start and get MediaTree running in a few steps.',
    ctaButton: 'Start'
  },
  ja: {
    eyebrow: 'MediaTree',
    title: 'プライベートメディアライブラリを、見やすく始める。',
    titleLines: ['プライベートメディアライブラリを、', '見やすく始める。'],
    subtitle: 'セットアップから再生まで、もっと直感的に。散らばったローカル動画を、自分だけの空間へ。',
    subtitleLines: ['セットアップから再生まで、もっと直感的に。', '散らばったローカル動画を、自分だけの空間へ。'],
    primary: '始める',
    secondary: 'GitHub を見る',
    heroAlt: 'MediaTree ホーム画面スクリーンショット',
    heroHint: 'ホーム画面の展示枠',
    heroHintSub: 'imageSlots.home を画像 URL に置き換え',
    stats: [
      ['かんたん導入', 'Docker ですぐに起動'],
      ['自動整理', 'ポスターと情報を自然に表示'],
      ['明快な更新', 'アップグレードも復元もわかりやすく']
    ],
    sections: [
      {
        label: 'ブラウズページ',
        title: 'ライブラリ全体を、ひと目で。',
        text: 'ポスター、タイトル、カテゴリが自然に並びます。見たい作品へ、よりすばやく。',
        link: '/ja/guide/scrapers',
        linkText: '整理方法を見る',
        imageKey: 'browser',
        imageAlt: 'ブラウズページのスクリーンショット',
        hint: 'ブラウズページのスクリーンショット枠'
      },
      {
        label: 'お気に入りページ',
        title: '好きな作品を、いつもの場所に。',
        text: 'よく見る作品をまとめておけば、次に見るときもすぐに戻れます。',
        link: '/ja/guide/faq',
        linkText: '使い方を見る',
        imageKey: 'favorites',
        imageAlt: 'お気に入りページのスクリーンショット',
        hint: 'お気に入りページのスクリーンショット枠'
      },
      {
        label: '再生ページ',
        title: '再生、字幕、外部プレイヤー。流れるように。',
        text: 'ブラウザで観る。IINA、mpv、VLC に渡す。どの見方も、すぐ手の届く場所に。',
        link: '/ja/guide/external-clients',
        linkText: '再生を見る',
        imageKey: 'detail',
        imageAlt: '再生ページのスクリーンショット',
        hint: '再生ページのスクリーンショット枠'
      },
      {
        label: '設定ページ',
        title: '設定はわかりやすく。管理は軽やかに。',
        text: 'ライブラリ、スクレイパー、更新、バックアップを一か所に。日々の管理がシンプルになります。',
        link: '/ja/guide/configuration',
        linkText: '設定を見る',
        imageKey: 'settings',
        imageAlt: '設定ページのスクリーンショット',
        hint: '設定ページのスクリーンショット枠'
      }
    ],
    featuresTitle: '初回起動から、毎日の利用まで。',
    featuresText: '大切な手順を、わかりやすい流れに。迷う時間を減らし、使う時間を増やします。',
    features: [
      ['導入', '環境を整え、サービスを起動し、ライブラリを開く。'],
      ['整理', 'フォルダにポスターと情報を添えて、見やすく。'],
      ['再生', 'Web でも、好みのプレイヤーでも。'],
      ['保守', '更新、バックアップ、復元まで、道筋は明確に。']
    ],
    ctaTitle: 'あなたのライブラリを、始めよう。',
    ctaText: 'クイックスタートに沿って、数ステップで起動できます。',
    ctaButton: '始める'
  }
}

const t = computed(() => copy[locale.value])
const activePreview = ref<PreviewImage | null>(null)
const docsBase = '/mediatree'
const installPath = computed(() => {
  if (locale.value === 'en') return '/mediatree/en/guide/installation'
  if (locale.value === 'ja') return '/mediatree/ja/guide/installation'
  return '/mediatree/guide/installation'
})

function withBase(path: string) {
  if (path.startsWith('http')) return path
  return `${docsBase}${path}`
}

function imageFor(key: string) {
  return imageSlots[key as keyof typeof imageSlots]
}

function isScrollableImage(key: string) {
  return key === 'detail'
}

function openPreview(imageKey: string, alt: string, title: string) {
  const src = imageFor(imageKey)
  if (!src) return
  activePreview.value = {
    alt,
    scrollable: isScrollableImage(imageKey),
    src,
    title
  }
}

function closePreview() {
  activePreview.value = null
}

function handlePreviewKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') closePreview()
}

onMounted(() => {
  window.addEventListener('keydown', handlePreviewKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handlePreviewKeydown)
  document.documentElement.classList.remove('mt-preview-open')
})

watch(activePreview, (preview) => {
  document.documentElement.classList.toggle('mt-preview-open', Boolean(preview))
})
</script>

<template>
  <main class="mt-home" :class="`mt-locale-${locale}`">
    <section class="mt-hero" :style="{ '--mt-hero-image': `url(${imageSlots.home})` }">
      <div class="mt-hero-bg mt-hero-bg-a"></div>
      <div class="mt-hero-bg mt-hero-bg-b"></div>
      <div class="mt-hero-visual" aria-hidden="true"></div>
      <div class="mt-shell mt-hero-grid">
        <div class="mt-hero-copy">
          <p class="mt-eyebrow">{{ t.eyebrow }}</p>
          <h1>
            <span v-for="line in t.titleLines" :key="line">{{ line }}</span>
          </h1>
          <p class="mt-lede">
            <span v-for="line in t.subtitleLines" :key="line">{{ line }}</span>
          </p>
          <div class="mt-actions">
            <a class="mt-button mt-button-primary" :href="installPath">
              {{ t.primary }}
            </a>
            <a class="mt-button mt-button-secondary" href="https://github.com/ZASENJC/mediatree">
              {{ t.secondary }}
            </a>
          </div>
          <figure class="mt-hero-mobile-screen mt-screen-static">
            <div
              class="mt-screen-trigger"
              role="button"
              tabindex="0"
              :aria-label="t.heroAlt"
              @click="openPreview('homeMobile', t.heroAlt, t.eyebrow)"
              @keydown.enter.prevent="openPreview('homeMobile', t.heroAlt, t.eyebrow)"
              @keydown.space.prevent="openPreview('homeMobile', t.heroAlt, t.eyebrow)"
            >
              <div class="mt-mac-bar" aria-hidden="true">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <div class="mt-screen-scroll">
                <img :src="imageSlots.homeMobile" :alt="t.heroAlt" />
              </div>
            </div>
          </figure>
          <div class="mt-stats">
            <div v-for="item in t.stats" :key="item[0]">
              <strong>{{ item[0] }}</strong>
              <span>{{ item[1] }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="mt-sections">
      <article
        v-for="(section, index) in t.sections"
        :key="section.title"
        class="mt-feature-row"
        :class="{ 'mt-feature-row-reverse': index % 2 === 1 }"
      >
        <div class="mt-feature-copy">
          <span>{{ section.label }}</span>
          <h2>{{ section.title }}</h2>
          <p>{{ section.text }}</p>
          <a :href="withBase(section.link)">{{ section.linkText }} →</a>
        </div>
        <figure
          class="mt-screen"
          :class="{
            'mt-screen-scrollable': isScrollableImage(section.imageKey),
            'mt-screen-static': !isScrollableImage(section.imageKey)
          }"
        >
          <div
            v-if="imageFor(section.imageKey)"
            class="mt-screen-trigger"
            role="button"
            tabindex="0"
            :aria-label="section.imageAlt"
            @click="openPreview(section.imageKey, section.imageAlt, section.label)"
            @keydown.enter.prevent="openPreview(section.imageKey, section.imageAlt, section.label)"
            @keydown.space.prevent="openPreview(section.imageKey, section.imageAlt, section.label)"
          >
            <div class="mt-mac-bar" aria-hidden="true">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <div class="mt-screen-scroll">
              <img :src="imageFor(section.imageKey)" :alt="section.imageAlt" />
            </div>
          </div>
          <div v-else class="mt-image-placeholder">
            <div class="mt-mac-bar" aria-hidden="true">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <span>{{ section.hint }}</span>
            <small>imageSlots.{{ section.imageKey }}</small>
          </div>
        </figure>
      </article>
    </section>

    <section class="mt-feature-grid-section">
      <div class="mt-shell">
        <div class="mt-section-heading">
          <h2>{{ t.featuresTitle }}</h2>
          <p>{{ t.featuresText }}</p>
        </div>
        <div class="mt-feature-grid">
          <article v-for="feature in t.features" :key="feature[0]">
            <div class="mt-feature-dot"></div>
            <h3>{{ feature[0] }}</h3>
            <p>{{ feature[1] }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="mt-cta">
      <div class="mt-shell mt-cta-card">
        <h2>{{ t.ctaTitle }}</h2>
        <p>{{ t.ctaText }}</p>
        <a class="mt-button mt-button-primary" :href="installPath">
          {{ t.ctaButton }}
        </a>
      </div>
    </section>

    <div
      v-if="activePreview"
      class="mt-preview"
      role="dialog"
      aria-modal="true"
      :aria-label="activePreview.title"
      @click.self="closePreview"
    >
      <div
        class="mt-preview-window"
        :class="{ 'mt-preview-window-scrollable': activePreview.scrollable }"
      >
        <div class="mt-mac-bar mt-preview-bar" aria-hidden="true">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <button class="mt-preview-close" type="button" aria-label="Close preview" @click="closePreview">
          <span aria-hidden="true"></span>
        </button>
        <div class="mt-preview-body">
          <img :src="activePreview.src" :alt="activePreview.alt" />
        </div>
      </div>
    </div>
  </main>
</template>
