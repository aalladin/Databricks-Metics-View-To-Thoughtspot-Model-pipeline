-- ============================================================
-- UC Metric View: PAYROLL_MV
-- Source: FACT_PAYROLL joined to all dimension tables
-- Canonical metric: Net Pay
-- ============================================================

CREATE OR REPLACE VIEW TS_AGENT_DEMO.HR_PAYROLL.PAYROLL_MV
WITH METRICS LANGUAGE YAML AS $$
version: 1.1

source: TS_AGENT_DEMO.HR_PAYROLL.FACT_PAYROLL

joins:
  - name: employee
    source: TS_AGENT_DEMO.HR_PAYROLL.DIM_EMPLOYEE
    "on": source.employee_id = employee.employee_id
  - name: department
    source: TS_AGENT_DEMO.HR_PAYROLL.DIM_DEPARTMENT
    "on": source.department_id = department.department_id
  - name: job_title
    source: TS_AGENT_DEMO.HR_PAYROLL.DIM_JOB_TITLE
    "on": source.job_title_id = job_title.job_title_id
  - name: location
    source: TS_AGENT_DEMO.HR_PAYROLL.DIM_LOCATION
    "on": source.location_id = location.location_id
  - name: pay_period
    source: TS_AGENT_DEMO.HR_PAYROLL.DIM_PAY_PERIOD
    "on": source.pay_period_id = pay_period.pay_period_id
  - name: dt
    source: TS_AGENT_DEMO.HR_PAYROLL.DIM_DATE
    "on": source.date_key = dt.date_key

dimensions:
  - name: Employee Name
    expr: "CONCAT(employee.first_name, ' ', employee.last_name)"
  - name: Employment Status
    expr: employee.employment_status
  - name: Employment Type
    expr: employee.employment_type
  - name: Gender
    expr: employee.gender
  - name: Department Name
    expr: department.department_name
  - name: Cost Center
    expr: department.cost_center
  - name: Job Title
    expr: job_title.job_title
  - name: Job Level
    expr: job_title.job_level
  - name: Job Family
    expr: job_title.job_family
  - name: Location Name
    expr: location.location_name
  - name: City
    expr: location.city
  - name: State
    expr: location.state
  - name: Country
    expr: location.country
  - name: Region
    expr: location.region
  - name: Pay Date
    expr: pay_period.pay_date
  - name: Pay Frequency
    expr: pay_period.pay_frequency
  - name: Fiscal Year
    expr: pay_period.fiscal_year
  - name: Fiscal Quarter
    expr: pay_period.fiscal_quarter

measures:
  - name: Gross Pay
    expr: SUM(source.gross_pay)
  - name: Net Pay
    expr: SUM(source.net_pay)
  - name: Base Pay
    expr: SUM(source.base_pay)
  - name: Overtime Pay
    expr: SUM(source.overtime_pay)
  - name: Bonus Pay
    expr: SUM(source.bonus_pay)
  - name: Total Tax
    expr: SUM(source.federal_tax + source.state_tax + source.social_security + source.medicare)
  - name: Total Deductions
    expr: SUM(source.health_insurance_deduction + source.retirement_401k_deduction + source.other_deductions)
  - name: Regular Hours
    expr: SUM(source.regular_hours)
  - name: Overtime Hours
    expr: SUM(source.overtime_hours)
  - name: Headcount
    expr: COUNT(DISTINCT source.employee_id)
  - name: Avg Gross Pay
    expr: SUM(source.gross_pay) / COUNT(DISTINCT source.employee_id)
  - name: Tax Burden Pct
    expr: SUM(source.federal_tax + source.state_tax + source.social_security + source.medicare) / SUM(source.gross_pay) * 100
$$;

COMMENT ON VIEW TS_AGENT_DEMO.HR_PAYROLL.PAYROLL_MV IS
  'Sales metrics over Payroll, Employee, Department, Job Title, Location, and Pay Period. Net Pay is the canonical compensation metric.';
