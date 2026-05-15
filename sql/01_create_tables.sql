-- ============================================================
-- HR Payroll Schema - Table Definitions
-- Catalog: TS_AGENT_DEMO | Schema: HR_PAYROLL
-- ============================================================

USE CATALOG ts_agent_demo;
CREATE SCHEMA IF NOT EXISTS hr_payroll;
USE SCHEMA hr_payroll;

-- Dimension: Date
CREATE TABLE IF NOT EXISTS dim_date (
  date_key INT,
  full_date DATE,
  year INT,
  quarter INT,
  month INT,
  month_name STRING,
  week_of_year INT,
  day_of_week INT,
  day_name STRING,
  is_weekend BOOLEAN,
  is_holiday BOOLEAN,
  fiscal_year INT,
  fiscal_quarter INT
);

-- Dimension: Location
CREATE TABLE IF NOT EXISTS dim_location (
  location_id INT,
  location_name STRING,
  city STRING,
  state STRING,
  country STRING,
  region STRING,
  postal_code STRING,
  is_remote BOOLEAN
);

-- Dimension: Department
CREATE TABLE IF NOT EXISTS dim_department (
  department_id INT,
  department_name STRING,
  department_head STRING,
  cost_center STRING,
  parent_department_id INT
);

-- Dimension: Job Title
CREATE TABLE IF NOT EXISTS dim_job_title (
  job_title_id INT,
  job_title STRING,
  job_level STRING,
  job_family STRING,
  min_salary DOUBLE,
  max_salary DOUBLE,
  is_exempt BOOLEAN
);

-- Dimension: Pay Period
CREATE TABLE IF NOT EXISTS dim_pay_period (
  pay_period_id INT,
  period_start_date DATE,
  period_end_date DATE,
  pay_date DATE,
  pay_frequency STRING,
  fiscal_year INT,
  fiscal_quarter INT,
  period_number INT
);

-- Dimension: Employee
CREATE TABLE IF NOT EXISTS dim_employee (
  employee_id INT,
  first_name STRING,
  last_name STRING,
  email STRING,
  hire_date DATE,
  termination_date DATE,
  employment_status STRING,
  employment_type STRING,
  department_id INT,
  job_title_id INT,
  location_id INT,
  manager_id INT,
  gender STRING,
  date_of_birth DATE,
  annual_salary DOUBLE
);

-- Fact: Payroll
CREATE TABLE IF NOT EXISTS fact_payroll (
  payroll_id INT,
  employee_id INT,
  pay_period_id INT,
  department_id INT,
  job_title_id INT,
  location_id INT,
  date_key INT,
  gross_pay DOUBLE,
  base_pay DOUBLE,
  overtime_pay DOUBLE,
  bonus_pay DOUBLE,
  federal_tax DOUBLE,
  state_tax DOUBLE,
  social_security DOUBLE,
  medicare DOUBLE,
  health_insurance_deduction DOUBLE,
  retirement_401k_deduction DOUBLE,
  other_deductions DOUBLE,
  net_pay DOUBLE,
  overtime_hours DOUBLE,
  regular_hours DOUBLE
);
