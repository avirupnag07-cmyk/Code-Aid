export type Evidence = {
  file?: string | null
  line?: number | null
  end_line?: number | null
  snippet?: string | null
  reason: string
}

export type Fact = { text: string; evidence: Evidence[] }

export type Finding = {
  text: string
  severity: 'info' | 'low' | 'medium' | 'high' | string
  rule_id: string
  evidence: Evidence[]
}

export type LanguageDiagnostic = {
  language: string
  path: string
  line?: number | null
  column?: number | null
  severity: string
  message: string
  tool: string
  code: string
  source: string
}

export type Hypothesis = {
  text: string
  score: number
  rationale: string
  evidence: Evidence[]
}

export type GeneratedTest = {
  path: string
  content: string
  purpose: string
  validation_status: string
  validation_message: string
  test_mode: string
}

export type ExecutionResult = {
  status: string
  exit_code: number | null
  stdout: string
  stderr: string
  duration_ms: number | null
  reason: string
  command: string[]
  started_at?: string | null
  finished_at?: string | null
}

export type VerificationCheck = {
  name: string
  status: string
  message: string
  evidence: Evidence[]
}

export type VerificationResult = {
  status: string
  file_path?: string | null
  changed: boolean
  safe_to_apply: boolean
  syntax_valid?: boolean | null
  diff: string
  message: string
  checks: VerificationCheck[]
  baseline_execution?: ExecutionResult | null
  patched_execution?: ExecutionResult | null
  original_failure_reproduced?: boolean | null
  failure_disappeared?: boolean | null
  regressions_detected?: boolean | null
}

export type InvestigationResults = {
  facts: Fact[]
  findings: Finding[]
  hypotheses: Hypothesis[]
  generated_tests: GeneratedTest[]
  execution_results: ExecutionResult[]
  verification: VerificationResult
  detected_languages?: string[]
  diagnostics?: LanguageDiagnostic[]
  language_diagnostics?: LanguageDiagnostic[]
  language_analysis?: Record<string, unknown>
}

export type SourceInfo = {
  source_type: string
  sample_id?: string | null
  original_filename?: string | null
  file_count: number
  traceback: string
  metadata: Record<string, unknown>
  intake: Record<string, string>
  files: SourceFile[]
  detected_languages?: string[]
  repository?: RepositoryMetadata | null
}

export type RepositoryMetadata = {
  provider: string
  url: string
  owner: string
  name: string
  ref: string
  sha: string
  subdirectory?: string | null
  imported_at: string
}

export type SourceFile = { path: string; kind: string; size: number }

export type InvestigationSummary = {
  id: string
  title: string
  status: string
  source_type: string
  sample_id?: string | null
  created_at: string
  updated_at: string
  finding_count: number
  hypothesis_count: number
}

export type Investigation = InvestigationSummary & {
  source: SourceInfo
  results: InvestigationResults
}

export type Sample = {
  id: string
  name: string
  description: string
  category: string
  exception_type: string
  traceback: string
  file_count: number
  metadata: Record<string, unknown>
}

export type CreateInvestigationInput = {
  title: string
  bugDescription: string
  traceback: string
  sampleId: string
  reproductionSteps: string
  expectedBehavior: string
  actualBehavior: string
  environment: string
  archive: File | null
  repositoryUrl?: string
  repositoryRef?: string
  repositorySubdirectory?: string
}

export type GitHubStatus = { provider: 'github'; configured: boolean; connected: boolean; message: string }
export type GitHubRepository = { id: number; full_name: string; private: boolean; clone_url: string; default_branch: string }

export type LanguageSupport = {
  id: string
  name: string
  extensions: string[]
  status: string
  detection: string
  syntax?: string
  analysis: string
  diagnostics?: string
  test_generation?: string
  execution: string
  notes?: string
}

export type LanguagesResponse = LanguageSupport[] | { languages?: LanguageSupport[]; supported?: LanguageSupport[] }
