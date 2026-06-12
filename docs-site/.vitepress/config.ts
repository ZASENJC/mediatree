import { defineConfig } from 'vitepress'

const zhGuide = [
  { text: '快速开始', link: '/guide/installation' },
  { text: '配置说明', link: '/guide/configuration' },
  { text: '刮削器系统', link: '/guide/scrapers' },
  { text: '外部客户端', link: '/guide/external-clients' },
  { text: '升级与回滚', link: '/guide/updates' },
  { text: '常见问题', link: '/guide/faq' }
]

const zhReference = [
  { text: 'API Reference', link: '/reference/api' }
]

const zhDevelopment = [
  { text: '开发指南', link: '/development/' },
  { text: '发布规则', link: '/development/release-policy' }
]

const enGuide = [
  { text: 'Quick Start', link: '/en/guide/installation' },
  { text: 'Configuration', link: '/en/guide/configuration' },
  { text: 'Scrapers', link: '/en/guide/scrapers' },
  { text: 'External Clients', link: '/en/guide/external-clients' },
  { text: 'Updates & Rollback', link: '/en/guide/updates' },
  { text: 'FAQ', link: '/en/guide/faq' }
]

const enReference = [
  { text: 'API Reference', link: '/en/reference/api' }
]

const enDevelopment = [
  { text: 'Development Guide', link: '/en/development/' },
  { text: 'Release Policy', link: '/en/development/release-policy' }
]

export default defineConfig({
  base: '/mediatree/',
  cleanUrls: true,
  lastUpdated: true,
  head: [
    ['link', { rel: 'icon', href: '/mediatree/logo.png' }],
    ['meta', { name: 'theme-color', content: '#111827' }]
  ],
  themeConfig: {
    logo: '/logo.png',
    search: {
      provider: 'local'
    },
    socialLinks: [
      { icon: 'github', link: 'https://github.com/ZASENJC/mediatree' }
    ]
  },
  locales: {
    root: {
      label: '简体中文',
      lang: 'zh-CN',
      title: 'MediaTree 文档',
      description: 'MediaTree 部署、配置、刮削、播放、升级和开发文档。',
      themeConfig: {
        nav: [
          { text: '用户指南', link: '/guide/installation' },
          { text: 'API', link: '/reference/api' },
          { text: '开发', link: '/development/' },
          { text: 'Release', link: 'https://github.com/ZASENJC/mediatree/releases' }
        ],
        sidebar: {
          '/guide/': [
            {
              text: '用户指南',
              items: zhGuide
            }
          ],
          '/reference/': [
            {
              text: '参考',
              items: zhReference
            }
          ],
          '/development/': [
            {
              text: '开发者',
              items: zhDevelopment
            }
          ]
        },
        docFooter: {
          prev: '上一页',
          next: '下一页'
        },
        outline: {
          label: '本页目录'
        },
        darkModeSwitchLabel: '外观',
        sidebarMenuLabel: '菜单',
        returnToTopLabel: '回到顶部',
        langMenuLabel: '语言',
        lastUpdated: {
          text: '最后更新'
        }
      }
    },
    en: {
      label: 'English',
      lang: 'en-US',
      title: 'MediaTree Docs',
      description: 'Documentation for MediaTree deployment, configuration, scraping, playback, updates, and development.',
      themeConfig: {
        nav: [
          { text: 'User Guide', link: '/en/guide/installation' },
          { text: 'API', link: '/en/reference/api' },
          { text: 'Development', link: '/en/development/' },
          { text: 'Release', link: 'https://github.com/ZASENJC/mediatree/releases' }
        ],
        sidebar: {
          '/en/guide/': [
            {
              text: 'User Guide',
              items: enGuide
            }
          ],
          '/en/reference/': [
            {
              text: 'Reference',
              items: enReference
            }
          ],
          '/en/development/': [
            {
              text: 'Developers',
              items: enDevelopment
            }
          ]
        },
        docFooter: {
          prev: 'Previous page',
          next: 'Next page'
        },
        outline: {
          label: 'On this page'
        },
        lastUpdated: {
          text: 'Last updated'
        }
      }
    }
  }
})
