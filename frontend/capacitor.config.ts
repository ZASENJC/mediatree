import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'com.zasenjc.mediatree',
  appName: 'MediaTree',
  webDir: 'dist',
  backgroundColor: '#03040a',
  android: {
    allowMixedContent: true,
    backgroundColor: '#03040a',
  },
  server: {
    androidScheme: 'http',
    cleartext: true,
  },
}

export default config
