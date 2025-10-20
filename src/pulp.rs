use std::collections::{HashMap, HashSet};
use std::fmt;
use std::ops::{Add, Sub, Mul, Div, Neg};

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum LpCategory {
    Continuous,
    Integer,
    Binary,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LpConstraintSense {
    Eq,
    Le,
    Ge,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LpStatus {
    NotSolved,
    Optimal,
    Infeasible,
    Unbounded,
    // ... add more as needed
}

#[derive(Debug, Clone)]
pub struct LpVariable {
    pub name: String,
    pub lowBound: Option<f64>,
    pub upBound: Option<f64>,
    pub cat: LpCategory,
    pub varValue: Option<f64>,
    pub dj: Option<f64>,
    pub _lowbound_original: Option<f64>,
    pub _upbound_original: Option<f64>,
}

impl LpVariable {
    pub fn new(name: &str, lowBound: Option<f64>, upBound: Option<f64>, cat: LpCategory) -> Self {
        let (lowBound, upBound, cat) = match cat {
            LpCategory::Binary => (Some(0.0), Some(1.0), LpCategory::Integer),
            _ => (lowBound, upBound, cat),
        };
        Self {
            name: name.to_string(),
            lowBound,
            upBound,
            cat,
            varValue: None,
            dj: None,
            _lowbound_original: lowBound,
            _upbound_original: upBound,
        }
        // TODO: math.isfinite checks for both bounds
        // TODO: LpElement init?
        // TODO: column-based modeling attributes (e)
    }

    pub fn bounds(&mut self, low: Option<f64>, up: Option<f64>) {
        self.lowBound = low;
        self.upBound = up;
    }

    pub fn positive(&mut self) {
        self.lowBound = Some(0.0);
        self.upBound = None;
    }

    pub fn value(&self) -> Option<f64> {
        self.varValue
    }

    pub fn set_value(&mut self, val: f64) {
        // TODO: make a setter, getter
        self.varValue = Some(val);
    }

    pub fn round(&mut self, epsInt: f64, eps: f64) {
        // TODO: add defaults epsInt=1e-5, eps=1e-7
        if let Some(v) = self.varValue {
            if let Some(up) = self.upBound {
                if v > up && v <= up + eps {
                    self.varValue = Some(up);
                }
            }
            if let Some(low) = self.lowBound {
                if v < low && v >= low - eps {
                    self.varValue = Some(low);
                }
            }
            self.varValue = self.roundedValue(epsInt);
        }
    }

    pub fn roundedValue(&self, eps: f64) -> Option<f64> {
        // TODO: add default eps=1e-5
        if self.cat == LpCategory::Integer {
            if let Some(v) = self.varValue {
                if (v - v.round()).abs() <= eps {
                    return Some(v.round());
                }
            }
        }
        self.varValue
    }

    pub fn valueOrDefault(&self) -> f64 {
        if let Some(v) = self.varValue {
            v
        } else if let Some(low) = self.lowBound {
            if let Some(up) = self.upBound {
                if 0.0 >= low && 0.0 <= up {
                    0.0
                } else if low >= 0.0 {
                    low
                } else {
                    up
                }
            } else if 0.0 >= low {
                0.0
            } else {
                low
            }
        } else if let Some(up) = self.upBound {
            if 0.0 <= up {
                0.0
            } else {
                up
            }
        } else {
            0.0
        }
    }

    pub fn valid(&self, eps: f64) -> bool {
        //if self.name == "__dummy" and self.varValue is None:
            // return True
        if self.varValue.is_none() {
            return false;
        }
        let v = self.varValue.unwrap();
        if let Some(up) = self.upBound {
            if v > up + eps {
                return false;
            }
        }
        if let Some(low) = self.lowBound {
            if v < low - eps {
                return false;
            }
        }
        if self.cat == LpCategory::Integer && (v.round() - v).abs() > eps {
            return false;
        }
        true
    }

    pub fn infeasibilityGap(&self, mip: bool) -> f64 {
        // TODO: add default mip=True
        if let Some(v) = self.varValue {
            if let Some(up) = self.upBound {
                if v > up {
                    return v - up;
                }
            }
            if let Some(low) = self.lowBound {
                if v < low {
                    return v - low;
                }
            }
            if mip && self.cat == LpCategory::Integer && (v.round() - v) != 0.0 {
                return v.round() - v;
            }
            0.0
        } else {
            0.0
        }
    }

    pub fn isBinary(&self) -> bool {
        self.cat == LpCategory::Binary
            || (self.cat == LpCategory::Integer
                && self.lowBound == Some(0.0)
                && self.upBound == Some(1.0))
    }

    pub fn isInteger(&self) -> bool {
        self.cat == LpCategory::Integer
    }

    pub fn isFree(&self) -> bool {
        self.lowBound.is_none() && self.upBound.is_none()
    }

    pub fn isConstant(&self) -> bool {
        self.lowBound.is_some() && self.upBound == self.lowBound
    }

    pub fn isPositive(&self) -> bool {
        self.lowBound == Some(0.0) && self.upBound.is_none()
    }
}

#[derive(Debug, Clone)]
pub struct LpAffineExpression {
    pub terms: HashMap<String, f64>, // variable name -> coefficient
    pub constant: f64,
}

impl LpAffineExpression {
    pub fn new() -> Self {
        Self {
            terms: HashMap::new(),
            constant: 0.0,
        }
    }
    pub fn add_term(&mut self, var: &LpVariable, coeff: f64) {
        *self.terms.entry(var.name.clone()).or_insert(0.0) += coeff;
    }

    pub fn isAtomic(&self) -> bool {
        self.terms.len() == 1 && self.constant == 0.0 && self.terms.values().next() == Some(&1.0)
    }

    pub fn isNumericalConstant(&self) -> bool {
        self.terms.is_empty()
    }

    pub fn atom(&self) -> Option<&String> {
        self.terms.keys().next()
    }

    pub fn value(&self, vars: &HashMap<String, LpVariable>) -> Option<f64> {
        let mut s = self.constant;
        for (name, coeff) in &self.terms {
            let v = vars.get(name)?.varValue?;
            s += v * coeff;
        }
        Some(s)
    }

    pub fn valueOrDefault(&self, vars: &HashMap<String, LpVariable>) -> f64 {
        let mut s = self.constant;
        for (name, coeff) in &self.terms {
            let v = vars.get(name).map(|v| v.valueOrDefault()).unwrap_or(0.0);
            s += v * coeff;
        }
        s
    }

    pub fn addInPlace(&mut self, other: &LpAffineExpression, sign: f64) {
        self.constant += other.constant * sign;
        for (k, v) in &other.terms {
            *self.terms.entry(k.clone()).or_insert(0.0) += v * sign;
        }
    }

    pub fn subInPlace(&mut self, other: &LpAffineExpression) {
        self.addInPlace(other, -1.0);
    }
}

// Operator overloading for LpAffineExpression
impl Add for LpAffineExpression {
    type Output = Self;
    fn add(mut self, rhs: Self) -> Self::Output {
        self.add_in_place(&rhs, 1.0);
        self
    }
}
impl Sub for LpAffineExpression {
    type Output = Self;
    fn sub(mut self, rhs: Self) -> Self::Output {
        self.sub_in_place(&rhs);
        self
    }
}
impl Neg for LpAffineExpression {
    type Output = Self;
    fn neg(mut self) -> Self::Output {
        self.constant = -self.constant;
        for v in self.terms.values_mut() {
            *v = -*v;
        }
        self
    }
}
impl Mul<f64> for LpAffineExpression {
    type Output = Self;
    fn mul(mut self, rhs: f64) -> Self::Output {
        self.constant *= rhs;
        for v in self.terms.values_mut() {
            *v *= rhs;
        }
        self
    }
}
impl Div<f64> for LpAffineExpression {
    type Output = Self;
    fn div(mut self, rhs: f64) -> Self::Output {
        self.constant /= rhs;
        for v in self.terms.values_mut() {
            *v /= rhs;
        }
        self
    }
}

#[derive(Debug, Clone)]
pub struct LpConstraint {
    pub expr: LpAffineExpression,
    pub sense: LpConstraintSense,
    pub rhs: f64,
    pub name: Option<String>,
    pub pi: Option<f64>,
    pub slack: Option<f64>,
}

impl LpConstraint {
    pub fn new(expr: LpAffineExpression, sense: LpConstraintSense, rhs: f64, name: Option<String>) -> Self {
        Self {
            expr,
            sense,
            rhs,
            name,
            pi: None,
            slack: None,
        }
    }

    pub fn getLb(&self) -> Option<f64> {
        match self.sense {
            LpConstraintSense::Ge | LpConstraintSense::Eq => Some(self.rhs),
            _ => None,
        }
    }

    pub fn getUb(&self) -> Option<f64> {
        match self.sense {
            LpConstraintSense::Le | LpConstraintSense::Eq => Some(self.rhs),
            _ => None,
        }
    }

    pub fn value(&self, vars: &HashMap<String, LpVariable>) -> Option<f64> {
        self.expr.value(vars)
    }

    pub fn valueOrDefault(&self, vars: &HashMap<String, LpVariable>) -> f64 {
        self.expr.valueOrDefault(vars)
    }

    pub fn valid(&self, vars: &HashMap<String, LpVariable>, eps: f64) -> bool {
        let val = self.value(vars).unwrap_or(0.0);
        match self.sense {
            LpConstraintSense::Eq => val.abs() <= eps,
            LpConstraintSense::Le => val <= self.rhs + eps,
            LpConstraintSense::Ge => val >= self.rhs - eps,
        }
    }
}

#[derive(Debug, Clone)]
pub struct LpProblem {
    pub name: String,
    pub sense: i32, // 1=min, -1=max
    pub objective: Option<LpAffineExpression>,
    pub constraints: HashMap<String, LpConstraint>,
    pub variables: HashMap<String, LpVariable>,
    pub status: LpStatus,
}

impl LpProblem {
    pub fn new(name: &str, sense: i32) -> Self {
        Self {
            name: name.to_string(),
            sense,
            objective: None,
            constraints: HashMap::new(),
            variables: HashMap::new(),
            status: LpStatus::NotSolved,
        }
    }

    pub fn addVariable(&mut self, variable: LpVariable) {
        self.variables.insert(variable.name.clone(), variable);
    }

    pub fn addVariables(&mut self, variables: Vec<LpVariable>) {
        for v in variables {
            self.addVariable(v);
        }
    }

    pub fn addConstraint(&mut self, name: &str, constraint: LpConstraint) {
        self.constraints.insert(name.to_string(), constraint);
    }

    pub fn setObjective(&mut self, obj: LpAffineExpression) {
        self.objective = Some(obj);
    }

    pub fn variables(&self) -> Vec<&LpVariable> {
        self.variables.values().collect()
    }

    pub fn constraints(&self) -> Vec<&LpConstraint> {
        self.constraints.values().collect()
    }

    pub fn solve(&mut self) -> LpStatus {
        // Stub: integrate with solver here
        self.status = LpStatus::Optimal;
        self.status
    }

    pub fn numVariables(&self) -> usize {
        self.variables.len()
    }

    pub fn numConstraints(&self) -> usize {
        self.constraints.len()
    }

    pub fn valid(&self, eps: f64) -> bool {
        for v in self.variables.values() {
            if !v.valid(eps) {
                return false;
            }
        }
        for c in self.constraints.values() {
            if !c.valid(&self.variables, eps) {
                return false;
            }
        }
        true
    }

    pub fn infeasibilityGap(&self, mip: bool) -> f64 {
        let mut gap = 0.0;
        for v in self.variables.values() {
            gap = gap.max(v.infeasibilityGap(mip).abs());
        }
        for c in self.constraints.values() {
            let val = c.value(&self.variables).unwrap_or(0.0);
            if !c.valid(&self.variables, 0.0) {
                gap = gap.max(val.abs());
            }
        }
        gap
    }
}

// Utility functions
pub fn lp_sum(exprs: &[LpAffineExpression]) -> LpAffineExpression {
    exprs.iter().cloned().fold(LpAffineExpression::new(), |acc, e| acc + e)
}

pub fn lp_dot(v1: &[LpAffineExpression], v2: &[LpAffineExpression]) -> LpAffineExpression {
    lp_sum(&v1.iter().zip(v2.iter()).map(|(a, b)| {
        let mut e = a.clone();
        e.constant *= b.constant;
        e
    }).collect::<Vec<_>>())
}

// Display implementations for pretty printing
impl fmt::Display for LpVariable {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.name)
    }
}
impl fmt::Display for LpAffineExpression {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let mut s = String::new();
        for (var, coeff) in &self.terms {
            s.push_str(&format!("{}*{} + ", coeff, var));
        }
        s.push_str(&format!("{}", self.constant));
        write!(f, "{}", s)
    }
}
impl fmt::Display for LpConstraint {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let sense_str = match self.sense {
            LpConstraintSense::Eq => "=",
            LpConstraintSense::Le => "<=",
            LpConstraintSense::Ge => ">=",
        };
        write!(f, "{} {} {}", self.expr, sense_str, self.rhs)
    }
}
impl fmt::Display for LpProblem {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let sense_str = if self.sense == 1 { "MINIMIZE" } else { "MAXIMIZE" };
        writeln!(f, "{}:", self.name)?;
        writeln!(f, "{}", sense_str)?;
        if let Some(obj) = &self.objective {
            writeln!(f, "{}", obj)?;
        }
        writeln!(f, "SUBJECT TO")?;
        for (name, c) in &self.constraints {
            writeln!(f, "{}: {}", name, c)?;
        }
        writeln!(f, "VARIABLES")?;
        for v in self.variables.values() {
            writeln!(f, "{}", v)?;
        }
        Ok(())
    }
}
