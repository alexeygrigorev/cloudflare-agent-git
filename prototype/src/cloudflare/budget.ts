export interface BudgetConfig {
  maxDailyOps: number;
  maxMonthlyOps: number;
  maxRepos: number;
  maxTotalBytes: number;
  maxBodyBytes: number;
}

export const HARD_CEILINGS: BudgetConfig = {
  maxDailyOps: 200,
  maxMonthlyOps: 6000,
  maxRepos: 4,
  maxTotalBytes: 16 * 1024 * 1024, // 16 MiB
  maxBodyBytes: 256 * 1024, // 256 KiB
};

export class BudgetError extends Error {
  constructor(message: string, public status: number = 429) {
    super(message);
    this.name = "BudgetError";
  }
}

export function parseConfigLimit(raw: unknown, name: string, ceiling: number): number {
  if (raw === undefined) {
    return ceiling;
  }
  if (typeof raw !== "number" && typeof raw !== "string") {
    throw new BudgetError(`Invalid config: ${name} must be a non-negative integer`, 503);
  }
  if (typeof raw === "string" && raw.trim() === "") {
    throw new BudgetError(`Invalid config: ${name} must be a non-negative integer`, 503);
  }
  const num = typeof raw === "number" ? raw : Number(raw);
  if (!Number.isFinite(num) || Number.isNaN(num) || !Number.isInteger(num) || num < 0) {
    throw new BudgetError(`Invalid config: ${name} must be a non-negative integer`, 503);
  }
  // Lower numeric caps are allowed; hard ceiling is enforced (no bypass)
  return Math.min(num, ceiling);
}

export interface BudgetEnvConfig {
  maxDailyOps?: unknown;
  maxMonthlyOps?: unknown;
  maxRepos?: unknown;
  maxTotalBytes?: unknown;
  maxBodyBytes?: unknown;
}

export class BudgetTracker {
  public readonly config: BudgetConfig;

  constructor(private state: DurableObjectState, envConfig?: BudgetEnvConfig) {
    this.config = {
      maxDailyOps: parseConfigLimit(envConfig?.maxDailyOps, "MAX_DAILY_OPS", HARD_CEILINGS.maxDailyOps),
      maxMonthlyOps: parseConfigLimit(envConfig?.maxMonthlyOps, "MAX_MONTHLY_OPS", HARD_CEILINGS.maxMonthlyOps),
      maxRepos: parseConfigLimit(envConfig?.maxRepos, "MAX_REPOS", HARD_CEILINGS.maxRepos),
      maxTotalBytes: parseConfigLimit(envConfig?.maxTotalBytes, "MAX_TOTAL_BYTES", HARD_CEILINGS.maxTotalBytes),
      maxBodyBytes: parseConfigLimit(envConfig?.maxBodyBytes, "MAX_BODY_BYTES", HARD_CEILINGS.maxBodyBytes),
    };
  }

  private getUtcDay(date: Date): string {
    const pad = (n: number) => n.toString().padStart(2, "0");
    return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
  }

  private getUtcMonth(date: Date): string {
    const pad = (n: number) => n.toString().padStart(2, "0");
    return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}`;
  }

  private validateCounter(val: unknown, name: string): number {
    if (val === undefined) {
      return 0;
    }
    if (val === null || typeof val !== "number" || !Number.isFinite(val) || !Number.isInteger(val) || val < 0) {
      throw new BudgetError(`Corrupted counter state for ${name}`, 503);
    }
    return val;
  }

  async reserveOp(): Promise<void> {
    const now = new Date();
    const day = this.getUtcDay(now);
    const month = this.getUtcMonth(now);

    const dayKey = `budget:ops:day:${day}`;
    const monthKey = `budget:ops:month:${month}`;

    await this.state.storage.transaction(async (txn) => {
      let dayCount: number;
      let monthCount: number;
      try {
        dayCount = this.validateCounter(await txn.get(dayKey), dayKey);
        monthCount = this.validateCounter(await txn.get(monthKey), monthKey);
      } catch (err) {
        if (err instanceof BudgetError) throw err;
        throw new BudgetError("Store error during get", 503);
      }

      if (dayCount >= this.config.maxDailyOps) {
        throw new BudgetError(`Budget exceeded: max daily ops (${this.config.maxDailyOps})`, 429);
      }
      if (monthCount >= this.config.maxMonthlyOps) {
        throw new BudgetError(`Budget exceeded: max monthly ops (${this.config.maxMonthlyOps})`, 429);
      }

      try {
        await txn.put(dayKey, dayCount + 1);
        await txn.put(monthKey, monthCount + 1);
      } catch (err) {
        throw new BudgetError("Store error during put", 503);
      }
    });
  }

  async reserveBytes(bytes: number): Promise<void> {
    if (typeof bytes !== "number" || !Number.isFinite(bytes) || !Number.isInteger(bytes) || bytes < 0) {
      throw new BudgetError("Invalid bytes requested", 503);
    }
    if (bytes === 0) return;
    const bytesKey = `budget:bytes:total`;

    await this.state.storage.transaction(async (txn) => {
      let totalBytes: number;
      try {
        totalBytes = this.validateCounter(await txn.get(bytesKey), bytesKey);
      } catch (err) {
        if (err instanceof BudgetError) throw err;
        throw new BudgetError("Store error during get", 503);
      }

      if (totalBytes + bytes > this.config.maxTotalBytes) {
        throw new BudgetError(`Budget exceeded: max total bytes (${this.config.maxTotalBytes})`, 429);
      }
      try {
        await txn.put(bytesKey, totalBytes + bytes);
      } catch (err) {
        throw new BudgetError("Store error during put", 503);
      }
    });
  }

  async reserveRepoSlot(repoName: string): Promise<void> {
    if (!repoName || typeof repoName !== "string") {
      throw new BudgetError("Invalid repo name", 503);
    }
    await this.state.storage.transaction(async (txn) => {
      let reposMap;
      try {
        reposMap = await txn.list({ prefix: "repo:" });
      } catch (err) {
        throw new BudgetError("Store error during list", 503);
      }
      const uniqueRepos = new Set<string>();
      for (const key of reposMap.keys()) {
        const m = /^repo:([^:]+):(upstream|pending)$/.exec(key);
        if (m) {
          uniqueRepos.add(m[1]);
        }
      }
      if (uniqueRepos.has(repoName)) {
        throw new BudgetError(`Repo slot already reserved: ${repoName}`, 409);
      }
      if (uniqueRepos.size >= this.config.maxRepos) {
        throw new BudgetError(`Budget exceeded: max repos (${this.config.maxRepos})`, 429);
      }
      try {
        await txn.put(`repo:${repoName}:pending`, {
          reservedAt: Date.now(),
        });
      } catch (err) {
        throw new BudgetError("Store error during put", 503);
      }
    });
  }

  async getStats(): Promise<{
    utcDayOps: number;
    calendarMonthOps: number;
    totalBytesUploaded: number;
    repoCount: number;
    dailyCap: number;
    monthlyCap: number;
    maxRepos: number;
    maxTotalBytes: number;
    maxBodyBytes: number;
    remainingDayOps: number;
    remainingMonthOps: number;
    remainingRepos: number;
    remainingTotalBytes: number;
  }> {
    const now = new Date();
    const day = this.getUtcDay(now);
    const month = this.getUtcMonth(now);

    const dayKey = `budget:ops:day:${day}`;
    const monthKey = `budget:ops:month:${month}`;
    const bytesKey = `budget:bytes:total`;

    let dayCount = 0;
    let monthCount = 0;
    let totalBytes = 0;
    let repoCount = 0;

    await this.state.storage.transaction(async (txn) => {
      dayCount = this.validateCounter(await txn.get(dayKey), dayKey);
      monthCount = this.validateCounter(await txn.get(monthKey), monthKey);
      totalBytes = this.validateCounter(await txn.get(bytesKey), bytesKey);
      const reposMap = await txn.list({ prefix: "repo:" });
      const uniqueRepos = new Set<string>();
      for (const key of reposMap.keys()) {
        const m = /^repo:([^:]+):(upstream|pending)$/.exec(key);
        if (m) uniqueRepos.add(m[1]);
      }
      repoCount = uniqueRepos.size;
    });

    return {
      utcDayOps: dayCount,
      calendarMonthOps: monthCount,
      totalBytesUploaded: totalBytes,
      repoCount: repoCount,
      dailyCap: this.config.maxDailyOps,
      monthlyCap: this.config.maxMonthlyOps,
      maxRepos: this.config.maxRepos,
      maxTotalBytes: this.config.maxTotalBytes,
      maxBodyBytes: this.config.maxBodyBytes,
      remainingDayOps: Math.max(0, this.config.maxDailyOps - dayCount),
      remainingMonthOps: Math.max(0, this.config.maxMonthlyOps - monthCount),
      remainingRepos: Math.max(0, this.config.maxRepos - repoCount),
      remainingTotalBytes: Math.max(0, this.config.maxTotalBytes - totalBytes),
    };
  }
}
