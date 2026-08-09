import { StudentRecord } from '../types';

export const INITIAL_STUDENTS: StudentRecord[] = [
  { id: 'STU-1001', rollNumber: '21CS001', name: 'Aarav Sharma', department: 'Computer Science', cgpa: 9.82, semester: 8, attendance: 96, email: 'aarav.sharma@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'Distributed Agent Orchestration' },
  { id: 'STU-1002', rollNumber: '21CS002', name: 'Ananya Roy', department: 'Computer Science', cgpa: 9.65, semester: 8, attendance: 94, email: 'ananya.roy@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'Neural LLM Compression' },
  { id: 'STU-1003', rollNumber: '21CS003', name: 'Rohan Verma', department: 'Computer Science', cgpa: 9.48, semester: 8, attendance: 91, email: 'rohan.verma@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'Vector DB Indexing' },
  { id: 'STU-1004', rollNumber: '21DS001', name: 'Priya Nair', department: 'Data Science', cgpa: 9.75, semester: 6, attendance: 98, email: 'priya.nair@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'Automated Anomaly Detection' },
  { id: 'STU-1005', rollNumber: '21AI001', name: 'Devansh Gupta', department: 'AI & ML', cgpa: 9.58, semester: 6, attendance: 92, email: 'devansh.g@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'Vision Transformer Benchmarks' },
  { id: 'STU-1006', rollNumber: '21CS004', name: 'Rahul Sharma', department: 'Computer Science', cgpa: 8.85, semester: 6, attendance: 88, email: 'rahul.s@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'Realtime WebRTC Audio Bridge' },
  { id: 'STU-1007', rollNumber: '21EC001', name: 'Diya Patel', department: 'Electronics', cgpa: 9.32, semester: 6, attendance: 95, email: 'diya.patel@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'FPGA Hardware Acceleration' },
  { id: 'STU-1008', rollNumber: '21EC002', name: 'Siddharth Rao', department: 'Electronics', cgpa: 8.91, semester: 6, attendance: 89, email: 'siddharth.r@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'Embedded IoT Sensor Node' },
  { id: 'STU-1009', rollNumber: '21ME001', name: 'Kavya Singh', department: 'Mechanical', cgpa: 9.15, semester: 8, attendance: 93, email: 'kavya.singh@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'Finite Element Thermals' },
  { id: 'STU-1010', rollNumber: '21ME002', name: 'Aditya Kulkarni', department: 'Mechanical', cgpa: 8.42, semester: 8, attendance: 82, email: 'aditya.k@campus.edu', status: 'Active', backlogs: 1, projectTitle: 'Solar Kinetic Generators' },
  { id: 'STU-1011', rollNumber: '21CE001', name: 'Neha Joshi', department: 'Civil', cgpa: 8.95, semester: 8, attendance: 90, email: 'neha.j@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'Seismic Structural Analysis' },
  { id: 'STU-1012', rollNumber: '21CE002', name: 'Vikram Mehta', department: 'Civil', cgpa: 7.82, semester: 6, attendance: 74, email: 'vikram.m@campus.edu', status: 'Active', backlogs: 1, projectTitle: 'Eco-Concrete Additives' },
  { id: 'STU-1013', rollNumber: '21CS005', name: 'Isha Deshmukh', department: 'Computer Science', cgpa: 9.38, semester: 6, attendance: 92, email: 'isha.d@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'Zero-Knowledge Proof Audit' },
  { id: 'STU-1014', rollNumber: '21DS002', name: 'Karan Saxena', department: 'Data Science', cgpa: 8.74, semester: 4, attendance: 86, email: 'karan.s@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'Predictive Student Retention' },
  { id: 'STU-1015', rollNumber: '21AI002', name: 'Meera Chawla', department: 'AI & ML', cgpa: 9.21, semester: 4, attendance: 95, email: 'meera.c@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'Multi-Modal Speech Synthesis' },
  { id: 'STU-1016', rollNumber: '21CS006', name: 'Aman Agarwal', department: 'Computer Science', cgpa: 6.85, semester: 4, attendance: 68, email: 'aman.a@campus.edu', status: 'Probation', backlogs: 3, projectTitle: 'Simple File Manager' },
  { id: 'STU-1017', rollNumber: '21EC003', name: 'Tanvi Bhatia', department: 'Electronics', cgpa: 7.12, semester: 4, attendance: 71, email: 'tanvi.b@campus.edu', status: 'Probation', backlogs: 2, projectTitle: 'Signal Filtering Unit' },
  { id: 'STU-1018', rollNumber: '21ME003', name: 'Varun Malhotra', department: 'Mechanical', cgpa: 6.92, semester: 4, attendance: 65, email: 'varun.m@campus.edu', status: 'Probation', backlogs: 2, projectTitle: 'Gearbox CAD Drafting' },
  { id: 'STU-1019', rollNumber: '21CS007', name: 'Riya Kapoor', department: 'Computer Science', cgpa: 9.42, semester: 6, attendance: 97, email: 'riya.k@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'Graph Query Engine' },
  { id: 'STU-1020', rollNumber: '21DS003', name: 'Siddharth Sengupta', department: 'Data Science', cgpa: 9.18, semester: 6, attendance: 89, email: 'siddharth.s@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'Time Series Forecasting' },
  { id: 'STU-1021', rollNumber: '21AI003', name: 'Tarun Varma', department: 'AI & ML', cgpa: 8.95, semester: 6, attendance: 91, email: 'tarun.v@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'Autonomous Robotics Navigation' },
  { id: 'STU-1022', rollNumber: '21EC004', name: 'Avani Reddy', department: 'Electronics', cgpa: 9.05, semester: 6, attendance: 93, email: 'avani.r@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'RISC-V Microcontroller Design' },
  { id: 'STU-1023', rollNumber: '21ME004', name: 'Nikhil Prabhu', department: 'Mechanical', cgpa: 8.25, semester: 6, attendance: 84, email: 'nikhil.p@campus.edu', status: 'Active', backlogs: 1, projectTitle: 'Aerodynamic Drag Simulation' },
  { id: 'STU-1024', rollNumber: '21CE003', name: 'Shreya Sundaram', department: 'Civil', cgpa: 8.65, semester: 6, attendance: 88, email: 'shreya.s@campus.edu', status: 'Active', backlogs: 0, projectTitle: 'Smart Drainage Architecture' },
  { id: 'STU-1025', rollNumber: '21CS008', name: 'Manish Pandey', department: 'Computer Science', cgpa: 7.45, semester: 4, attendance: 76, email: 'manish.p@campus.edu', status: 'Active', backlogs: 1, projectTitle: 'CLI File Encryption' }
];

// Generate extra realistic student records up to 100+ for rich datasets
const extraDepts: StudentRecord['department'][] = ['Computer Science', 'Electronics', 'Mechanical', 'Civil', 'Data Science', 'AI & ML'];
const firstNames = ['Amit', 'Bhavna', 'Chetan', 'Divya', 'Eshaan', 'Farhan', 'Gauri', 'Harsh', 'Indu', 'Jay', 'Kriti', 'Lalit', 'Maya', 'Naveen', 'Ojas', 'Pooja', 'Qasim', 'Rashmi', 'Sameer', 'Trisha', 'Umesh', 'Vandana', 'Yash', 'Zoya'];
const lastNames = ['Chaudhary', 'Iyer', 'Desai', 'Banerjee', 'Rao', 'Nambiar', 'Ghosh', 'Chatterjee', 'Mishra', 'Trivedi', 'Subramanian', 'Seth', 'Paul', 'Shukla', 'Bose', 'Pillai', 'Rathore', 'Menon'];

let idCounter = 1026;
for (let i = 0; i < 95; i++) {
  const dept = extraDepts[i % extraDepts.length];
  const fn = firstNames[i % firstNames.length];
  const ln = lastNames[(i * 3) % lastNames.length];
  const sem = (i % 8) + 1;
  const cgpa = Number((6.2 + ((i * 3.7) % 3.7)).toFixed(2));
  const attendance = Math.floor(62 + ((i * 37) % 37));
  const backlogs = cgpa < 7.0 ? (i % 3) + 1 : 0;
  const status = cgpa < 6.8 ? 'Probation' : (sem === 8 ? 'Graduated' : 'Active');
  
  const deptCodeMap: Record<string, string> = {
    'Computer Science': 'CS',
    'Electronics': 'EC',
    'Mechanical': 'ME',
    'Civil': 'CE',
    'Data Science': 'DS',
    'AI & ML': 'AI'
  };

  INITIAL_STUDENTS.push({
    id: `STU-${idCounter}`,
    rollNumber: `21${deptCodeMap[dept]}${String((i % 50) + 10).padStart(3, '0')}`,
    name: `${fn} ${ln}`,
    department: dept,
    cgpa,
    semester: sem,
    attendance,
    email: `${fn.toLowerCase()}.${ln.toLowerCase()}@campus.edu`,
    status,
    backlogs,
    projectTitle: `${dept} Research Module ${i + 1}`
  });
  idCounter++;
}

// In-Memory Database Store instance
class CampusDatabase {
  private students: StudentRecord[] = [];

  constructor() {
    this.reset();
  }

  public reset() {
    this.students = JSON.parse(JSON.stringify(INITIAL_STUDENTS));
  }

  public getAllStudents(): StudentRecord[] {
    return [...this.students];
  }

  public queryStudents(params: {
    department?: string;
    minCgpa?: number;
    maxCgpa?: number;
    minAttendance?: number;
    maxAttendance?: number;
    status?: string;
    searchName?: string;
    limit?: number;
    sortBy?: keyof StudentRecord;
    sortOrder?: 'asc' | 'desc';
  }): { records: StudentRecord[]; sql: string } {
    let result = [...this.students];
    const whereClauses: string[] = [];

    if (params.department && params.department.toLowerCase() !== 'all') {
      const deptLower = params.department.toLowerCase();
      result = result.filter(s => s.department.toLowerCase().includes(deptLower));
      whereClauses.push(`LOWER(department) LIKE '%${params.department.replace(/'/g, "''")}%'`);
    }

    if (params.minCgpa !== undefined && !isNaN(params.minCgpa)) {
      result = result.filter(s => s.cgpa >= params.minCgpa!);
      whereClauses.push(`cgpa >= ${params.minCgpa}`);
    }

    if (params.maxCgpa !== undefined && !isNaN(params.maxCgpa)) {
      result = result.filter(s => s.cgpa <= params.maxCgpa!);
      whereClauses.push(`cgpa <= ${params.maxCgpa}`);
    }

    if (params.minAttendance !== undefined && !isNaN(params.minAttendance)) {
      result = result.filter(s => s.attendance >= params.minAttendance!);
      whereClauses.push(`attendance >= ${params.minAttendance}`);
    }

    if (params.maxAttendance !== undefined && !isNaN(params.maxAttendance)) {
      result = result.filter(s => s.attendance <= params.maxAttendance!);
      whereClauses.push(`attendance <= ${params.maxAttendance}`);
    }

    if (params.status && params.status.toLowerCase() !== 'all') {
      result = result.filter(s => s.status.toLowerCase() === params.status!.toLowerCase());
      whereClauses.push(`status = '${params.status}'`);
    }

    if (params.searchName) {
      const nameLower = params.searchName.toLowerCase();
      result = result.filter(s => s.name.toLowerCase().includes(nameLower) || s.rollNumber.toLowerCase().includes(nameLower));
      whereClauses.push(`(LOWER(name) LIKE '%${nameLower}%' OR LOWER(roll_number) LIKE '%${nameLower}%')`);
    }

    // Sorting
    const sortBy = params.sortBy || 'cgpa';
    const sortOrder = params.sortOrder || 'desc';
    
    result.sort((a, b) => {
      const valA = a[sortBy] ?? '';
      const valB = b[sortBy] ?? '';
      if (valA < valB) return sortOrder === 'asc' ? -1 : 1;
      if (valA > valB) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });

    const whereString = whereClauses.length > 0 ? ` WHERE ${whereClauses.join(' AND ')}` : '';
    const limitString = params.limit ? ` LIMIT ${params.limit}` : '';
    const sql = `SELECT * FROM students${whereString} ORDER BY ${String(sortBy)} ${sortOrder.toUpperCase()}${limitString};`;

    if (params.limit && params.limit > 0) {
      result = result.slice(0, params.limit);
    }

    return { records: result, sql };
  }

  public updateStudentCgpa(searchQuery: string, newCgpa: number): { affected: StudentRecord[]; sql: string; message: string } {
    const qLower = searchQuery.toLowerCase();
    const matches = this.students.filter(s => 
      s.name.toLowerCase().includes(qLower) || 
      s.rollNumber.toLowerCase().includes(qLower) ||
      s.id.toLowerCase() === qLower
    );

    if (matches.length === 0) {
      return {
        affected: [],
        sql: `UPDATE students SET cgpa = ${newCgpa} WHERE name LIKE '%${searchQuery}%'; -- (0 rows matched)`,
        message: `No student matched search query: "${searchQuery}"`
      };
    }

    matches.forEach(s => {
      s.cgpa = Number(newCgpa.toFixed(2));
      if (s.cgpa < 6.8 && s.status === 'Active') {
        s.status = 'Probation';
      } else if (s.cgpa >= 6.8 && s.status === 'Probation') {
        s.status = 'Active';
      }
    });

    const affectedIds = matches.map(m => `'${m.id}'`).join(', ');
    const sql = `UPDATE students SET cgpa = ${newCgpa.toFixed(2)} WHERE id IN (${affectedIds});`;
    return {
      affected: matches,
      sql,
      message: `Updated CGPA to ${newCgpa.toFixed(2)} for ${matches.length} student(s) (${matches.map(m => m.name).join(', ')})`
    };
  }

  public addStudent(newStudent: Partial<StudentRecord>): { record: StudentRecord; sql: string } {
    const id = `STU-${1000 + this.students.length + 1}`;
    const student: StudentRecord = {
      id,
      rollNumber: newStudent.rollNumber || `21CS${String(this.students.length + 1).padStart(3, '0')}`,
      name: newStudent.name || 'New Student',
      department: (newStudent.department as any) || 'Computer Science',
      cgpa: Number(newStudent.cgpa || 8.0),
      semester: Number(newStudent.semester || 1),
      attendance: Number(newStudent.attendance || 85),
      email: newStudent.email || `${(newStudent.name || 'student').toLowerCase().replace(/\s+/g, '.')}@campus.edu`,
      status: (newStudent.cgpa || 8.0) < 6.8 ? 'Probation' : 'Active',
      backlogs: Number(newStudent.backlogs || 0),
      projectTitle: newStudent.projectTitle || 'Independent Capstone'
    };

    this.students.unshift(student);
    const sql = `INSERT INTO students (id, roll_number, name, department, cgpa, semester, attendance, email, status, backlogs) VALUES ('${student.id}', '${student.rollNumber}', '${student.name.replace(/'/g, "''")}', '${student.department}', ${student.cgpa}, ${student.semester}, ${student.attendance}, '${student.email}', '${student.status}', ${student.backlogs});`;
    return { record: student, sql };
  }

  public deleteStudents(condition: string): { count: number; sql: string } {
    let toDelete: StudentRecord[] = [];
    if (condition === 'attendance_zero') {
      toDelete = this.students.filter(s => s.attendance === 0);
      this.students = this.students.filter(s => s.attendance > 0);
    } else if (condition === 'probation') {
      toDelete = this.students.filter(s => s.status === 'Probation');
      this.students = this.students.filter(s => s.status !== 'Probation');
    } else {
      toDelete = this.students.filter(s => s.attendance < 50);
      this.students = this.students.filter(s => s.attendance >= 50);
    }

    const sql = `DELETE FROM students WHERE attendance = 0; -- Deleted ${toDelete.length} records`;
    return { count: toDelete.length, sql };
  }

  public calculateMetrics(records: StudentRecord[]) {
    if (records.length === 0) {
      return {
        totalRecords: 0,
        averageCgpa: 0,
        highestCgpa: 0,
        lowestCgpa: 0,
        avgAttendance: 0,
        probationCount: 0,
        departmentBreakdown: {}
      };
    }

    const totalRecords = records.length;
    const cgpas = records.map(r => r.cgpa);
    const sumCgpa = cgpas.reduce((acc, c) => acc + c, 0);
    const averageCgpa = Number((sumCgpa / totalRecords).toFixed(2));
    const highestCgpa = Math.max(...cgpas);
    const lowestCgpa = Math.min(...cgpas);

    const attendances = records.map(r => r.attendance);
    const avgAttendance = Number((attendances.reduce((acc, a) => acc + a, 0) / totalRecords).toFixed(1));
    const probationCount = records.filter(r => r.status === 'Probation').length;

    const departmentBreakdown: Record<string, { count: number; avgCgpa: number }> = {};
    records.forEach(r => {
      if (!departmentBreakdown[r.department]) {
        departmentBreakdown[r.department] = { count: 0, avgCgpa: 0 };
      }
      departmentBreakdown[r.department].count += 1;
      departmentBreakdown[r.department].avgCgpa += r.cgpa;
    });

    Object.keys(departmentBreakdown).forEach(d => {
      const item = departmentBreakdown[d];
      item.avgCgpa = Number((item.avgCgpa / item.count).toFixed(2));
    });

    return {
      totalRecords,
      averageCgpa,
      highestCgpa,
      lowestCgpa,
      avgAttendance,
      probationCount,
      departmentBreakdown
    };
  }

  public toCSV(records: StudentRecord[]): string {
    if (records.length === 0) return 'ID,RollNumber,Name,Department,CGPA,Semester,Attendance,Email,Status\n';
    const headers = 'ID,RollNumber,Name,Department,CGPA,Semester,Attendance,Email,Status,Backlogs\n';
    const rows = records.map(r => 
      `"${r.id}","${r.rollNumber}","${r.name.replace(/"/g, '""')}","${r.department}",${r.cgpa},${r.semester},${r.attendance},"${r.email}","${r.status}",${r.backlogs}`
    ).join('\n');
    return headers + rows;
  }
}

export const dbInstance = new CampusDatabase();
