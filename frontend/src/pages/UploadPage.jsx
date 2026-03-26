import { useState } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'
import DropZone from '../components/DropZone'
import AdminMenu from '../components/AdminMenu'

export default function UploadPage() {
    const navigate = useNavigate()
    const [files, setFiles] = useState([])
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
            const response = await axios.post('/api/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            })
            sessionStorage.setItem('uploadResults', JSON.stringify(response.data.results))
            navigate('/result')
        } catch (err) {
            setStatus('error')
            setMessage(err.response?.data?.error || '上传失败，请重试')
        }
    }

    return (
        <div className="upload-page-root">
            <div className="upload-admin-corner">
                <AdminMenu />
            </div>
            <div className="upload-container">

                {/* Header */}
                <header className="upload-header">
                    <div className="brand-logo">
                        <div className="brand-icon-wrap">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                                stroke="white" strokeWidth="2.2"
                                strokeLinecap="round" strokeLinejoin="round">
                                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                                <polyline points="14 2 14 8 20 8" />
                                <path d="M12 18v-6" />
                                <path d="M8 15h8" />
                            </svg>
                        </div>
                        <div className="brand-text-wrap">
                            <span className="brand-name">SafeFood AI Auditor</span>
                            <span className="brand-tagline">食品报告智能核查平台</span>
                        </div>
                    </div>

                    <h1 className="hero-title">SafeFood <em className="hero-em">AI Auditor</em></h1>
                    <p className="hero-subtitle">
                        上传食品检验 PDF 报告，自动完成合规性验证与多维度交叉比对。
                    </p>
                </header>

                {/* 上传卡片 */}
                <main className="upload-main">
                    {message && (
                        <div className="flash-messages">
                            <div className={`flash-message ${status}`}>
                                <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
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
                        <DropZone onFilesChange={handleFilesChange} />

                        {files.length > 0 && (
                            <div className="file-queue">
                                <div className="queue-header">待处理文件 ({files.length})</div>
                                <ul className="queue-list">
                                    {files.map((file, index) => (
                                        <li key={index} className="queue-item">
                                            <div className="queue-icon">
                                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
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

                        <div className="form-actions">
                            <button
                                type="submit"
                                className="btn-primary"
                                disabled={files.length === 0 || status === 'uploading'}
                            >
                                {status === 'uploading' ? (
                                    <>
                                        <span className="btn-spinner" />
                                        <span>核查中，请稍候…</span>
                                    </>
                                ) : (
                                    <>
                                        <span>开始智能核查</span>
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                                            stroke="currentColor" strokeWidth="2.5"
                                            strokeLinecap="round" strokeLinejoin="round">
                                            <line x1="5" y1="12" x2="19" y2="12" />
                                            <polyline points="12 5 19 12 12 19" />
                                        </svg>
                                    </>
                                )}
                            </button>
                        </div>
                    </form>
                </main>

                <footer className="upload-footer">
                    <p>© 2026 食安智审 · SafeFood AI Auditor · 食品报告智能核查平台</p>
                </footer>
            </div>
        </div>
    )
}
