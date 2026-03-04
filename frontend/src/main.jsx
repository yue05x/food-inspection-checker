import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'
import App from './App.jsx'

// 给 body 加上 page-upload class，激活旧 CSS 里的上传页样式
document.body.classList.add('page-upload')

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
