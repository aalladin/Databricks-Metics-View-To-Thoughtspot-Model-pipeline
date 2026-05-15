-- ============================================================
-- Flat Denormalized View: PAYROLL_SV
-- Alternative to Model approach — single table for ThoughtSpot
-- ThoughtSpot applies SUM/COUNT at query time
-- ============================================================

CREATE OR REPLACE VIEW TS_AGENT_DEMO.HR_PAYROLL.PAYROLL_SV AS
SELECT
  -- Dimensions
  CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
  e.employment_status,
  e.employment_type,
  e.gender,
  d.department_name,
  d.cost_center,
  j.job_title,
  j.job_level,
  j.job_family,
  l.location_name,
  l.city,
  l.state,
  l.country,
  l.region,
  pp.pay_date,
  pp.pay_frequency,
  pp.fiscal_year,
  pp.fiscal_quarter,

  -- Keys (for COUNT DISTINCT)
  f.employee_id,

  -- Measures (row-level, ThoughtSpot SUMs)
  f.gross_pay,
  f.base_pay,
  f.overtime_pay,
  f.bonus_pay,
  f.net_pay,
  f.federal_tax,
  f.state_tax,
  f.social_security,
  f.medicare,
  f.health_insurance_deduction,
  f.retirement_401k_deduction,
  f.other_deductions,
  f.regular_hours,
  f.overtime_hours,
  (f.federal_tax + f.state_tax + f.social_security + f.medicare) AS total_tax,
  (f.health_insurance_deduction + f.retirement_401k_deduction + f.other_deductions) AS total_deductions

FROM TS_AGENT_DEMO.HR_PAYROLL.FACT_PAYROLL f
JOIN TS_AGENT_DEMO.HR_PAYROLL.DIM_EMPLOYEE e    ON f.employee_id = e.employee_id
JOIN TS_AGENT_DEMO.HR_PAYROLL.DIM_DEPARTMENT d  ON f.department_id = d.department_id
JOIN TS_AGENT_DEMO.HR_PAYROLL.DIM_JOB_TITLE j   ON f.job_title_id = j.job_title_id
JOIN TS_AGENT_DEMO.HR_PAYROLL.DIM_LOCATION l    ON f.location_id = l.location_id
JOIN TS_AGENT_DEMO.HR_PAYROLL.DIM_PAY_PERIOD pp ON f.pay_period_id = pp.pay_period_id;
