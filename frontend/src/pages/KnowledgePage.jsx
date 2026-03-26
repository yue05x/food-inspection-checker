import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import AdminMenu from '../components/AdminMenu'

/* ── Mock file data (mirrors actual backend/static structure) ── */
const KB_FILES = {
    rules: [
        { name: '2025年食品安全监督抽检实施细则.pdf', size: '8.2 MB', date: '2025-01-15', status: 'available' },
        { name: '2024年食品安全监督抽检实施细则.pdf', size: '7.9 MB', date: '2024-01-20', status: 'available' },
    ],
    standards: [
        { name: 'GB2762-2022 食品中污染物限量.pdf', size: '3.4 MB', date: '2022-06-01', status: 'cached' },
        { name: 'GB2763-2021 农药最大残留限量.pdf', size: '12.1 MB', date: '2021-09-03', status: 'cached' },
        { name: 'GB23200.113-2018 植物源性食品中208种农药残留量测定.pdf', size: '5.6 MB', date: '2018-12-21', status: 'cached' },
        { name: 'GB23200.121-2021 食品中65种农药残留量测定.pdf', size: '4.2 MB', date: '2021-11-26', status: 'cached' },
        { name: 'GB5009.3-2016 食品中水分的测定.pdf', size: '1.8 MB', date: '2016-08-31', status: 'pending' },
        { name: 'GB7718-2011 预包装食品标签通则.pdf', size: '2.3 MB', date: '2011-04-20', status: 'pending' },
    ],
    methods: [
        { name: 'GB5009系列食品理化检验方法汇编.pdf', size: '45.2 MB', date: '2023-03-01', status: 'available' },
        { name: 'NY-T1379系列农药残留检测方法.pdf', size: '12.8 MB', date: '2022-07-15', status: 'available' },
        { name: 'SN-T系列进出口食品检验方法.pdf', size: '8.6 MB', date: '2021-11-08', status: 'available' },
    ],
    reports: [
        { name: '检验报告_2026001.pdf', size: '2.3 MB', date: '2026-03-10', status: 'available' },
        { name: '检验报告_2026002.pdf', size: '1.9 MB', date: '2026-03-11', status: 'available' },
        { name: '检验报告_2026003.pdf', size: '2.1 MB', date: '2026-03-12', status: 'available' },
    ],
}

const STORAGE_PATHS = {
    rules: 'backend/static/files/',
    standards: 'backend/static/downloads/',
    methods: 'backend/static/files/',
    reports: 'backend/static/uploads/',
}

const STATUS = {
    available: { label: '可用', cls: 'kb-st-ok' },
    cached: { label: '已缓存', cls: 'kb-st-cached' },
    pending: { label: '待下载', cls: 'kb-st-pending' },
}

const TABS = [
    {
        id: 'rules', label: '实施细则',
        icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></svg>
    },
    {
        id: 'standards', label: '国标文件',
        icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M9 21V9" /></svg>
    },
    {
        id: 'methods', label: '检验方法',
        icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 1-2-2V9m0 0h18" /></svg>
    },
    {
        id: 'reports', label: '上传报告',
        icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" /><polyline points="14 2 14 8 20 8" /></svg>
    },
]

function FileIcon() {
    return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
            <polyline points="14 2 14 8 20 8" />
        </svg>
    )
}

export default function KnowledgePage() {
    const navigate = useNavigate()
    const [tab, setTab] = useState('rules')
    const [search, setSearch] = useState('')
    const uploadRef = useRef(null)

    const files = (KB_FILES[tab] || []).filter(f =>
        f.name.toLowerCase().includes(search.toLowerCase())
    )
    const storagePath = STORAGE_PATHS[tab]
    const totalAll = (KB_FILES[tab] || []).length
    const cachedCount = (KB_FILES[tab] || []).filter(f => f.status === 'cached' || f.status === 'available').length

    return (
        <div className="kb-page">
            {/* Header */}
            <header className="kb-header">
                <div className="kb-header-left">
                    <button className="kb-back-btn" onClick={() => navigate(-1)}>
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                            <polyline points="15 18 9 12 15 6" />
                        </svg>
                    </button>
                    <div>
                        <h1 className="kb-title">本地知识库</h1>
                        <p className="kb-subtitle">统一管理细则、国标、检验方法与报告 · 支持缓存入库</p>
                    </div>
                </div>
                <div className="kb-header-right">
                    <button className="kb-upload-btn" onClick={() => uploadRef.current?.click()}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                            <polyline points="17 8 12 3 7 8" />
                            <line x1="12" y1="3" x2="12" y2="15" />
                        </svg>
                        上传新文件
                    </button>
                    <input ref={uploadRef} type="file" accept="application/pdf" style={{ display: 'none' }} />
                    <AdminMenu />
                </div>
            </header>

            <div className="kb-body">
                {/* Tab bar */}
                <div className="kb-tab-bar">
                    {TABS.map(t => (
                        <button key={t.id} className={`kb-tab ${tab === t.id ? 'active' : ''}`} onClick={() => { setTab(t.id); setSearch('') }}>
                            {t.icon}
                            {t.label}
                            <span className="kb-tab-count">{KB_FILES[t.id]?.length ?? 0}</span>
                        </button>
                    ))}
                </div>

                {/* Storage path + search */}
                <div className="kb-toolbar">
                    <div className="kb-path-bar">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                        </svg>
                        <span>存储路径：</span>
                        <code className="kb-path-code">{storagePath}</code>
                        <span className="kb-path-sep" />
                        <span className="kb-path-stat">{cachedCount}/{totalAll} 已就绪</span>
                    </div>
                    <div className="kb-search-wrap">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
                        </svg>
                        <input
                            className="kb-search"
                            placeholder="搜索文件…"
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                        />
                    </div>
                </div>

                {/* File list */}
                <div className="kb-file-list">
                    {files.length === 0 ? (
                        <div className="kb-empty">
                            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                                <polyline points="14 2 14 8 20 8" />
                            </svg>
                            <p>暂无匹配文件</p>
                        </div>
                    ) : files.map((f, i) => {
                        const st = STATUS[f.status]
                        const viewUrl = tab === 'standards'
                            ? `/static/downloads/${f.name}`
                            : tab === 'reports'
                                ? `/static/uploads/${f.name}`
                                : `/static/files/${f.name}`
                        return (
                            <div key={i} className="kb-file-row">
                                <div className="kb-file-ico"><FileIcon /></div>
                                <div className="kb-file-info">
                                    <div className="kb-file-name" title={f.name}>{f.name}</div>
                                    <div className="kb-file-meta">
                                        <span>{f.size}</span>
                                        <span className="kb-meta-dot">·</span>
                                        <span>{f.date}</span>
                                        <span className="kb-meta-dot">·</span>
                                        <code className="kb-file-path">{storagePath}{f.name}</code>
                                    </div>
                                </div>
                                <div className="kb-file-actions">
                                    <span className={`kb-status ${st.cls}`}>{st.label}</span>
                                    <a href={viewUrl} target="_blank" rel="noopener noreferrer" className="btn-icon-sm" title="查看">
                                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
                                        </svg>
                                    </a>
                                    <a href={viewUrl} download className="btn-icon-sm" title="下载">
                                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                            <polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
                                        </svg>
                                    </a>
                                </div>
                            </div>
                        )
                    })}
                </div>

                {/* Cache notice */}
                <div className="kb-cache-notice">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0, marginTop: 1 }}>
                        <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                    <span>
                        新标准下载后自动入库缓存，统一存储于 <code>backend/static/downloads/</code>。
                        已缓存文件可直接调用，无需重复下载。上传报告存储于 <code>backend/static/uploads/</code>，
                        细则与检验方法存储于 <code>backend/static/files/</code>。
                    </span>
                </div>
            </div>
        </div>
    )
}
