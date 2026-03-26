import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const ADMIN_PASSWORD = 'admin2025'

export default function AdminMenu() {
    const [open, setOpen] = useState(false)
    const [showAuth, setShowAuth] = useState(false)
    const [pwd, setPwd] = useState('')
    const [error, setError] = useState('')
    const [shaking, setShaking] = useState(false)
    const navigate = useNavigate()
    const ref = useRef(null)
    const inputRef = useRef(null)

    useEffect(() => {
        const handler = (e) => {
            if (ref.current && !ref.current.contains(e.target)) setOpen(false)
        }
        document.addEventListener('mousedown', handler)
        return () => document.removeEventListener('mousedown', handler)
    }, [])

    useEffect(() => {
        if (showAuth) {
            setTimeout(() => inputRef.current?.focus(), 50)
        }
    }, [showAuth])

    const handleAdminClick = () => {
        setOpen(false)
        if (sessionStorage.getItem('adminAuth') === '1') {
            navigate('/admin')
        } else {
            setPwd('')
            setError('')
            setShowAuth(true)
        }
    }

    const handleConfirm = () => {
        if (pwd === ADMIN_PASSWORD) {
            sessionStorage.setItem('adminAuth', '1')
            setShowAuth(false)
            navigate('/admin')
        } else {
            setError('密码错误，请重试')
            setPwd('')
            setShaking(true)
            setTimeout(() => setShaking(false), 400)
            inputRef.current?.focus()
        }
    }

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') handleConfirm()
        if (e.key === 'Escape') { setShowAuth(false); setError('') }
    }

    return (
        <>
            <div className="admin-menu-wrap" ref={ref}>
                <button className="admin-menu-btn" onClick={() => setOpen(v => !v)}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="3" />
                        <path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14" />
                    </svg>
                    <span>管理员</span>
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
                        style={{ transition: 'transform 0.2s', transform: open ? 'rotate(180deg)' : 'none' }}>
                        <polyline points="6 9 12 15 18 9" />
                    </svg>
                </button>

                {open && (
                    <div className="admin-dropdown">
                        <div className="admin-dropdown-label">管理员视图</div>
                        <button className="admin-dropdown-item" onClick={handleAdminClick}>
                            <div className="admin-item-icon admin-item-icon--blue">
                                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <rect x="3" y="3" width="7" height="7" rx="1" />
                                    <rect x="14" y="3" width="7" height="7" rx="1" />
                                    <rect x="14" y="14" width="7" height="7" rx="1" />
                                    <rect x="3" y="14" width="7" height="7" rx="1" />
                                </svg>
                            </div>
                            <div>
                                <div className="admin-item-title">管理员后台</div>
                                <div className="admin-item-desc">驾驶舱 · 知识库管理</div>
                            </div>
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginLeft: 'auto', color: '#CBD5E1' }}>
                                <polyline points="9 18 15 12 9 6" />
                            </svg>
                        </button>
                    </div>
                )}
            </div>

            {/* Auth Modal */}
            {showAuth && (
                <div className="auth-overlay" onClick={(e) => { if (e.target === e.currentTarget) { setShowAuth(false); setError('') } }}>
                    <div className={`auth-modal ${shaking ? 'auth-modal--shake' : ''}`}>
                        <div className="auth-modal-icon">
                            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                            </svg>
                        </div>
                        <h2 className="auth-modal-title">管理员验证</h2>
                        <p className="auth-modal-desc">请输入管理员密码以继续访问</p>
                        <input
                            ref={inputRef}
                            className={`auth-modal-input ${error ? 'auth-modal-input--error' : ''}`}
                            type="password"
                            placeholder="输入管理员密码"
                            value={pwd}
                            onChange={e => { setPwd(e.target.value); setError('') }}
                            onKeyDown={handleKeyDown}
                        />
                        {error && <p className="auth-modal-error">{error}</p>}
                        <div className="auth-modal-actions">
                            <button className="auth-btn-cancel" onClick={() => { setShowAuth(false); setError('') }}>取消</button>
                            <button className="auth-btn-confirm" onClick={handleConfirm}>确认进入</button>
                        </div>
                    </div>
                </div>
            )}
        </>
    )
}
