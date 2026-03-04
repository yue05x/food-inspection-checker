import { useRef, useState } from 'react'

/**
 * DropZone 拖拽上传组件
 * Props:
 *   onFilesChange(files: File[]) — 文件列表变化时的回调
 */
export default function DropZone({ onFilesChange }) {
    const [isDragging, setIsDragging] = useState(false)
    const fileInputRef = useRef(null)

    // 阻止默认行为（防止浏览器直接打开文件）
    const prevent = (e) => {
        e.preventDefault()
        e.stopPropagation()
    }

    // 拖入区域 → 高亮
    const handleDragEnter = (e) => { prevent(e); setIsDragging(true) }
    const handleDragOver = (e) => { prevent(e); setIsDragging(true) }

    // 拖离区域 → 取消高亮
    const handleDragLeave = (e) => { prevent(e); setIsDragging(false) }

    // 松开文件
    const handleDrop = (e) => {
        prevent(e)
        setIsDragging(false)
        const files = Array.from(e.dataTransfer.files)
        onFilesChange(files)
    }

    // 点击区域 → 触发文件选择框
    const handleClick = () => fileInputRef.current?.click()

    // input 选择文件后
    const handleInputChange = (e) => {
        const files = Array.from(e.target.files)
        onFilesChange(files)
    }

    return (
        <div
            className={`upload-area ${isDragging ? 'highlight' : ''}`}
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={handleClick}
        >
            {/* 隐藏的真实 input，由点击触发 */}
            <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf,image/jpeg,image/png,image/jpg"
                multiple
                className="file-input-hidden"
                onChange={handleInputChange}
            />

            <div className="upload-content">
                <div className="upload-icon-wrapper">
                    <svg className="upload-icon" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" strokeWidth="1.5"
                        strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="17 8 12 3 7 8" />
                        <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                </div>
                <div className="upload-text">
                    <span className="link-text">点击选择文件</span>
                    <span className="separator">或</span>
                    <span className="drag-text">拖拽至此</span>
                </div>
                <p className="upload-hint">支持 PDF 和图片格式（JPG、PNG）</p>
            </div>
        </div>
    )
}
