// memory.mjs — 考研对话自学习记忆系统
// 架构: 感官→短期/工作→情景→语义→程序 五级记忆
// 纯 Node.js ESM，零外部依赖，自动持久化

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs"
import { dirname, join } from "node:path"
import { homedir, platform } from "node:os"
import { randomUUID, createHash } from "node:crypto"

// ═══════════════════════════════════════════════════════════
// Config
// ═══════════════════════════════════════════════════════════

const MEMORY_DIR = join(homedir(), ".kaoyan-memory")
const MEMORY_FILE = join(MEMORY_DIR, "memory.json")
const MAX_EPISODES = 200           // 情景记忆上限
const MAX_WORKING_ITEMS = 20       // 工作记忆上限
const DECAY_DAYS = 90              // 记忆衰减周期（天）
const INFER_THRESHOLD = 3          // 推断语义记忆所需证据数

// ═══════════════════════════════════════════════════════════
// Types & Schema
// ═══════════════════════════════════════════════════════════

/** @typedef {{
 *   id: string,
 *   timestamp: string,
 *   type: 'query'|'compare'|'feedback'|'intent',
 *   school?: string,
 *   major?: string,
 *   majorCode?: string,
 *   session?: string,
 *   result?: object,
 *   userFeedback?: 'hotter'|'colder'|'accurate'|'inaccurate'|null,
 *   context?: { previousQueries?: string[], userIntent?: string, rawInput?: string }
 * }} Episode */

/** @typedef {{
 *   targetTier?: string[],
 *   preferredRegions?: string[],
 *   preferredMajorCategories?: string[],
 *   avoidSchools?: string[],
 *   preferredSchools?: string[],
 *   riskTolerance?: 'low'|'medium'|'high',
 *   targetYear?: number,
 *   budgetMode?: boolean
 * }} UserProfile */

/** @typedef {{
 *   fact: string,
 *   category: 'preference'|'constraint'|'goal'|'behavior',
 *   confidence: number,
 *   evidence: number,
 *   firstSeen: string,
 *   lastConfirmed: string,
 *   sources: string[]
 * }} InferredFact */

/** @typedef {{
 *   currentSessionId: string,
 *   sessionStart: string,
 *   recentQueryIds: string[],
 *   currentTopic: string|null,
 *   pendingComparisons: {school:string,major:string}[],
 *   lastInteraction: string
 * }} WorkingMemory */

/** @typedef {{
 *   preferredOutputFormat: 'json'|'markdown'|'table'|null,
 *   dataSourcePreference: string[],
 *   lastLoginMethod: string|null,
 *   queryPatterns: {pattern:string,count:number}[]
 * }} ProceduralMemory */

/** @typedef {{
 *   version: string,
 *   createdAt: string,
 *   updatedAt: string,
 *   episodicMemory: Episode[],
 *   semanticMemory: {
 *     userProfile: UserProfile,
 *     inferredFacts: InferredFact[]
 *   },
 *   workingMemory: WorkingMemory,
 *   proceduralMemory: ProceduralMemory
 * }} MemoryBank */

// ═══════════════════════════════════════════════════════════
// Persistence
// ═══════════════════════════════════════════════════════════

function ensureDir() {
	if (!existsSync(MEMORY_DIR)) {
		mkdirSync(MEMORY_DIR, { recursive: true })
	}
}

function loadMemoryBank() {
	ensureDir()
	if (!existsSync(MEMORY_FILE)) {
		return createEmptyBank()
	}
	try {
		const data = JSON.parse(readFileSync(MEMORY_FILE, "utf-8"))
		return migrateIfNeeded(data)
	} catch {
		return createEmptyBank()
	}
}

function saveMemoryBank(bank) {
	ensureDir()
	bank.updatedAt = new Date().toISOString()
	writeFileSync(MEMORY_FILE, JSON.stringify(bank, null, 2))
}

function createEmptyBank() {
	const now = new Date().toISOString()
	return {
		version: "1.0",
		createdAt: now,
		updatedAt: now,
		episodicMemory: [],
		semanticMemory: {
			userProfile: {},
			inferredFacts: [],
		},
		workingMemory: {
			currentSessionId: randomUUID(),
			sessionStart: now,
			recentQueryIds: [],
			currentTopic: null,
			pendingComparisons: [],
			lastInteraction: now,
		},
		proceduralMemory: {
			preferredOutputFormat: null,
			dataSourcePreference: [],
			lastLoginMethod: null,
			queryPatterns: [],
		},
	}
}

function migrateIfNeeded(data) {
	if (!data.version) data.version = "1.0"
	if (!data.semanticMemory) data.semanticMemory = { userProfile: {}, inferredFacts: [] }
	if (!data.workingMemory) {
		data.workingMemory = {
			currentSessionId: randomUUID(),
			sessionStart: new Date().toISOString(),
			recentQueryIds: [],
			currentTopic: null,
			pendingComparisons: [],
			lastInteraction: new Date().toISOString(),
		}
	}
	if (!data.proceduralMemory) {
		data.proceduralMemory = {
			preferredOutputFormat: null,
			dataSourcePreference: [],
			lastLoginMethod: null,
			queryPatterns: [],
		}
	}
	return data
}

// ═══════════════════════════════════════════════════════════
// Core Memory Operations
// ═══════════════════════════════════════════════════════════

class KaoyanMemory {
	constructor() {
		this.bank = loadMemoryBank()
	}

	_save() {
		saveMemoryBank(this.bank)
	}

	// ─── Working Memory ─────────────────────────────────────

	/** 记录一次交互，更新工作记忆 */
	touchInteraction(topic = null) {
		const wm = this.bank.workingMemory
		wm.lastInteraction = new Date().toISOString()
		if (topic) wm.currentTopic = topic
		this._save()
	}

	/** 开始新会话 */
	startNewSession() {
		const wm = this.bank.workingMemory
		wm.currentSessionId = randomUUID()
		wm.sessionStart = new Date().toISOString()
		wm.recentQueryIds = []
		wm.currentTopic = null
		wm.pendingComparisons = []
		wm.lastInteraction = new Date().toISOString()
		this._save()
		return wm.currentSessionId
	}

	/** 将 episode ID 推入工作记忆（LRU） */
	_pushWorkingId(id) {
		const wm = this.bank.workingMemory
		wm.recentQueryIds = [id, ...wm.recentQueryIds.filter((x) => x !== id)].slice(0, MAX_WORKING_ITEMS)
		wm.lastInteraction = new Date().toISOString()
	}

	/** 添加待对比项 */
	pushPendingComparison(school, major) {
		const wm = this.bank.workingMemory
		const exists = wm.pendingComparisons.some((p) => p.school === school && p.major === major)
		if (!exists) {
			wm.pendingComparisons.push({ school, major })
			if (wm.pendingComparisons.length > 10) wm.pendingComparisons.shift()
		}
		this._save()
	}

	/** 清除已对比项 */
	clearPendingComparison(school, major) {
		const wm = this.bank.workingMemory
		wm.pendingComparisons = wm.pendingComparisons.filter((p) => !(p.school === school && p.major === major))
		this._save()
	}

	// ─── Episodic Memory ────────────────────────────────────

	/** 记录一次查询事件 */
	recordQuery({ school, major, majorCode, session, result, userFeedback = null, context = {} }) {
		const episode = {
			id: randomUUID(),
			timestamp: new Date().toISOString(),
			type: "query",
			school,
			major,
			majorCode,
			session,
			result: result
				? {
						compositeHeat: result.compositeHeat,
						heatLevel: result.heatLevel,
						dataSource: result.dataSource,
				  }
				: null,
			userFeedback,
			context: {
				previousQueries: [...this.bank.workingMemory.recentQueryIds.slice(0, 5)],
				userIntent: context.userIntent || null,
				rawInput: context.rawInput || null,
			},
		}

		this.bank.episodicMemory.unshift(episode)
		this._pushWorkingId(episode.id)

		// 触发压缩
		if (this.bank.episodicMemory.length > MAX_EPISODES) {
			this._compressEpisodic()
		}

		// 触发语义推断
		if (this.bank.episodicMemory.length % 5 === 0) {
			this._inferSemantics()
		}

		this._save()
		return episode.id
	}

	/** 记录用户反馈 */
	recordFeedback(episodeId, feedback) {
		const ep = this.bank.episodicMemory.find((e) => e.id === episodeId)
		if (ep) {
			ep.userFeedback = feedback
			this._save()
		}
	}

	/** 记录对比意图 */
	recordCompare({ schools, majors, context = {} }) {
		const episode = {
			id: randomUUID(),
			timestamp: new Date().toISOString(),
			type: "compare",
			context: {
				schools,
				majors,
				userIntent: context.userIntent || "compare",
				rawInput: context.rawInput || null,
			},
		}
		this.bank.episodicMemory.unshift(episode)
		this._pushWorkingId(episode.id)
		this.bank.workingMemory.currentTopic = "学校对比"
		this._save()
		return episode.id
	}

	// ─── Retrieval ──────────────────────────────────────────

	/** 按学校+专业精确查找历史 */
	findHistory(school, major, limit = 5) {
		return this.bank.episodicMemory
			.filter((e) => e.type === "query" && e.school === school && e.major === major)
			.slice(0, limit)
	}

	/** 查找用户查询过的所有学校 */
	getQueriedSchools() {
		const schools = new Map()
		for (const e of this.bank.episodicMemory) {
			if (e.type === "query" && e.school) {
				const key = e.school
				const existing = schools.get(key) || { count: 0, lastQuery: e.timestamp, majors: new Set() }
				existing.count++
				existing.lastQuery = e.timestamp
				if (e.major) existing.majors.add(e.major)
				schools.set(key, existing)
			}
		}
		return Array.from(schools.entries())
			.map(([school, data]) => ({ school, count: data.count, lastQuery: data.lastQuery, majors: Array.from(data.majors) }))
			.sort((a, b) => new Date(b.lastQuery) - new Date(a.lastQuery))
	}

	/** 查找用户查询过的所有专业 */
	getQueriedMajors() {
		const majors = new Map()
		for (const e of this.bank.episodicMemory) {
			if (e.type === "query" && e.major) {
				const key = e.major
				const existing = majors.get(key) || { count: 0, lastQuery: e.timestamp, schools: new Set() }
				existing.count++
				existing.lastQuery = e.timestamp
				if (e.school) existing.schools.add(e.school)
				majors.set(key, existing)
			}
		}
		return Array.from(majors.entries())
			.map(([major, data]) => ({ major, count: data.count, lastQuery: data.lastQuery, schools: Array.from(data.schools) }))
			.sort((a, b) => b.count - a.count)
	}

	/** 获取最近查询 */
	getRecentQueries(limit = 5) {
		return this.bank.episodicMemory.filter((e) => e.type === "query").slice(0, limit)
	}

	/** 获取当前会话上下文 */
	getSessionContext() {
		const wm = this.bank.workingMemory
		const recent = wm.recentQueryIds
			.map((id) => this.bank.episodicMemory.find((e) => e.id === id))
			.filter(Boolean)
		return {
			sessionId: wm.currentSessionId,
			sessionStart: wm.sessionStart,
			currentTopic: wm.currentTopic,
			recentQueries: recent,
			pendingComparisons: wm.pendingComparisons,
		}
	}

	/** 查找相似查询（基于学校/专业关键词） */
	findSimilar(school, major, limit = 3) {
		const targets = [school, major].filter(Boolean)
		if (targets.length === 0) return []

		const scored = this.bank.episodicMemory
			.filter((e) => e.type === "query")
			.map((e) => {
				let score = 0
				if (e.school && school && (e.school.includes(school) || school.includes(e.school))) score += 2
				if (e.major && major && (e.major.includes(major) || major.includes(e.major))) score += 2
				// 时间衰减
				const daysAgo = (Date.now() - new Date(e.timestamp).getTime()) / (1000 * 60 * 60 * 24)
				score *= Math.exp(-daysAgo / DECAY_DAYS)
				return { episode: e, score }
			})
			.filter((x) => x.score > 0.5)
			.sort((a, b) => b.score - a.score)

		return scored.slice(0, limit).map((x) => x.episode)
	}

	// ─── Semantic Memory ────────────────────────────────────

	/** 获取用户画像 */
	getUserProfile() {
		return this.bank.semanticMemory.userProfile
	}

	/** 获取推断事实 */
	getInferredFacts(category = null, minConfidence = 0.5) {
		let facts = this.bank.semanticMemory.inferredFacts
		if (category) facts = facts.filter((f) => f.category === category)
		return facts.filter((f) => f.confidence >= minConfidence).sort((a, b) => b.confidence - a.confidence)
	}

	/** 显式更新用户画像 */
	updateUserProfile(updates) {
		const profile = this.bank.semanticMemory.userProfile
		for (const [key, value] of Object.entries(updates)) {
			if (Array.isArray(value) && Array.isArray(profile[key])) {
				profile[key] = [...new Set([...profile[key], ...value])]
			} else {
				profile[key] = value
			}
		}
		this._save()
	}

	// ─── Procedural Memory ──────────────────────────────────

	/** 记录输出格式偏好 */
	recordFormatPreference(format) {
		this.bank.proceduralMemory.preferredOutputFormat = format
		this._save()
	}

	/** 记录数据源偏好 */
	recordDataSourcePreference(source) {
		const prefs = this.bank.proceduralMemory.dataSourcePreference
		if (!prefs.includes(source)) {
			prefs.unshift(source)
			if (prefs.length > 5) prefs.pop()
		}
		this._save()
	}

	/** 记录查询模式 */
	recordQueryPattern(rawInput) {
		if (!rawInput) return
		const patterns = this.bank.proceduralMemory.queryPatterns
		// 简单归一化：提取"学校+专业"模式
		const normalized = rawInput.replace(/[查一下告诉我想知道]/g, "").trim()
		const existing = patterns.find((p) => p.pattern === normalized)
		if (existing) {
			existing.count++
		} else {
			patterns.push({ pattern: normalized, count: 1 })
			if (patterns.length > 20) patterns.shift()
		}
		this._save()
	}

	// ─── Compression & Inference ────────────────────────────

	/** 压缩情景记忆：合并相似查询，保留代表性样本 */
	_compressEpisodic() {
		const eps = this.bank.episodicMemory
		if (eps.length <= MAX_EPISODES) return

		// 按 (school, major) 分组，每组保留最新 + 最有反馈价值的
		const groups = new Map()
		for (const e of eps) {
			if (e.type !== "query" || !e.school) continue
			const key = `${e.school}::${e.major || ""}`
			if (!groups.has(key)) groups.set(key, [])
			groups.get(key).push(e)
		}

		const kept = []
		// 非查询类型全部保留
		for (const e of eps) {
			if (e.type !== "query") kept.push(e)
		}

		// 每组保留最新 2 条 + 有反馈的
		for (const groupEps of groups.values()) {
			const sorted = groupEps.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
			const withFeedback = sorted.filter((e) => e.userFeedback !== null)
			const latest = sorted.slice(0, 2)
			kept.push(...latest)
			for (const e of withFeedback) {
				if (!kept.some((k) => k.id === e.id)) kept.push(e)
			}
		}

		// 去重 + 时间排序 + 截断
		const unique = []
		const seen = new Set()
		for (const e of kept.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))) {
			if (!seen.has(e.id)) {
				seen.add(e.id)
				unique.push(e)
			}
		}

		this.bank.episodicMemory = unique.slice(0, MAX_EPISODES)
	}

	/** 从情景记忆推断语义事实 */
	_inferSemantics() {
		const eps = this.bank.episodicMemory.filter((e) => e.type === "query")
		const profile = this.bank.semanticMemory.userProfile
		const facts = this.bank.semanticMemory.inferredFacts

		// 1. 推断目标层次
		const tierCounts = { 985: 0, 211: 0, doubleFirst: 0, normal: 0 }
		for (const e of eps) {
			if (!e.school) continue
			const sNorm = e.school.replace(/大学|学院|研究所/g, "")
			const tier = inferSchoolTier(e.school)
			if (tier) tierCounts[tier] = (tierCounts[tier] || 0) + 1
		}
		const total = Object.values(tierCounts).reduce((a, b) => a + b, 0)
		if (total >= INFER_THRESHOLD) {
			const preferred = Object.entries(tierCounts)
				.filter(([, c]) => c >= 2)
				.map(([t]) => t)
			if (preferred.length > 0) {
				profile.targetTier = [...new Set([...(profile.targetTier || []), ...preferred])]
				upsertFact(facts, "用户倾向于报考 " + preferred.map(tierLabel).join("、") + " 院校", "preference", preferred.length / total, eps.slice(0, 5).map((e) => e.id))
			}
		}

		// 2. 推断地域偏好
		const regionCounts = new Map()
		for (const e of eps) {
			if (!e.school) continue
			const region = inferRegion(e.school)
			if (region) regionCounts.set(region, (regionCounts.get(region) || 0) + 1)
		}
		for (const [region, count] of regionCounts.entries()) {
			if (count >= 2) {
				profile.preferredRegions = [...new Set([...(profile.preferredRegions || []), region])]
				upsertFact(facts, `用户关注 ${region} 地区院校`, "preference", Math.min(count / 5, 0.95), eps.filter((e) => inferRegion(e.school) === region).map((e) => e.id))
			}
		}

		// 3. 推断专业方向
		const majorCounts = new Map()
		for (const e of eps) {
			if (!e.major) continue
			const cat = inferMajorCategory(e.major)
			if (cat) majorCounts.set(cat, (majorCounts.get(cat) || 0) + 1)
		}
		for (const [cat, count] of majorCounts.entries()) {
			if (count >= 2) {
				profile.preferredMajorCategories = [...new Set([...(profile.preferredMajorCategories || []), cat])]
				upsertFact(facts, `用户倾向于 ${cat} 类专业`, "preference", Math.min(count / 5, 0.95), eps.filter((e) => inferMajorCategory(e.major) === cat).map((e) => e.id))
			}
		}

		// 4. 推断风险承受度
		const heats = eps.filter((e) => e.result?.compositeHeat !== undefined).map((e) => e.result.compositeHeat)
		if (heats.length >= INFER_THRESHOLD) {
			const avgHeat = heats.reduce((a, b) => a + b, 0) / heats.length
			let tolerance = "medium"
			if (avgHeat > 75) tolerance = "high"
			else if (avgHeat < 45) tolerance = "low"
			profile.riskTolerance = tolerance
			upsertFact(facts, `用户风险承受度为 ${toleranceLabel(tolerance)}`, "behavior", Math.min(heats.length / 8, 0.9), eps.slice(0, 5).map((e) => e.id))
		}

		// 5. 高频学校/专业 → preferred
		const schoolFreq = new Map()
		const majorFreq = new Map()
		for (const e of eps) {
			if (e.school) schoolFreq.set(e.school, (schoolFreq.get(e.school) || 0) + 1)
			if (e.major) majorFreq.set(e.major, (majorFreq.get(e.major) || 0) + 1)
		}
		for (const [school, count] of schoolFreq.entries()) {
			if (count >= 3) {
				profile.preferredSchools = [...new Set([...(profile.preferredSchools || []), school])]
				upsertFact(facts, `用户多次查询 ${school}，可能是目标院校`, "goal", Math.min(count / 6, 0.95), eps.filter((e) => e.school === school).map((e) => e.id))
			}
		}
		for (const [major, count] of majorFreq.entries()) {
			if (count >= 3) {
				upsertFact(facts, `用户多次查询 ${major}，可能是意向专业`, "goal", Math.min(count / 6, 0.95), eps.filter((e) => e.major === major).map((e) => e.id))
			}
		}
	}

	// ─── Export / Summary ───────────────────────────────────

	/** 生成记忆摘要（供 LLM 上下文使用） */
	generateContextSummary() {
		const profile = this.bank.semanticMemory.userProfile
		const facts = this.bank.semanticMemory.inferredFacts
		const recent = this.getRecentQueries(3)
		const queriedSchools = this.getQueriedSchools().slice(0, 5)
		const queriedMajors = this.getQueriedMajors().slice(0, 5)

		let summary = "## 用户记忆摘要\n\n"

		if (profile.targetTier?.length > 0) {
			summary += `**目标层次**: ${profile.targetTier.map(tierLabel).join("、")}\n`
		}
		if (profile.preferredRegions?.length > 0) {
			summary += `**关注地区**: ${profile.preferredRegions.join("、")}\n`
		}
		if (profile.preferredMajorCategories?.length > 0) {
			summary += `**专业方向**: ${profile.preferredMajorCategories.join("、")}\n`
		}
		if (profile.riskTolerance) {
			summary += `**风险承受**: ${toleranceLabel(profile.riskTolerance)}\n`
		}
		if (profile.preferredSchools?.length > 0) {
			summary += `**意向院校**: ${profile.preferredSchools.join("、")}\n`
		}

		const topFacts = facts.filter((f) => f.confidence >= 0.7).slice(0, 5)
		if (topFacts.length > 0) {
			summary += `\n**关键推断**:\n`
			for (const f of topFacts) {
				summary += `- ${f.fact}（置信度 ${(f.confidence * 100).toFixed(0)}%）\n`
			}
		}

		if (recent.length > 0) {
			summary += `\n**最近查询**:\n`
			for (const e of recent) {
				const date = new Date(e.timestamp).toLocaleDateString("zh-CN")
				summary += `- ${date}: ${e.school} ${e.major}（${e.result?.heatLevel || "未知"}）\n`
			}
		}

		if (queriedSchools.length > 0) {
			summary += `\n**查询过的学校**（按时间）: ${queriedSchools.map((s) => s.school).join("、")}\n`
		}
		if (queriedMajors.length > 0) {
			summary += `**查询过的专业**（按频次）: ${queriedMajors.map((m) => m.major).join("、")}\n`
		}

		const wm = this.bank.workingMemory
		if (wm.currentTopic) {
			summary += `\n**当前话题**: ${wm.currentTopic}\n`
		}
		if (wm.pendingComparisons.length > 0) {
			summary += `**待对比**: ${wm.pendingComparisons.map((p) => `${p.school}${p.major ? " " + p.major : ""}`).join("、")}\n`
		}

		return summary
	}

	/** 导出完整记忆（用于备份/迁移） */
	exportBank() {
		return JSON.parse(JSON.stringify(this.bank))
	}

	/** 导入记忆（用于恢复/迁移） */
	importBank(data) {
		this.bank = migrateIfNeeded(data)
		this._save()
	}

	/** 清空记忆 */
	clear() {
		this.bank = createEmptyBank()
		this._save()
	}
}

// ═══════════════════════════════════════════════════════════
// Inference Helpers（纯启发式，零外部依赖）
// ═══════════════════════════════════════════════════════════

const TIER_985 = new Set([
	"北京大学","清华大学","复旦大学","上海交通大学","浙江大学","南京大学","中国科学技术大学","哈尔滨工业大学",
	"西安交通大学","北京航空航天大学","北京理工大学","南开大学","天津大学","东南大学","武汉大学","华中科技大学",
	"吉林大学","厦门大学","山东大学","中南大学","大连理工大学","电子科技大学","华东师范大学","四川大学",
	"重庆大学","湖南大学","东北大学","兰州大学","中国海洋大学","西北农林科技大学","中央民族大学",
	"中国人民大学","中山大学","同济大学","北京师范大学","国防科技大学","华南理工大学","西北工业大学",
	"中国农业大学","华东师范大学",
])

const TIER_211 = new Set([
	"上海财经大学","中央财经大学","对外经济贸易大学","北京邮电大学","西安电子科技大学","中国政法大学",
	"北京外国语大学","上海外国语大学","南京航空航天大学","南京理工大学","苏州大学","暨南大学",
	"华中师范大学","西南大学","东北师范大学","陕西师范大学","华南师范大学","湖南师范大学",
	"南京师范大学","华东理工大学","河海大学","江南大学","中国矿业大学","南京农业大学",
	"合肥工业大学","西南交通大学","武汉理工大学","华中农业大学","中南财经政法大学",
	"福州大学","南昌大学","云南大学","广西大学","贵州大学","海南大学","辽宁大学",
	"安徽大学","郑州大学","新疆大学","石河子大学","西藏大学","青海大学","宁夏大学",
	"内蒙古大学","延边大学","东北林业大学","东北农业大学","四川农业大学",
])

const REGION_MAP = [
	{ regs: ["北京","清华","北大","人大","北航","北理","北邮","中农","北师","北外","中政"], region: "北京" },
	{ regs: ["上海","复旦","交大","同济","华东","上财","上外"], region: "上海" },
	{ regs: ["南京","东南","南大","南航","南理","河海","南师","南农","中国药科"], region: "江苏" },
	{ regs: ["浙江","浙大"], region: "浙江" },
	{ regs: ["山东","山大","中国海洋"], region: "山东" },
	{ regs: ["广东","中大","华南","暨南","南方"], region: "广东" },
	{ regs: ["湖北","武大","华中","武汉","中南财"], region: "湖北" },
	{ regs: ["湖南","中南"], region: "湖南" },
	{ regs: ["四川","川大","电子","西南"], region: "四川" },
	{ regs: ["陕西","西安","西北","陕西师"], region: "陕西" },
	{ regs: ["天津","南开","天大"], region: "天津" },
	{ regs: ["福建","厦大","福州"], region: "福建" },
	{ regs: ["安徽","中科大","合肥"], region: "安徽" },
	{ regs: ["重庆","重大"], region: "重庆" },
	{ regs: ["辽宁","大连","东北"], region: "辽宁" },
	{ regs: ["吉林","吉大"], region: "吉林" },
	{ regs: ["黑龙江","哈工大","哈工程"], region: "黑龙江" },
]

const MAJOR_CATEGORIES = [
	{ cats: ["哲学","逻辑学","宗教学","伦理学"], name: "哲学" },
	{ cats: ["经济","金融","财政","税务","国贸","统计"], name: "经济学" },
	{ cats: ["法学","政治","社会","民族","马克思","公安"], name: "法学" },
	{ cats: ["教育","心理","体育"], name: "教育学" },
	{ cats: ["文学","语言","新闻","传播","翻译"], name: "文学" },
	{ cats: ["历史","考古","文博"], name: "历史学" },
	{ cats: ["数学","物理","化学","天文","地理","大气","海洋","生物","生态","统计"], name: "理学" },
	{ cats: ["力学","机械","仪器","材料","电气","电子","信息","控制","计算机","建筑","土木","水利","化工","能源","交通","船舶","航空","农业","林业","环境","生物工程","食品","安全"], name: "工学" },
	{ cats: ["农学","园艺","植保","畜牧","兽医","水产"], name: "农学" },
	{ cats: ["基础医学","临床","口腔","公卫","中医","药学","护理","中药"], name: "医学" },
	{ cats: ["工商管理","管理","会计","旅游","图书情报","工程管理"], name: "管理学" },
	{ cats: ["艺术","音乐","美术","设计","戏剧","电影"], name: "艺术学" },
]

function inferSchoolTier(name) {
	for (const s of TIER_985) {
		if (name.includes(s)) return "985"
	}
	for (const s of TIER_211) {
		if (name.includes(s)) return "211"
	}
	if (name.includes("双一流") || name.includes("一流学科")) return "doubleFirst"
	return "normal"
}

function inferRegion(name) {
	for (const r of REGION_MAP) {
		for (const reg of r.regs) {
			if (name.includes(reg)) return r.region
		}
	}
	return null
}

function inferMajorCategory(name) {
	for (const cat of MAJOR_CATEGORIES) {
		for (const keyword of cat.cats) {
			if (name.includes(keyword)) return cat.name
		}
	}
	return null
}

function tierLabel(tier) {
	const map = { 985: "985", 211: "211", doubleFirst: "双一流", normal: "普通院校" }
	return map[tier] || tier
}

function toleranceLabel(t) {
	const map = { low: "保守型（偏好冷门）", medium: "稳健型", high: "激进型（接受卷王）" }
	return map[t] || t
}

function upsertFact(facts, text, category, confidence, sources) {
	const existing = facts.find((f) => f.fact === text)
	const now = new Date().toISOString()
	if (existing) {
		existing.confidence = Math.max(existing.confidence, confidence)
		existing.evidence = Math.max(existing.evidence, sources?.length || 1)
		existing.lastConfirmed = now
		if (sources) existing.sources = [...new Set([...existing.sources, ...sources])]
	} else {
		facts.push({
			fact: text,
			category,
			confidence,
			evidence: sources?.length || 1,
			firstSeen: now,
			lastConfirmed: now,
			sources: sources || [],
		})
	}
}

// ═══════════════════════════════════════════════════════════
// Export
// ═══════════════════════════════════════════════════════════

export { KaoyanMemory, MEMORY_FILE }
export default KaoyanMemory
