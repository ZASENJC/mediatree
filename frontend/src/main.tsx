import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { TheaterProvider } from './theater'
import { initializeTheme } from './theme'
import './index.css'

initializeTheme()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <TheaterProvider>
        <App />
      </TheaterProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
