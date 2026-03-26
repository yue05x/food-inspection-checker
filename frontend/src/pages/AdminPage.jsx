import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

/* ══════════════════════════════════════════════
   DASHBOARD DATA & CHARTS
══════════════════════════════════════════════ */
const DASH_DATA = {
    kpis: [
        { label: '检验报告', value: '1,284', unit: '份', trend: '+12.3%', color: '#3B82F6' },
        { label: '送检物品', value: '3,672', unit: '件', trend: '+8.7%', color: '#8B5CF6' },
        { label: '送检人员', value: '89', unit: '人', trend: '+3.4%', color: '#06B6D4' },
        { label: '涉及国标', value: '156', unit: '项', trend: '+5.1%', color: '#10B981' },
    ],
    categories: [
        { name: '肉制品', count: 342, pct: 22 },
        { name: '乳制品', count: 287, pct: 18 },
        { name: '饮料', count: 231, pct: 15 },
        { name: '调味品', count: 198, pct: 13 },
        { name: '糕点', count: 176, pct: 11 },
        { name: '食用油', count: 143, pct: 9 },
        { name: '其他', count: 295, pct: 12 },
    ],
    submitters: [
        { name: '张伟', dept: '质检部', count: 142 },
        { name: '李娟', dept: '监管科', count: 118 },
        { name: '王明', dept: '抽检组', count: 97 },
        { name: '陈芳', dept: '检验室', count: 83 },
        { name: '刘洋', dept: '质检部', count: 71 },
    ],
    standards: [
        { code: 'GB 2762', name: '食品中污染物限量', count: 89 },
        { code: 'GB 2763', name: '农药最大残留限量', count: 76 },
        { code: 'GB 23200', name: '农药残留检测方法', count: 65 },
        { code: 'GB 5009', name: '食品理化检验方法', count: 54 },
        { code: 'GB 7718', name: '预包装食品标签通则', count: 43 },
    ],
    trend: [
        { month: '9月', count: 87 },
        { month: '10月', count: 124 },
        { month: '11月', count: 98 },
        { month: '12月', count: 145 },
        { month: '1月', count: 112 },
        { month: '2月', count: 156 },
        { month: '3月', count: 189 },
    ],
}

const PALETTE = ['#3B82F6', '#8B5CF6', '#06B6D4', '#10B981', '#F59E0B', '#EF4444', '#64748B']

function DonutChart({ data }) {
    const total = data.reduce((s, d) => s + d.count, 0)
    const cx = 84, cy = 84, r = 62
    const toRad = (deg) => (deg * Math.PI) / 180
    const polarXY = (angle, radius) => ({
        x: cx + radius * Math.cos(toRad(angle)),
        y: cy + radius * Math.sin(toRad(angle)),
    })
    let cursor = -90
    const slices = data.map((d, i) => {
        const sweep = (d.count / total) * 359.99
        const start = cursor
        cursor += sweep
        const s = polarXY(start, r)
        const e = polarXY(start + sweep, r)
        const large = sweep > 180 ? 1 : 0
        return { ...d, color: PALETTE[i], d: `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}` }
    })
    return (
        <div className="adm-donut-wrap">
            <svg viewBox="0 0 168 168" width="168" height="168" style={{ flexShrink: 0 }}>
                {slices.map((sl, i) => (
                    <path key={i} d={sl.d} fill="none" stroke={sl.color} strokeWidth="20" strokeLinecap="butt" />
                ))}
                <text x={cx} y={cy - 7} textAnchor="middle" fill="#0F172A" fontSize="22" fontWeight="700">
                    {total.toLocaleString()}
                </text>
                <text x={cx} y={cy + 13} textAnchor="middle" fill="#94A3B8" fontSize="10">
                    送检物品总计
                </text>
            </svg>
            <div className="adm-donut-legend">
                {data.map((d, i) => (
                    <div key={i} className="adm-donut-row">
                        <span className="adm-donut-dot" style={{ background: PALETTE[i] }} />
                        <span className="adm-donut-name">{d.name}</span>
                        <span className="adm-donut-pct">{d.pct}%</span>
                    </div>
                ))}
            </div>
        </div>
    )
}

function BarChart({ data }) {
    const max = Math.max(...data.map(d => d.count))
    const W = 52, H = 110
    return (
        <div style={{ flex: 1 }}>
            <svg viewBox={`0 0 ${data.length * W} ${H + 28}`} width="100%" height={H + 28}>
                <defs>
                    <linearGradient id="bGrad2" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.9" />
                        <stop offset="100%" stopColor="#3B82F6" stopOpacity="0.3" />
                    </linearGradient>
                </defs>
                {data.map((d, i) => {
                    const bH = Math.max(4, (d.count / max) * H)
                    const x = i * W + 6
                    const y = H - bH
                    return (
                        <g key={i}>
                            <rect x={x} y={y} width={40} height={bH} fill="url(#bGrad2)" rx="4" />
                            <text x={x + 20} y={H + 16} textAnchor="middle" fill="#64748B" fontSize="10">{d.month}</text>
                            <text x={x + 20} y={y - 5} textAnchor="middle" fill="#94A3B8" fontSize="9">{d.count}</text>
                        </g>
                    )
                })}
            </svg>
            <div className="adm-bar-footer">
                <span>最近7个月送检报告数量</span>
                <span style={{ color: '#3B82F6', fontWeight: 600 }}>峰值 189份（3月）</span>
            </div>
        </div>
    )
}

function RankList({ items, accentColor = '#3B82F6', codeKey }) {
    const max = Math.max(...items.map(d => d.count))
    return (
        <div className="adm-rank-list">
            {items.map((item, i) => (
                <div key={i} className="adm-rank-row">
                    <span className="adm-rank-num" style={{ color: i < 3 ? accentColor : '#94A3B8' }}>{i + 1}</span>
                    <div className="adm-rank-body">
                        <div className="adm-rank-label">
                            {codeKey && <span className="adm-rank-code" style={{ borderColor: accentColor + '40', color: accentColor }}>{item[codeKey]}</span>}
                            <span className="adm-rank-name">{item.name}</span>
                            {item.dept && <span className="adm-rank-tag">{item.dept}</span>}
                        </div>
                        <div className="adm-rank-track">
                            <div className="adm-rank-bar" style={{ width: `${(item.count / max) * 100}%`, background: i < 3 ? accentColor : '#CBD5E1' }} />
                        </div>
                    </div>
                    <span className="adm-rank-val">{item.count}</span>
                </div>
            ))}
        </div>
    )
}

function DashboardContent() {
    const dateStr = new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
    return (
        <div className="adm-dash-body">
            <div className="adm-section-header">
                <div className="adm-live">
                    <span className="adm-live-dot" />
                    <span>实时数据 · {dateStr} · 模拟数据</span>
                </div>
            </div>
            {/* KPI Row */}
            <div className="adm-kpi-row">
                {DASH_DATA.kpis.map((k, i) => (
                    <div key={i} className="adm-kpi-card">
                        <div className="adm-kpi-indicator" style={{ background: k.color + '15', borderColor: k.color + '35', color: k.color }}>
                            ▲ {k.trend}
                        </div>
                        <div className="adm-kpi-value">
                            {k.value}<span className="adm-kpi-unit">{k.unit}</span>
                        </div>
                        <div className="adm-kpi-label">{k.label}</div>
                        <div className="adm-kpi-track" style={{ background: k.color + '15' }}>
                            <div className="adm-kpi-fill" style={{ background: k.color, width: '68%' }} />
                        </div>
                    </div>
                ))}
            </div>
            {/* Charts Row */}
            <div className="adm-chart-row">
                <div className="adm-card" style={{ flex: '0 0 400px' }}>
                    <div className="adm-card-hd">
                        <span className="adm-card-title">品类分布</span>
                        <span className="adm-card-sub">按送检物品分类统计</span>
                    </div>
                    <DonutChart data={DASH_DATA.categories} />
                </div>
                <div className="adm-card" style={{ flex: 1 }}>
                    <div className="adm-card-hd">
                        <span className="adm-card-title">月度送检趋势</span>
                        <span className="adm-card-sub">近7个月报告数量变化</span>
                    </div>
                    <BarChart data={DASH_DATA.trend} />
                </div>
            </div>
            {/* Rank Row */}
            <div className="adm-chart-row">
                <div className="adm-card" style={{ flex: 1 }}>
                    <div className="adm-card-hd">
                        <span className="adm-card-title">送检人排行</span>
                        <span className="adm-card-sub">TOP 5</span>
                    </div>
                    <RankList items={DASH_DATA.submitters} accentColor="#3B82F6" />
                </div>
                <div className="adm-card" style={{ flex: 1 }}>
                    <div className="adm-card-hd">
                        <span className="adm-card-title">高频涉及国标</span>
                        <span className="adm-card-sub">TOP 5</span>
                    </div>
                    <RankList items={DASH_DATA.standards} accentColor="#06B6D4" codeKey="code" />
                </div>
            </div>
        </div>
    )
}

/* ══════════════════════════════════════════════
   KNOWLEDGE BASE CONTENT
══════════════════════════════════════════════ */
const KB_TABS = [
    { id: 'rules',     label: '实施细则', path: 'backend/static/files/' },
    { id: 'standards', label: '国标文件', path: 'backend/static/downloads/' },
    { id: 'reports',   label: '上传报告', path: 'backend/static/uploads/' },
    { id: 'labels',    label: '包装图片', path: 'backend/static/uploads/labels/' },
]
const TAB_URL_PREFIX = {
    rules:     '/static/files/',
    standards: '/static/downloads/',
    reports:   '/static/uploads/',
    labels:    '/static/uploads/labels/',
}
const IMAGE_EXTS = new Set(['.jpg', '.jpeg', '.png', '.webp', '.bmp'])

function KnowledgeContent() {
    const [kbTab, setKbTab]     = useState('rules')
    const [search, setSearch]   = useState('')
    const [files, setFiles]     = useState([])
    const [loading, setLoading] = useState(false)
    const [counts, setCounts]   = useState({})
    const [uploading, setUploading] = useState(false)
    const uploadRef = useRef(null)

    const fetchFiles = async (tab) => {
        setLoading(true)
        try {
            const res = await fetch(`/api/admin/kb_files?tab=${tab}`)
            const data = await res.json()
            if (data.success) {
                setFiles(data.files)
                setCounts(prev => ({ ...prev, [tab]: data.count }))
            }
        } catch (e) {
            console.error('获取文件列表失败', e)
        } finally {
            setLoading(false)
        }
    }

    // 初始化及切换 tab 时加载
    useEffect(() => { fetchFiles(kbTab) }, [kbTab])

    const handleTabChange = (id) => { setKbTab(id); setSearch('') }

    const handleUpload = async (e) => {
        const file = e.target.files?.[0]
        if (!file) return
        setUploading(true)
        const form = new FormData()
        form.append('file', file)
        form.append('tab', kbTab)
        try {
            const res = await fetch('/api/admin/upload_kb_file', { method: 'POST', body: form })
            const data = await res.json()
            if (data.success) {
                await fetchFiles(kbTab)
            } else {
                alert('上传失败：' + data.error)
            }
        } catch (e) {
            alert('上传出错：' + e.message)
        } finally {
            setUploading(false)
            if (uploadRef.current) uploadRef.current.value = ''
        }
    }

    const tabInfo = KB_TABS.find(t => t.id === kbTab) || KB_TABS[0]
    const filtered = files.filter(f => f.name.toLowerCase().includes(search.toLowerCase()))
    const urlPrefix = TAB_URL_PREFIX[kbTab]

    return (
        <div className="adm-kb-body">
            <div className="adm-kb-toolbar-top">
                <div className="kb-tab-bar">
                    {KB_TABS.map(t => (
                        <button key={t.id} className={`kb-tab ${kbTab === t.id ? 'active' : ''}`}
                            onClick={() => handleTabChange(t.id)}>
                            {t.label}
                            <span className="kb-tab-count">{counts[t.id] ?? '–'}</span>
                        </button>
                    ))}
                </div>
                <button className="kb-upload-btn" disabled={uploading}
                    onClick={() => uploadRef.current?.click()}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="17 8 12 3 7 8" />
                        <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                    {uploading ? '上传中…' : '上传新文件'}
                </button>
                <input ref={uploadRef} type="file" accept="application/pdf"
                    style={{ display: 'none' }} onChange={handleUpload} />
            </div>

            <div className="kb-toolbar">
                <div className="kb-path-bar">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                    </svg>
                    <span>存储路径：</span>
                    <code className="kb-path-code">{tabInfo.path}</code>
                    <span className="kb-path-sep" />
                    <span className="kb-path-stat">{files.length} 个文件</span>
                </div>
                <div className="kb-search-wrap">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
                    </svg>
                    <input className="kb-search" placeholder="搜索文件…" value={search}
                        onChange={e => setSearch(e.target.value)} />
                </div>
            </div>

            <div className="kb-file-list">
                {loading ? (
                    <div className="kb-empty"><p>加载中…</p></div>
                ) : filtered.length === 0 ? (
                    <div className="kb-empty">
                        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                            <polyline points="14 2 14 8 20 8" />
                        </svg>
                        <p>{search ? '暂无匹配文件' : '该目录暂无文件'}</p>
                    </div>
                ) : filtered.map((f, i) => {
                    const viewUrl = urlPrefix + encodeURIComponent(f.name)
                    const ext = f.name.slice(f.name.lastIndexOf('.')).toLowerCase()
                    const isImage = IMAGE_EXTS.has(ext)
                    return (
                        <div key={i} className="kb-file-row">
                            <div className="kb-file-ico">
                                {isImage ? (
                                    <img src={viewUrl} alt={f.name}
                                        style={{ width: 36, height: 36, objectFit: 'cover', borderRadius: 4, border: '1px solid rgba(0,0,0,0.1)' }} />
                                ) : (
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                                        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                                        <polyline points="14 2 14 8 20 8" />
                                    </svg>
                                )}
                            </div>
                            <div className="kb-file-info">
                                <div className="kb-file-name" title={f.name}>{f.name}</div>
                                <div className="kb-file-meta">
                                    <span>{f.size}</span>
                                    <span className="kb-meta-dot">·</span>
                                    <span>{f.date}</span>
                                </div>
                            </div>
                            <div className="kb-file-actions">
                                <a href={viewUrl} target="_blank" rel="noopener noreferrer"
                                    className="btn-icon-sm" title="在新标签页预览">
                                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                                        <circle cx="12" cy="12" r="3" />
                                    </svg>
                                </a>
                                <a href={viewUrl} download={f.name}
                                    className="btn-icon-sm" title="下载">
                                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                        <polyline points="7 10 12 15 17 10" />
                                        <line x1="12" y1="15" x2="12" y2="3" />
                                    </svg>
                                </a>
                            </div>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}

/* ══════════════════════════════════════════════
   ADMIN PAGE (Combined)
══════════════════════════════════════════════ */
const MAIN_TABS = [
    {
        id: 'dashboard', label: '数据驾驶舱',
        icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /></svg>
    },
    {
        id: 'knowledge', label: '本地知识库',
        icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /></svg>
    },
]

export default function AdminPage() {
    const [authed, setAuthed] = useState(false)
    const [tab, setTab] = useState('dashboard')
    const navigate = useNavigate()

    useEffect(() => {
        if (sessionStorage.getItem('adminAuth') === '1') {
            setAuthed(true)
        } else {
            navigate('/')
        }
    }, [])

    const logout = () => {
        sessionStorage.removeItem('adminAuth')
        navigate('/')
    }

    if (!authed) return null

    return (
        <div className="admin-page">
            {/* Header */}
            <header className="admin-page-header">
                <div className="admin-page-header-left">
                    <button className="admin-page-back" onClick={() => navigate('/')}>
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                            <polyline points="15 18 9 12 15 6" />
                        </svg>
                    </button>
                    <div className="admin-page-brand">
                        <div className="admin-page-badge">管理员后台</div>
                        <div className="admin-page-divider" />
                        <h1 className="admin-page-title">SafeFood AI Auditor</h1>
                        <span className="admin-page-subtitle">食品报告智能核查平台 · 管理控制台</span>
                    </div>
                </div>
                <div className="admin-page-header-right">
                    <button className="admin-logout-btn" onClick={logout}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                            <polyline points="16 17 21 12 16 7" />
                            <line x1="21" y1="12" x2="9" y2="12" />
                        </svg>
                        退出登录
                    </button>
                </div>
            </header>

            {/* Tab Bar */}
            <div className="admin-page-tabs">
                {MAIN_TABS.map(t => (
                    <button key={t.id} className={`admin-page-tab ${tab === t.id ? 'active' : ''}`}
                        onClick={() => setTab(t.id)}>
                        {t.icon}
                        {t.label}
                    </button>
                ))}
            </div>

            {/* Content */}
            <div className="admin-page-content">
                {tab === 'dashboard' ? <DashboardContent /> : <KnowledgeContent />}
            </div>
        </div>
    )
}
