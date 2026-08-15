import { 
  AppMode, 
  OutputFormat, 
  OrchestrationResult, 
  DatabasePreviewResponse, 
  ColumnValidationResult, 
  StudentRecord 
} from '../types';

const API_BASE = '/api';

/**
 * Executes a synchronous pipeline request through the backend Mother Agent.
 */
export async function orchestrateSync(
  query: string,
  mode: AppMode,
  confirmed: boolean = false,
  outputFormat?: OutputFormat
): Promise<OrchestrationResult> {
  // If user selected a specific output format in Analyze mode, append guidance to prompt if not already present
  let formattedQuery = query;
  if (mode === 'analyze' && outputFormat && outputFormat !== 'text') {
    if (outputFormat === 'pdf' && !query.toLowerCase().includes('pdf')) {
      formattedQuery = `${query} in PDF`;
    } else if (outputFormat === 'ppt' && !query.toLowerCase().includes('ppt') && !query.toLowerCase().includes('powerpoint')) {
      formattedQuery = `${query} in PowerPoint`;
    } else if (outputFormat === 'excel' && !query.toLowerCase().includes('excel') && !query.toLowerCase().includes('spreadsheet')) {
      formattedQuery = `${query} in Excel`;
    }
  }

  const response = await fetch(`${API_BASE}/orchestrate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      user_query: formattedQuery,
      prompt: formattedQuery,
      mode: mode,
      confirmed: confirmed,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => 'Unknown server error');
    throw new Error(`Backend error (${response.status}): ${errorText}`);
  }

  return response.json();
}

/**
 * Fetches the live database preview across all tables.
 */
export async function fetchDatabasePreview(sampleSize: number = 5): Promise<DatabasePreviewResponse> {
  const response = await fetch(`${API_BASE}/database/preview?sample_size=${sampleSize}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch database preview: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetches table names from the database schema.
 */
export async function fetchDatabaseTables(): Promise<string[]> {
  const response = await fetch(`${API_BASE}/database/tables`);
  if (!response.ok) {
    throw new Error(`Failed to fetch database tables: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Validates a candidate column name against schema with fuzzy suggestions.
 */
export async function validateColumn(table: string, column: string): Promise<ColumnValidationResult> {
  const response = await fetch(`${API_BASE}/database/validate-column`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ table, column }),
  });
  if (!response.ok) {
    throw new Error(`Column validation failed: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Generates the direct download URL for a generated artifact.
 */
export function getFileDownloadUrl(fileName: string): string {
  const cleanName = fileName.replace(/^.*[\\\/]/, '');
  return `${API_BASE}/files/download/${encodeURIComponent(cleanName)}`;
}

/**
 * Fetches all student records.
 */
export async function fetchStudents(): Promise<StudentRecord[]> {
  const response = await fetch(`${API_BASE}/students`);
  if (!response.ok) {
    throw new Error(`Failed to fetch students: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Resets the student dataset to seed state.
 */
export async function resetDatabase(): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/students/reset`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`Failed to reset database: ${response.statusText}`);
  }
  return response.json();
}
