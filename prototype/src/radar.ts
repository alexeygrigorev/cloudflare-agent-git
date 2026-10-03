export type HeadVector = Record<string, string>;

export interface HeadChange {
  agent: string;
  ref: string;
  sha: string;
  before: string | null;
}

export interface RadarPairCheck {
  pair: [string, string];
  heads: { a: string; b: string };
  reason: string | null;
}

export interface Radar {
  onPush(change: HeadChange, heads: HeadVector, siblings: string[]): RadarPairCheck[];
}

export class StubRadar implements Radar {
  onPush(change: HeadChange, heads: HeadVector, siblings: string[]): RadarPairCheck[] {
    const checks: RadarPairCheck[] = [];
    for (const sibling of siblings) {
      if (sibling === change.agent) {
        continue;
      }
      const ownHead = heads[change.agent];
      const siblingHead = heads[sibling];
      checks.push({
        pair: [change.agent, sibling],
        heads: { a: ownHead, b: siblingHead },
        reason: ownHead !== siblingHead ? "heads-diverged" : null,
      });
    }
    return checks;
  }
}

export class SilentRadar implements Radar {
  onPush(_change: HeadChange, _heads: HeadVector, _siblings: string[]): RadarPairCheck[] {
    return [];
  }
}

export function radarFromEnv(value: string | undefined): Radar {
  return value === "silent" ? new SilentRadar() : new StubRadar();
}
