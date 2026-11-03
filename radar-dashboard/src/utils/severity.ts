import type { FindingReport } from '@/api/client'

export type Severity = FindingReport['severity']

export const SEVERITY_ORDER: Severity[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']

/** A FALSE_POSITIVE verdict takes a finding out of the score and of every finding count. */
export function isFalsePositive(finding: FindingReport): boolean {
  return finding.human_verdict === 'FALSE_POSITIVE'
}
