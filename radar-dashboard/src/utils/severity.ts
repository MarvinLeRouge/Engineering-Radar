import type { FindingReport } from '@/api/client'

export type Severity = FindingReport['severity']

export const SEVERITY_ORDER: Severity[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
