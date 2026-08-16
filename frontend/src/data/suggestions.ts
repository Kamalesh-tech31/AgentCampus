import { AppMode } from '../types';

export interface SuggestionItem {
  id: string;
  category: string;
  prompt: string;
  description: string;
  iconType?: 'analytics' | 'ranking' | 'risk' | 'search' | 'mutation';
}

export const SUGGESTIONS_CATALOG: Record<AppMode, SuggestionItem[]> = {
  analyze: [
    {
      id: 'an-1',
      category: 'Risk Assessment',
      prompt: 'Find academically at-risk students and explain reasons',
      description: 'Identifies students below CGPA and attendance thresholds with factor analysis',
      iconType: 'risk'
    },
    {
      id: 'an-2',
      category: 'Weighted Ranking',
      prompt: 'Rank the top 10 students using 80% marks and 20% attendance',
      description: 'Computes normalized composite scores and ranks top performers',
      iconType: 'ranking'
    },
    {
      id: 'an-3',
      category: 'Correlation Analysis',
      prompt: 'Analyze attendance correlation with CGPA and create a detailed report',
      description: 'Calculates Pearson r, linear regression slope, and scatter fit',
      iconType: 'analytics'
    },
    {
      id: 'an-4',
      category: 'Department Benchmarking',
      prompt: 'Compare Computer Science and Electronics department performance',
      description: 'Evaluates cohort averages, grade distributions, and attendance rates',
      iconType: 'analytics'
    },
    {
      id: 'an-5',
      category: 'Ranking by Attribute',
      prompt: 'Show top 10 students ranked by attendance with CGPA above 8.0',
      description: 'Multi-criteria sorting with minimum threshold filters',
      iconType: 'ranking'
    },
    {
      id: 'an-6',
      category: 'Backlog Impact',
      prompt: 'Analyze performance distribution for students with active backlogs',
      description: 'Statistical breakdown of academic delay across semesters',
      iconType: 'risk'
    }
  ],
  explore: [
    {
      id: 'ex-1',
      category: 'Top Performers',
      prompt: 'Show the top 10 CSE students',
      description: 'Lists highest CGPA students in Computer Science',
      iconType: 'search'
    },
    {
      id: 'ex-2',
      category: 'High Honor Filter',
      prompt: 'Find all students with CGPA above 9.0',
      description: 'Filters honor roll candidates across all engineering branches',
      iconType: 'search'
    },
    {
      id: 'ex-3',
      category: 'Attendance Monitor',
      prompt: 'List all students in Electronics with attendance below 75%',
      description: 'Identifies attendance shortage before semester exams',
      iconType: 'search'
    },
    {
      id: 'ex-4',
      category: 'Full Cohort View',
      prompt: 'Show all active students ordered by roll number',
      description: 'Retrieves active student roster in numerical order',
      iconType: 'search'
    },
    {
      id: 'ex-5',
      category: 'Clean Record Check',
      prompt: 'Find students in Mechanical department with zero backlogs',
      description: 'Clear record verification for campus placement eligibility',
      iconType: 'search'
    }
  ],
  modify: [
    {
      id: 'mo-1',
      category: 'Individual Update',
      prompt: "Change Rahul's CGPA to 9.2",
      description: 'Updates a specific student record after re-evaluation',
      iconType: 'mutation'
    },
    {
      id: 'mo-2',
      category: 'Attendance Adjustment',
      prompt: "Update Arun's attendance to 95%",
      description: 'Corrects verified medical absence attendance',
      iconType: 'mutation'
    },
    {
      id: 'mo-3',
      category: 'Bulk Department Update',
      prompt: 'Increase attendance of all CSE students by 5%',
      description: 'Applies event credit across an entire department cohort',
      iconType: 'mutation'
    },
    {
      id: 'mo-4',
      category: 'Safe Deletion',
      prompt: 'Delete all students with CGPA below 5',
      description: 'Requires explicit safety confirmation before removal',
      iconType: 'mutation'
    },
    {
      id: 'mo-5',
      category: 'New Enrollment',
      prompt: 'Add new student Ananya Roy in Computer Science with 9.1 CGPA',
      description: 'Inserts newly admitted transfer student with full profile',
      iconType: 'mutation'
    }
  ]
};

/**
 * Returns fresh contextual suggestions for the current mode,
 * dynamically excluding any prompts that have already been executed in recent history.
 */
export function getFreshSuggestions(
  mode: AppMode,
  usedPrompts: string[] = [],
  limit: number = 4
): SuggestionItem[] {
  const pool = SUGGESTIONS_CATALOG[mode] || SUGGESTIONS_CATALOG.explore;
  const normalizedUsed = new Set(
    usedPrompts.map(p => p.trim().toLowerCase().replace(/[.,/#!$%^&*;:{}=\-_`~()]/g, ''))
  );

  const unused = pool.filter(item => {
    const normalizedItem = item.prompt.trim().toLowerCase().replace(/[.,/#!$%^&*;:{}=\-_`~()]/g, '');
    return !normalizedUsed.has(normalizedItem);
  });

  // If all suggestions have been used, loop back to the pool to prevent empty state
  const result = unused.length > 0 ? unused : pool;
  return result.slice(0, limit);
}
