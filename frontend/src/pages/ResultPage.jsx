import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

/* ───────── 工具函数 ───────── */
function statusText(s) {
    if (s === 'passed' || s === 'pass') return '通过'
    if (s === 'failed' || s === 'fail') return '未通过'
    return '待验证'
}
function statusClass(s) {
    if (s === 'passed' || s === 'pass') return 'passed'
    if (s === 'failed' || s === 'fail') return 'failed'
    return 'unknown'
}

function calculateModulesStatus(s) {
    if (!s) s = {}

    // ─── 标准指标合理性：从实际证据推算状态 ───
    const rag = s.ragflow_verification || {}
    const indicatorEvidence = (rag.evidence || []).filter(e => e.type === 'indicator')
    const NOT_FOUND = ['', '未找到限量值', '未提取', '未查到']
    const anyLimitFound = indicatorEvidence.some(e => e.extracted_limit && !NOT_FOUND.includes((e.extracted_limit || '').trim()))
    const anyLimitFailed = indicatorEvidence.some(e => e.limit_issue)
    let stdStatus
    if (indicatorEvidence.length === 0) {
        stdStatus = s.standard_indicators_status || 'unknown'
    } else if (anyLimitFailed) {
        stdStatus = 'failed'
    } else if (anyLimitFound) {
        stdStatus = 'passed'
    } else {
        stdStatus = 'unknown'  // 全部“未查到” → 待验证
    }

    // ─── 标签信息：从已上传的 labels 推算状态 ───
    const labels = (s.additional_files || {}).labels || []
    let labelStatus
    if (labels.length === 0) {
        labelStatus = s.label_info_status || 'unknown'
    } else if (labels.some(l => l.product_type || l.standard_code)) {
        labelStatus = 'passed'
    } else {
        labelStatus = 'unknown'  // 上传了但未能提取
    }

    // ─── 评价依据合理性状态 ───
    const basisStatus = s.regulatory_basis_consistent === true ? 'passed'
        : s.regulatory_basis_consistent === false ? 'failed' : 'unknown'

    const modules = [
        { id: 'standards', title: '检验项目合规性', status: s.standards_compliance_status || 'unknown', desc: '检验项目是否符合实施细则规定' },
        { id: 'validation', title: '评价依据合理性', status: basisStatus, desc: '判定依据标准是否与细则一致' },
        { id: 'method_compliance', title: '检测方法合规性', status: s.method_compliance_status || 'unknown', desc: '检测方法是否合规有效' },
        { id: 'standard_compliance', title: '标准指标合理性', status: stdStatus, desc: '标准限量是否满足要求' },
        { id: 'sample_check', title: '样品信息核对', status: s.sample_info_status || 'unknown', desc: '样品信息与委托单是否一致' },
        { id: 'package', title: '标签信息', status: labelStatus, desc: '产品标签信息是否完整' },
    ]

    let failedCount = 0
    let unknownCount = 0
    let passedCount = 0
    modules.forEach(m => {
        const sc = statusClass(m.status)
        if (sc === 'failed') failedCount++
        else if (sc === 'passed') passedCount++
        else unknownCount++
    })

    return { modules, failedCount, unknownCount, passedCount }
}

/* ───────── 综合核对结果 Tab ───────── */
function SummaryTab({ result, onSwitchTab }) {
    const s = result.summary || {}
    const { modules, failedCount, unknownCount } = calculateModulesStatus(s)

    const overallPassed = failedCount === 0 && unknownCount === 0

    return (
        <div>
            {/* 总体状态 */}
            <div className={`overall-status ${failedCount > 0 ? 'failed' : overallPassed ? 'passed' : 'unknown'}`}>
                <div className="status-icon">
                    {failedCount > 0
                        ? <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" /></svg>
                        : overallPassed
                            ? <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
                            : <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
                    }
                </div>
                <div className="status-content">
                    <h2 className="status-title">{failedCount > 0 ? '验证未通过' : overallPassed ? '验证通过' : '待补充信息'}</h2>
                    <p className="status-description">
                        {failedCount > 0 || unknownCount > 0
                            ? `检测到 ${failedCount} 个模块未通过，${unknownCount} 个模块待验证`
                            : '所有验证项目均符合要求'}
                    </p>
                </div>
            </div>

            {/* 模块卡片网格 */}
            <div className="section-block">
                <h3 className="block-title">验证模块概览</h3>
                <div className="verification-modules-grid">
                    {modules.map(m => (
                        <div key={m.id} className={`module-card ${statusClass(m.status)}`} onClick={() => onSwitchTab(m.id)} style={{ cursor: 'pointer' }}>
                            <div className="module-content">
                                <h4 className="module-title">{m.title}</h4>
                                <p className="module-description">{m.desc}</p>
                            </div>
                            <div className="module-status">
                                <span className={`status-badge ${statusClass(m.status)}`}>{statusText(m.status)}</span>
                            </div>
                            <div className="module-arrow">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6" /></svg>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}


/* ───────── 截图预览弹窗 ───────── */
function ScreenshotModal({ src, onClose }) {
    if (!src) return null
    return (
        <div onClick={onClose} style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999, cursor: 'pointer'
        }}>
            <div onClick={e => e.stopPropagation()} style={{ position: 'relative', maxWidth: '90vw', maxHeight: '90vh' }}>
                <img src={src} alt="截图" style={{ maxWidth: '100%', maxHeight: '90vh', borderRadius: 8, boxShadow: '0 20px 60px rgba(0,0,0,0.5)' }} />
                <button onClick={onClose} style={{
                    position: 'absolute', top: -12, right: -12, width: 32, height: 32,
                    borderRadius: '50%', background: '#ef4444', border: 'none', color: '#fff',
                    cursor: 'pointer', fontSize: 18, lineHeight: 1, display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>✕</button>
                <a href={src} download style={{
                    position: 'absolute', bottom: -40, left: '50%', transform: 'translateX(-50%)',
                    background: '#3b82f6', color: '#fff', padding: '6px 16px', borderRadius: 6,
                    fontSize: 13, textDecoration: 'none', whiteSpace: 'nowrap'
                }}>⬇ 保存截图</a>
            </div>
        </div>
    )
}

/* ───────── 评价依据合理性 Tab ───────── */
function ValidationTab({ result }) {
    const s = result.summary || {}
    const gbResults = s.gb_validation || {}
    const rag = s.ragflow_verification || {}
    const [screenshotSrc, setScreenshotSrc] = useState(null)

    return (
        <div>
            {/* 截图弹窗 */}
            <ScreenshotModal src={screenshotSrc} onClose={() => setScreenshotSrc(null)} />

            {/* 依据标准一致性 */}
            <div className="section-block">
                <h3 className="block-title">检验依据标准一致性</h3>
                {(() => {
                    // 归一化：去掉 -202X 年份后缀再比较
                    const normGB = code => code.trim().replace(/-\d{4}$/, '').trim()

                    // 报告的国标编号（原始）
                    const reportCodes = s.gb_codes || []
                    // 细则的国标编号（原始）
                    const gbPattern = /GB(?:\/T|\/Z)?\s*[\d]+[\d.]*(?:-\d{2,4})?/gi
                    const ruleCodes = []
                        ; (rag.matched_items || []).forEach(item => {
                            const basis = (item.required_basis || '').trim()
                            if (!basis) return
                                ; (basis.match(gbPattern) || []).forEach(m =>
                                    ruleCodes.push(m.replace(/\s+/g, ' ').trim())
                                )
                        })

                    // 按归一化键分组（Map<normKey, {report?, rules?}>）
                    const codeMap = new Map()
                    const ensure = key => { if (!codeMap.has(key)) codeMap.set(key, { report: null, rules: null }) }
                    reportCodes.forEach(c => { const k = normGB(c); ensure(k); codeMap.get(k).report = c })
                    ruleCodes.forEach(c => { const k = normGB(c); ensure(k); codeMap.get(k).rules = c })

                    const sorted = [...codeMap.entries()].sort(([a], [b]) => a.localeCompare(b))
                    if (sorted.length === 0) return <div className="info-scrim">暂无标准依据数据</div>

                    return (
                        <div className="table-container">
                            <table className="clean-table" style={{ width: '100%' }}>
                                <thead>
                                    <tr>
                                        <th>报告检验结论（国标文件）</th>
                                        <th>细则依据法律法规/标准</th>
                                        <th style={{ width: 100 }}>结论</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {sorted.map(([norm, { report, rules }]) => {
                                        const consistent = report && rules
                                        const rowStyle = !consistent ? { background: 'rgba(239,68,68,0.06)' } : {}
                                        return (
                                            <tr key={norm} style={rowStyle}>
                                                <td>{report ? <strong>{report}</strong> : <span style={{ color: '#94a3b8' }}>—</span>}</td>
                                                <td>{rules ? <strong>{rules}</strong> : <span style={{ color: '#94a3b8' }}>—</span>}</td>
                                                <td>{consistent
                                                    ? <span className="badge-sm success">一致</span>
                                                    : report && !rules
                                                        ? <span className="badge-sm warning">细则无要求</span>
                                                        : <span className="badge-sm error">报告未引用</span>}
                                                </td>
                                            </tr>
                                        )
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )
                })()}
            </div>

            {/* 依据国标文件有效性 */}
            <div className="section-block">
                <h3 className="block-title">依据国标文件有效性</h3>
                {Object.keys(gbResults).length > 0 ? (
                    <div className="table-container">
                        <table className="clean-table" style={{ width: '100%' }}>
                            <thead>
                                <tr>
                                    <th style={{ width: 140 }}>标准编号</th>
                                    <th style={{ width: 110 }}>有效性</th>
                                    <th>详细信息</th>
                                    <th style={{ width: 130 }}>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {Object.entries(gbResults).map(([code, v]) => (
                                    <tr key={code}>
                                        <td><strong>{code}</strong></td>
                                        <td>
                                            <span className={`badge-sm ${v.passed ? 'success' : 'error'}`}>
                                                {v.status_text || (v.passed ? '现行有效' : '已废止')}
                                            </span>
                                        </td>
                                        <td style={{ fontSize: 12, color: '#94a3b8' }}>
                                            {v.publish_date && <div>发布：{v.publish_date}</div>}
                                            {v.implement_date && <div>实施：{v.implement_date}</div>}
                                            {v.reasons && v.reasons.length > 0 && (
                                                <div style={{ color: '#f87171', marginTop: 4 }}>{v.reasons[0]}</div>
                                            )}
                                        </td>
                                        <td>
                                            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                                                {v.screenshot_path ? (
                                                    <button className="btn-icon-sm" title="查看截图"
                                                        onClick={() => setScreenshotSrc(v.screenshot_path)}>
                                                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                                                            <circle cx="8.5" cy="8.5" r="1.5" />
                                                            <polyline points="21 15 16 10 5 21" />
                                                        </svg>
                                                    </button>
                                                ) : (
                                                    <button className="btn-icon-sm" title="无截图" disabled style={{ opacity: 0.35, cursor: 'default' }}>
                                                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                                                            <circle cx="8.5" cy="8.5" r="1.5" />
                                                            <polyline points="21 15 16 10 5 21" />
                                                        </svg>
                                                    </button>
                                                )}
                                                {v.download_path ? (
                                                    <a href={v.download_path} download className="btn-icon-sm" title="下载标准文件">
                                                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                                            <polyline points="7 10 12 15 17 10" />
                                                            <line x1="12" y1="15" x2="12" y2="3" />
                                                        </svg>
                                                    </a>
                                                ) : (
                                                    <button className="btn-icon-sm" title="无标准文件" disabled style={{ opacity: 0.35, cursor: 'default' }}>
                                                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                                            <polyline points="7 10 12 15 17 10" />
                                                            <line x1="12" y1="15" x2="12" y2="3" />
                                                        </svg>
                                                    </button>
                                                )}
                                                {v.detail_url ? (
                                                    <a href={v.detail_url} target="_blank" rel="noreferrer" className="btn-icon-sm" title="查看详情页">
                                                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                                                            <polyline points="15 3 21 3 21 9" />
                                                            <line x1="10" y1="14" x2="21" y2="3" />
                                                        </svg>
                                                    </a>
                                                ) : (
                                                    <button className="btn-icon-sm" title="无详情页" disabled style={{ opacity: 0.35, cursor: 'default' }}>
                                                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                                                            <polyline points="15 3 21 3 21 9" />
                                                            <line x1="10" y1="14" x2="21" y2="3" />
                                                        </svg>
                                                    </button>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : <div className="info-scrim">暂无国标验证数据</div>}
            </div>
        </div>
    )
}


/* ───────── 检验项目合规性 Tab ───────── */
function StandardsTab({ result, onJumpToPdf }) {
    const s = result.summary || {}
    const rag = s.ragflow_verification || {}
    const matched = rag.matched_items || []
    const missing = rag.missing_items || []   // 细则有，报告无 (string[])
    const extra = rag.extra_items || []        // 报告有，细则无 (string[])

    const noData = matched.length === 0 && missing.length === 0 && extra.length === 0
    if (noData) return <div className="info-scrim">未找到相关检验项目细则数据</div>

    const totalRules = matched.length + missing.length

    // 只显示真正贡献了 matched_items 的细则页码（过滤掉未贡献条目的通用页面）
    const evidencePages = [...new Set(
        matched.filter(m => m.source_page).map(m => m.source_page)
    )].sort((a, b) => a - b)

    return (
        <div className="section-block">
            <h3 className="block-title">检验项目合规性验证</h3>
            {/* 细则来源页码入口 */}
            {evidencePages.length > 0 && (
                <div style={{ marginBottom: 12, fontSize: 12, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <span>细则来源页：</span>
                    {evidencePages.map(p => (
                        <button key={p} className="badge-sm info"
                            style={{ cursor: 'pointer' }}
                            title={`跳转到细则第 ${p} 页`}
                            onClick={() => onJumpToPdf && onJumpToPdf('rules', p)}>
                            P.{p}
                        </button>
                    ))}
                </div>
            )}
            <div style={{ marginBottom: 12, fontSize: 13, color: '#94a3b8' }}>
                细则要求 <strong style={{ color: '#e2e8f0' }}>{totalRules}</strong> 项 ·
                已匹配 <strong style={{ color: '#4ade80' }}>{matched.length}</strong> 项 ·
                报告缺失 <strong style={{ color: '#f87171' }}>{missing.length}</strong> 项 ·
                细则外 <strong style={{ color: '#fbbf24' }}>{extra.length}</strong> 项
            </div>
            <div className="table-container">
                <table className="clean-table" style={{ width: '100%' }}>
                    <thead>
                        <tr>
                            <th>细则要求项目</th>
                            <th>报告检验项目</th>
                            <th style={{ width: 80 }}>页码</th>
                            <th style={{ width: 100 }}>一致性</th>
                        </tr>
                    </thead>
                    <tbody>
                        {matched.map((item, i) => (
                            <tr key={`m-${i}`}>
                                <td>{item.name || '–'}</td>
                                <td>{item.report_name || item.name || '–'}</td>
                                <td>
                                    {item.source_page ? (
                                        <button className="badge-sm info"
                                            style={{ cursor: 'pointer' }}
                                            title={`跳转到细则第 ${item.source_page} 页`}
                                            onClick={() => onJumpToPdf && onJumpToPdf('rules', item.source_page)}>
                                            P.{item.source_page}
                                        </button>
                                    ) : '–'}
                                </td>
                                <td><span className="badge-sm success">✓ 一致</span></td>
                            </tr>
                        ))}
                        {missing.map((name, i) => (
                            <tr key={`miss-${i}`}>
                                <td>{name}</td>
                                <td style={{ color: '#f87171' }}>—</td>
                                <td>–</td>
                                <td><span className="badge-sm error">报告缺失</span></td>
                            </tr>
                        ))}
                        {extra.map((name, i) => (
                            <tr key={`ex-${i}`}>
                                <td style={{ color: '#94a3b8' }}>—</td>
                                <td>{name}</td>
                                <td>–</td>
                                <td><span className="badge-sm warning">细则未要求</span></td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    )
}


/* ───────── 检测方法合规性 Tab ───────── */
function MethodComplianceTab({ result, onJumpToPdf }) {
    const rag = (result.summary || {}).ragflow_verification || {}
    const matched = rag.matched_items || []
    const methodIssues = rag.method_issues || []
    const issueNames = new Set(methodIssues.map(i => i.item))

    if (matched.length === 0) {
        return <div className="info-scrim">无方法核查数据</div>
    }

    return (
        <div className="section-block">
            <h3 className="block-title">检测方法合规性验证</h3>
            {/* 细则来源页汇总 */}
            {(() => {
                const pages = [...new Set(
                    matched.filter(m => m.source_page).map(m => m.source_page)
                )].sort((a, b) => a - b)
                if (pages.length === 0) return null
                return (
                    <div style={{ marginBottom: 12, fontSize: 12, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                        <span>细则来源页：</span>
                        {pages.map(p => (
                            <button key={p} className="badge-sm info"
                                style={{ cursor: 'pointer' }}
                                title={`跳转到细则第 ${p} 页`}
                                onClick={() => onJumpToPdf && onJumpToPdf('rules', p)}>
                                P.{p}
                            </button>
                        ))}
                    </div>
                )
            })()}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {matched.map((item, i) => {
                    const hasIssue = issueNames.has(item.name)
                    const rawMethods = (item.required_method || '').trim().split(/\s+/).filter(Boolean)
                    const methods = []
                    for (let k = 0; k < rawMethods.length; k++) {
                        const token = rawMethods[k]
                        // 如果 token 是常见的标准前缀（纯字母或带斜杠字母，如 GB, GB/T, NY/T 等），且后面还有内容，则合并为一个完整的标准号
                        if (/^[A-Za-z]+(?:\/[A-Za-z]+)?$/.test(token) && k + 1 < rawMethods.length) {
                            methods.push(token + ' ' + rawMethods[k + 1])
                            k++ // 跳过下一个 token
                        } else {
                            methods.push(token)
                        }
                    }
                    return (
                        <div key={i} style={{
                            borderRadius: 8,
                            border: `1px solid ${hasIssue ? 'rgba(239,68,68,0.3)' : 'var(--color-border)'}`,
                            padding: '12px 16px',
                            background: 'var(--color-surface)',
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                                <strong style={{ fontSize: 14 }}>{item.name}</strong>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                    {item.source_page && (
                                        <button className="badge-sm info"
                                            style={{ cursor: 'pointer' }}
                                            title={`跳转到细则第 ${item.source_page} 页`}
                                            onClick={() => onJumpToPdf && onJumpToPdf('rules', item.source_page)}>
                                            细则 P.{item.source_page}
                                        </button>
                                    )}
                                    <span className={`badge-sm ${hasIssue ? 'error' : 'success'}`}>
                                        {hasIssue ? '✗ 方法不合规' : '✓ 方法合规'}
                                    </span>
                                </div>
                            </div>
                            <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>
                                <span style={{ marginRight: 6 }}>细则要求方法：</span>
                                {methods.length > 0
                                    ? methods.map((m, j) => <span key={j} className="badge-sm" style={{ marginRight: 4, marginBottom: 2, display: 'inline-block' }}>{m}</span>)
                                    : <span>—</span>}
                            </div>
                            <div style={{ fontSize: 12, color: '#94a3b8' }}>
                                <span style={{ marginRight: 6 }}>报告使用方法：</span>
                                <span className="badge-sm">{item.report_method || '未识别'}</span>
                            </div>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}

/* ───────── 标准指标合理性 Tab ───────── */
function StandardComplianceTab({ result, onJumpToPdf }) {
    const rag = (result.summary || {}).ragflow_verification || {}
    const indicatorIssues = rag.indicator_issues || []
    const reportItems = result.items || []
    const indicatorEvidence = (rag.evidence || []).filter(e => e.type === 'indicator')
    const matchedItems = rag.matched_items || []

    const reportValueMap = {}
    reportItems.forEach(item => {
        const key = (item.item || '').trim()
        if (key) reportValueMap[key] = item
    })

    const LIMIT_NOT_FOUND = ['未找到限量值', '未提取', '未查到', '']
    const isLimitFound = s => s && !LIMIT_NOT_FOUND.includes(s.trim())

    const hasEvidence = indicatorEvidence.length > 0

    if (!hasEvidence && matchedItems.length === 0) {
        return <div className="info-scrim">暂无指标对比数据</div>
    }

    return (
        <div>
            {/* 表1：标准指标与计量单位核查 */}
            <div className="section-block">
                <h3 className="block-title">标准指标与计量单位核查</h3>
                {hasEvidence ? (
                    <div className="table-container">
                        <table className="clean-table" style={{ width: '100%' }}>
                            <thead>
                                <tr>
                                    <th>检验项目</th>
                                    <th>报告计量单位</th>
                                    <th>国标限量原文（含单位）</th>
                                    <th>来源国标及页码</th>
                                </tr>
                            </thead>
                            <tbody>
                                {indicatorEvidence.map((ev, i) => {
                                    const reportItem = reportValueMap[ev.item] || {}
                                    const reportUnit = reportItem.unit || '–'
                                    const limitOk = isLimitFound(ev.extracted_limit)
                                    return (
                                        <tr key={i}>
                                            <td>{ev.item}</td>
                                            <td>{reportUnit}</td>
                                            <td style={{ fontSize: 12, color: limitOk ? 'inherit' : '#fbbf24' }}>
                                                {limitOk ? ev.extracted_limit : '未查到'}
                                            </td>
                                            <td>
                                                <div style={{ fontSize: 11, color: '#94a3b8' }}>{ev.doc_name || '–'}</div>
                                                {ev.page_num && (
                                                    <button className="badge-sm info"
                                                        style={{ cursor: 'pointer', marginTop: 4, display: 'block' }}
                                                        title={`跳转到国标第 ${ev.page_num} 页`}
                                                        onClick={() => onJumpToPdf && onJumpToPdf('gb', ev.page_num)}>
                                                        国标 P.{ev.page_num}
                                                    </button>
                                                )}
                                            </td>
                                        </tr>
                                    )
                                })}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="info-scrim">未能从国标文件中查询到对应指标内容</div>
                )}
            </div>

            {/* 表2：实测值范围核查 */}
            <div className="section-block">
                <h3 className="block-title">实测值范围核查</h3>
                {hasEvidence ? (
                    <div className="table-container">
                        <table className="clean-table" style={{ width: '100%' }}>
                            <thead>
                                <tr>
                                    <th>检验项目</th>
                                    <th>报告实测值</th>
                                    <th>国标限量值</th>
                                    <th style={{ width: 90 }}>结论</th>
                                </tr>
                            </thead>
                            <tbody>
                                {indicatorEvidence.map((ev, i) => {
                                    const reportItem = reportValueMap[ev.item] || {}
                                    const measureVal = reportItem.value || reportItem.result || '–'
                                    const limitOk = isLimitFound(ev.extracted_limit)
                                    const isIssue = indicatorIssues.some(iss => iss.includes(ev.item))
                                    let badgeClass, badgeText
                                    if (isIssue) { badgeClass = 'error'; badgeText = '超标' }
                                    else if (!limitOk) { badgeClass = 'warning'; badgeText = '无法判断' }
                                    else { badgeClass = 'success'; badgeText = '合规' }
                                    return (
                                        <tr key={i}>
                                            <td>{ev.item}</td>
                                            <td>{measureVal}</td>
                                            <td style={{ fontSize: 12, color: limitOk ? 'inherit' : '#fbbf24' }}>
                                                {limitOk ? ev.extracted_limit : '未查到限量值'}
                                            </td>
                                            <td><span className={`badge-sm ${badgeClass}`}>{badgeText}</span></td>
                                        </tr>
                                    )
                                })}
                            </tbody>
                        </table>
                    </div>
                ) : matchedItems.length > 0 ? (
                    <>
                        <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 10 }}>
                            ⓘ 标准限量数据查询失败（RAGFlow 知识库未包含对应标准文件），以下仅展示报告中的测定值。
                        </div>
                        <div className="table-container">
                            <table className="clean-table" style={{ width: '100%' }}>
                                <thead>
                                    <tr>
                                        <th>检验项目（细则）</th>
                                        <th>报告项目名称</th>
                                        <th>报告测定值</th>
                                        <th>检测方法</th>
                                        <th style={{ width: 80 }}>细则页码</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {matchedItems.map((m, i) => {
                                        const reportItem = reportValueMap[m.report_name] || reportValueMap[m.name] || {}
                                        return (
                                            <tr key={i}>
                                                <td>{m.name || '–'}</td>
                                                <td>{m.report_name || m.name || '–'}</td>
                                                <td>{reportItem.value || reportItem.result || '–'}</td>
                                                <td style={{ fontSize: 12 }}>{reportItem.method || '–'}</td>
                                                <td>
                                                    {m.source_page ? (
                                                        <button className="badge-sm info"
                                                            style={{ cursor: 'pointer' }}
                                                            title={`跳转到细则第 ${m.source_page} 页`}
                                                            onClick={() => onJumpToPdf && onJumpToPdf('rules', m.source_page)}>
                                                            P.{m.source_page}
                                                        </button>
                                                    ) : '–'}
                                                </td>
                                            </tr>
                                        )
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </>
                ) : (
                    <div className="info-scrim">暂无指标对比数据</div>
                )}
            </div>
        </div>
    )
}


/* ───────── 样品信息核对 Tab ───────── */
function SampleCheckTab({ result }) {
    const additional = (result.summary || {}).additional_files || {}
    const protocols = additional.protocols || []

    return (
        <div className="section-block">
            <h3 className="block-title">样品信息核对</h3>
            {protocols.length > 0 ? (
                protocols.map((p, i) => (
                    <div key={i} style={{ background: 'rgba(255,255,255,0.05)', borderRadius: 8, padding: 16, marginBottom: 12 }}>
                        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>{p.filename}</div>
                        <a href={p.file_url} target="_blank" rel="noreferrer" style={{ color: '#3b82f6', fontSize: 13 }}>查看委托单</a>
                    </div>
                ))
            ) : (
                <div className="info-scrim">
                    <p>暂未上传委托单。点击左侧文件名旁的 <strong>+</strong> 按钮上传委托单。</p>
                </div>
            )}
        </div>
    )
}

/* ───────── 标签信息 Tab ───────── */
function PackageTab({ result }) {
    const additional = (result.summary || {}).additional_files || {}
    const labels = additional.labels || []

    return (
        <div className="section-block">
            <h3 className="block-title">标签信息</h3>
            {labels.length > 0 ? (
                labels.map((lb, i) => {
                    const hasInfo = lb.product_type || lb.standard_code
                    return (
                        <div key={i} style={{ background: 'rgba(255,255,255,0.08)', borderRadius: 10, padding: 16, marginBottom: 14, border: '1px solid rgba(0,0,0,0.08)' }}>
                            {/* 文件名 + 查看链接 */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2">
                                    <rect x="3" y="3" width="18" height="18" rx="2" />
                                    <path d="M3 9h18M9 21V9" />
                                </svg>
                                <span style={{ fontSize: 14, fontWeight: 600, color: '#1e293b' }}>{lb.filename}</span>
                                {lb.file_url && (
                                    <a href={lb.file_url} target="_blank" rel="noreferrer"
                                        style={{ color: '#3b82f6', fontSize: 12, marginLeft: 'auto' }}>
                                        查看原图 ↗
                                    </a>
                                )}
                            </div>

                            {/* 提取到的结构化信息 */}
                            {hasInfo ? (
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                                    {lb.product_type && (
                                        <div style={{ background: 'rgba(59,130,246,0.14)', borderRadius: 8, padding: '10px 14px' }}>
                                            <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>产品类型</div>
                                            <div style={{ fontSize: 14, fontWeight: 600, color: '#1e293b' }}>{lb.product_type}</div>
                                        </div>
                                    )}
                                    {lb.standard_code && (
                                        <div style={{ background: 'rgba(59,130,246,0.14)', borderRadius: 8, padding: '10px 14px' }}>
                                            <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>产品标准号</div>
                                            <div style={{ fontSize: 14, fontWeight: 600, color: '#1e293b' }}>{lb.standard_code}</div>
                                        </div>
                                    )}
                                    {lb.production_date && (
                                        <div style={{ background: 'rgba(0,0,0,0.04)', borderRadius: 8, padding: '10px 14px' }}>
                                            <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>生产日期</div>
                                            <div style={{ fontSize: 13, color: '#374151' }}>{lb.production_date}</div>
                                        </div>
                                    )}
                                    {lb.shelf_life && (
                                        <div style={{ background: 'rgba(0,0,0,0.04)', borderRadius: 8, padding: '10px 14px' }}>
                                            <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>保质期</div>
                                            <div style={{ fontSize: 13, color: '#374151' }}>{lb.shelf_life}</div>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div style={{ fontSize: 12, color: '#f59e0b', marginBottom: 8 }}>
                                    ⚠ 未能自动提取产品类型或标准号（OCR 识别内容不包含相关字段）
                                </div>
                            )}

                            {/* OCR 原始文本（折叠展示，供排查） */}
                            {lb.raw_text && (
                                <details style={{ marginTop: 10 }}>
                                    <summary style={{ fontSize: 11, color: '#475569', cursor: 'pointer', userSelect: 'none' }}>
                                        查看 OCR 识别原文
                                    </summary>
                                    <pre style={{
                                        fontSize: 11, color: '#374151', background: 'rgba(0,0,0,0.05)',
                                        borderRadius: 6, padding: 10, marginTop: 8,
                                        whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 200, overflowY: 'auto'
                                    }}>{lb.raw_text}</pre>
                                </details>
                            )}
                        </div>
                    )
                })
            ) : (
                <div className="info-scrim">
                    <p>暂未上传标签信息。点击左侧文件名旁的 <strong>+</strong> 按钮选择「标签图片」上传。</p>
                </div>
            )}
        </div>
    )
}


/* ───────── Tab 配置 ───────── */
const TABS = [
    { id: 'summary', label: '综合核对结果' },
    { id: 'standards', label: '检验项目合规性' },
    { id: 'validation', label: '评价依据合理性' },
    { id: 'method_compliance', label: '检测方法合理性' },
    { id: 'standard_compliance', label: '标准指标合理性' },
    { id: 'sample_check', label: '样品信息核对' },
    { id: 'package', label: '标签信息' },
]

/* ───────── 主页面 ───────── */
export default function ResultPage() {
    const navigate = useNavigate()
    const [results, setResults] = useState([])
    const [currentIndex, setCurrentIndex] = useState(0)
    const [tab, setTab] = useState('summary')
    const [pdfView, setPdfView] = useState('report')  // report | rules | gb
    const [pdfPage, setPdfPage] = useState(1)          // 当前 PDF 页码
    const appendInputRef = useRef(null)
    const hiddenFileInputRef = useRef(null)
    const [uploadType, setUploadType] = useState(null)
    const [dropdownIdx, setDropdownIdx] = useState(null)  // 当前展开下拉的文件索引
    const [previewWidth, setPreviewWidth] = useState(42) // 默认 42vw 宽度
    const [sidebarWidth, setSidebarWidth] = useState(260) // 默认 260px 宽度

    /* 拖拽调整侧边栏宽度 */
    const handleSidebarDragStart = (e) => {
        e.preventDefault()
        const startX = e.clientX
        const initialWidth = sidebarWidth

        const onMouseMove = (moveEvent) => {
            const deltaX = moveEvent.clientX - startX
            const newWidth = initialWidth + deltaX
            if (newWidth >= 200 && newWidth <= 500) setSidebarWidth(newWidth)
        }

        const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove)
            document.removeEventListener('mouseup', onMouseUp)
        }

        document.addEventListener('mousemove', onMouseMove)
        document.addEventListener('mouseup', onMouseUp)
    }

    /* 拖拽调整预览区宽度 */
    const handleDragStart = (e) => {
        e.preventDefault()
        const startX = e.clientX
        const initialWidth = previewWidth

        const onMouseMove = (moveEvent) => {
            const deltaX = moveEvent.clientX - startX
            const vw = document.documentElement.clientWidth
            // 向左拖动 deltaX 为负，宽度变大
            const newWidth = initialWidth - (deltaX / vw) * 100
            if (newWidth >= 20 && newWidth <= 75) setPreviewWidth(newWidth)
        }

        const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove)
            document.removeEventListener('mouseup', onMouseUp)
        }

        document.addEventListener('mousemove', onMouseMove)
        document.addEventListener('mouseup', onMouseUp)
    }

    /* 跳转 PDF 页码 */
    const jumpToPdf = (view, page) => {
        setPdfView(view)
        setPdfPage(page || 1)
    }

    useEffect(() => {
        const raw = sessionStorage.getItem('uploadResults')
        if (!raw) { navigate('/'); return }
        try { setResults(JSON.parse(raw)) } catch { navigate('/') }
    }, [navigate])

    const result = results[currentIndex]
    const s = result?.summary || {}

    /* PDF 视图 URL（含 #page=N 锚点跳页） */
    const gbDownloadPath = (() => {
        const code = s.gb_codes?.[0]
        if (!code) return ''
        // 优先从 gb_validation 取已下载的路径
        const v = (s.gb_validation || {})[code]
        if (v?.download_path) return v.download_path
        // 降级：static/files/{code}.pdf（空格保留，Flask 会 URL 编码）
        return `/static/files/${code}.pdf`
    })()
    const pdfBaseUrl = pdfView === 'report'
        ? result?.pdf_url || ''
        : pdfView === 'rules'
            ? '/static/files/2025年食品安全监督抽检实施细则.pdf'
            : gbDownloadPath
    const pdfUrl = pdfPage > 1 ? `${pdfBaseUrl}#page=${pdfPage}` : pdfBaseUrl

    /* 追加上传 PDF */
    const handleAppendPdf = async (file) => {
        if (!file) return
        const formData = new FormData()
        formData.append('file', file)
        try {
            const res = await fetch('/api/process_pdf', { method: 'POST', body: formData })
            const data = await res.json()
            if (data.success) {
                const updated = [...results, data.data]
                setResults(updated)
                sessionStorage.setItem('uploadResults', JSON.stringify(updated))
                setCurrentIndex(updated.length - 1)
            } else alert('处理失败：' + data.error)
        } catch (e) { alert('上传出错：' + e.message) }
        if (appendInputRef.current) appendInputRef.current.value = ''
    }

    /* 附加信息上传（委托单/标签） */
    const handleAttachFile = async (file) => {
        if (!file || !uploadType) return
        const api = uploadType === 'protocol' ? '/api/upload_protocol' : '/api/upload_label_info'
        const formData = new FormData()
        formData.append('file', file)
        try {
            const res = await fetch(api, { method: 'POST', body: formData })
            const data = await res.json()
            if (data.success) {
                const updated = results.map((r, i) => {
                    if (i !== currentIndex) return r
                    const af = r.summary.additional_files || { protocols: [], labels: [] }
                    if (uploadType === 'protocol') af.protocols = [...(af.protocols || []), data.data]
                    else af.labels = [...(af.labels || []), data.data]
                    return { ...r, summary: { ...r.summary, additional_files: af } }
                })
                setResults(updated)
                sessionStorage.setItem('uploadResults', JSON.stringify(updated))
            } else alert('上传失败：' + data.error)
        } catch (e) { alert('上传出错：' + e.message) }
        if (hiddenFileInputRef.current) hiddenFileInputRef.current.value = ''
    }

    if (!result) return null

    return (
        <div className="app-container" style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
            {/* ── 顶部 Header ── */}
            <header className="app-header">
                <div className="header-left">
                    <a href="/" className="brand-link" onClick={e => { e.preventDefault(); navigate('/') }}>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                            <polyline points="14 2 14 8 20 8" />
                            <path d="M12 18v-6" /><path d="M8 15h8" />
                        </svg>
                        <span className="brand-text">SafeFood AI Auditor</span>
                    </a>
                    <div className="divider" />
                    <span className="page-title">核查结果</span>
                </div>
            </header>

            {/* ── 三栏主体 ── */}
            <main className="app-workspace" style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

                {/* 左侧：文件列表 */}
                <aside className="sidebar-files" style={{ width: sidebarWidth, flexShrink: 0 }}>
                    <div className="sidebar-header"><h3>文件列表</h3></div>
                    <div className="sidebar-content">
                        <ul className="file-list-nav">
                            {results.map((r, i) => (
                                <li key={i}
                                    className={`file-nav-item ${i === currentIndex ? 'active' : ''}`}
                                    onClick={() => setCurrentIndex(i)}>
                                    <div className="file-item-main">
                                        <div className={`file-status-icon ${r.status}`}>
                                            {r.status === 'success'
                                                ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12" /></svg>
                                                : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
                                            }
                                        </div>
                                        <div className="file-meta">
                                            <span className="file-name" title={r.filename}>{r.filename}</span>
                                            {(() => {
                                                const { failedCount, unknownCount } = calculateModulesStatus(r.summary)
                                                const risks = failedCount + unknownCount
                                                return <span className="file-desc">{risks === 0 ? '无异常' : `${risks} 个风险项`}</span>
                                            })()}
                                        </div>
                                    </div>
                                    <div style={{ position: 'relative' }}>
                                        <button className="btn-icon-sm" title="上传附加信息"
                                            onClick={e => { e.stopPropagation(); setDropdownIdx(dropdownIdx === i ? null : i) }}
                                            style={{ marginLeft: 4 }}>
                                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
                                            </svg>
                                        </button>
                                        {dropdownIdx === i && (
                                            <div style={{
                                                position: 'absolute', right: 0, top: '110%', zIndex: 999,
                                                background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                                                borderRadius: 8, boxShadow: '0 8px 24px rgba(0,0,0,.5)',
                                                minWidth: 120, overflow: 'hidden'
                                            }}>
                                                {[
                                                    { label: '委托单', type: 'protocol' },
                                                    { label: '标签图片', type: 'label' }
                                                ].map(opt => (
                                                    <button key={opt.type}
                                                        style={{
                                                            display: 'block', width: '100%', textAlign: 'left',
                                                            padding: '9px 14px', background: 'none', border: 'none',
                                                            color: 'var(--color-text)', fontSize: 13, cursor: 'pointer'
                                                        }}
                                                        onMouseDown={e => e.stopPropagation()}
                                                        onClick={e => {
                                                            e.stopPropagation()
                                                            setUploadType(opt.type)
                                                            setDropdownIdx(null)
                                                            hiddenFileInputRef.current?.click()
                                                        }}>
                                                        {opt.label}
                                                    </button>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </li>
                            ))}
                        </ul>
                    </div>
                    <div className="sidebar-footer">
                        <button className="btn-secondary btn-block" onClick={() => appendInputRef.current?.click()}>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                <polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
                            </svg>
                            继续上传报告
                        </button>
                        <input ref={appendInputRef} type="file" accept="application/pdf" style={{ display: 'none' }}
                            onChange={e => handleAppendPdf(e.target.files[0])} />
                        <input ref={hiddenFileInputRef} type="file" accept="application/pdf,image/jpeg,image/png,image/jpg" style={{ display: 'none' }}
                            onChange={e => handleAttachFile(e.target.files[0])} />
                    </div>
                </aside>

                {/* 侧边栏拖拽控制柄 */}
                <div className="resizer-handle" onMouseDown={handleSidebarDragStart}>
                    <div className="resizer-line" />
                </div>

                {/* 中间：Tab 内容 */}
                <section className="content-detail">
                    <div className="detail-header">
                        <h2>{result.filename}</h2>
                    </div>

                    {/* Tab 导航 */}
                    <div className="tab-navigation">
                        {TABS.map(t => (
                            <button key={t.id}
                                className={`tab-btn ${tab === t.id ? 'active' : ''}`}
                                onClick={() => setTab(t.id)}>
                                {t.label}
                            </button>
                        ))}
                    </div>

                    {/* Tab 内容区 */}
                    <div className="detail-scroll-area">
                        {tab === 'summary' && <SummaryTab result={result} onSwitchTab={setTab} />}
                        {tab === 'standards' && <StandardsTab result={result} onJumpToPdf={jumpToPdf} />}
                        {tab === 'validation' && <ValidationTab result={result} />}
                        {tab === 'method_compliance' && <MethodComplianceTab result={result} onJumpToPdf={jumpToPdf} />}
                        {tab === 'standard_compliance' && <StandardComplianceTab result={result} onJumpToPdf={jumpToPdf} />}
                        {tab === 'sample_check' && <SampleCheckTab result={result} />}
                        {tab === 'package' && <PackageTab result={result} />}
                    </div>
                </section>

                {/* 拖拽控制柄 */}
                <div className="resizer-handle" onMouseDown={handleDragStart}>
                    <div className="resizer-line" />
                </div>

                {/* 右侧：PDF 预览 */}
                <section className="content-preview" style={{ width: `${previewWidth}vw` }}>
                    <div className="preview-header">
                        <h3>原始报告预览</h3>
                        <div className="preview-controls">
                            {['report', 'rules', 'gb'].map((v, _, arr) => {
                                const labels = { report: '报告', rules: '细则', gb: '国标' }
                                return (
                                    <button key={v}
                                        className={`btn-icon-text ${pdfView === v ? 'active' : ''}`}
                                        onClick={() => jumpToPdf(v, 1)}>
                                        {labels[v]}
                                    </button>
                                )
                            })}
                        </div>
                    </div>
                    <div className="preview-body">
                        <iframe
                            key={`${pdfView}-${pdfPage}`}
                            src={pdfUrl}
                            className="pdf-frame"
                            title="PDF预览"
                        />
                    </div>
                </section>
            </main>
        </div>
    )
}
