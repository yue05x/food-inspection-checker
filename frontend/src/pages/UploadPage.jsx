import { useState } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'
import DropZone from '../components/DropZone'

export default function UploadPage() {
    const navigate = useNavigate()
    const [files, setFiles] = useState([])
    // idle | uploading | error
    const [status, setStatus] = useState('idle')
    const [message, setMessage] = useState('')

    const handleFilesChange = (newFiles) => {
        setFiles(newFiles)
        setStatus('idle')
        setMessage('')
    }

    const handleSubmit = async (e) => {
        e.preventDefault()
        if (files.length === 0) return

        setStatus('uploading')
        setMessage('')

        const formData = new FormData()
        files.forEach(file => formData.append('pdfs', file))

        try {
            // 使用 Vite 代理：/api/upload 会自动转发到 Flask:5000/api/upload
            const response = await axios.post('/api/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            })

            // 把结果存到 sessionStorage，ResultPage 从这里取
            sessionStorage.setItem('uploadResults', JSON.stringify(response.data.results))
            // 跳转到结果页
            navigate('/result')

        } catch (err) {
            setStatus('error')
            setMessage(err.response?.data?.error || '上传失败，请重试')
        }
    }

    return (
        <div className="upload-container">
            {/* 顶部 Header */}
            <header className="upload-header">
                <div className="brand-logo">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" strokeWidth="2"
                        strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                        <polyline points="14 2 14 8 20 8" />
                        <path d="M12 18v-6" />
                        <path d="M8 15h8" />
                    </svg>
                    <span className="brand-name">InspeX</span>
                </div>
                <h1 className="hero-title">智能检验报告核查</h1>
                <p className="hero-subtitle">拖拽上传 PDF 文件，体验精准自动审核。</p>
            </header>

            {/* 主体 */}
            <main className="upload-main">
                {/* 错误提示 */}
                {message && (
                    <div className="flash-messages">
                        <div className={`flash-message ${status}`}>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                                stroke="currentColor" strokeWidth="2">
                                <circle cx="12" cy="12" r="10" />
                                <line x1="12" y1="8" x2="12" y2="12" />
                                <line x1="12" y1="16" x2="12.01" y2="16" />
                            </svg>
                            <span>{message}</span>
                        </div>
                    </div>
                )}

                <form className="upload-form" onSubmit={handleSubmit}>
                    {/* 拖拽上传区 */}
                    <DropZone onFilesChange={handleFilesChange} />

                    {/* 文件列表 */}
                    {files.length > 0 && (
                        <div className="file-queue">
                            <div className="queue-header">待处理文件 ({files.length})</div>
                            <ul className="queue-list">
                                {files.map((file, index) => (
                                    <li key={index} className="queue-item">
                                        <div className="queue-icon">
                                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                                                stroke="currentColor" strokeWidth="1.5">
                                                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                                                <polyline points="14 2 14 8 20 8" />
                                            </svg>
                                        </div>
                                        <span className="queue-name">{file.name}</span>
                                        <span className="queue-size">
                                            {(file.size / 1024 / 1024).toFixed(2)} MB
                                        </span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* 提交按钮 */}
                    <div className="form-actions">
                        <button
                            type="submit"
                            className="btn-primary"
                            disabled={files.length === 0 || status === 'uploading'}
                        >
                            <span>{status === 'uploading' ? '核查中...' : '开始智能核查'}</span>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                                stroke="currentColor" strokeWidth="2"
                                strokeLinecap="round" strokeLinejoin="round">
                                <line x1="5" y1="12" x2="19" y2="12" />
                                <polyline points="12 5 19 12 12 19" />
                            </svg>
                        </button>
                    </div>
                </form>
            </main>

            <footer className="upload-footer">
                <p>© 2026 InspeX System. Designed for Precision.</p>
            </footer>
        </div>
    )
}
