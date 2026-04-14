//! Shared types and model core used by Variable, Constraint, AffineExpr, and Model.

use std::cell::RefCell;
use std::collections::HashMap;
use std::rc::{Rc, Weak};

use indexmap::IndexMap;
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;

use crate::affine_expr::AffineExpr;

/// Unique identifier for a variable within a model.
pub type VarId = usize;
/// Unique identifier for a constraint within a model.
pub type ConstrId = usize;

/// Variable category: continuous, integer, or binary.
#[pyclass(from_py_object)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Category {
    Continuous,
    Integer,
    Binary,
}

/// Constraint sense: <=, ==, >=.
#[pyclass(from_py_object)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Sense {
    LessEqual,
    Equal,
    GreaterEqual,
}

/// Objective sense: minimize or maximize.
#[pyclass(from_py_object)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ObjSense {
    Minimize,
    Maximize,
}

#[derive(Clone, Debug)]
pub struct VariableData {
    pub name: String,
    pub lb: f64,
    pub ub: f64,
    pub category: Category,
    pub value: Option<f64>,
    pub dj: Option<f64>,
}

#[derive(Clone, Debug)]
pub struct ConstraintData {
    pub name: String,
    pub coeffs: IndexMap<VarId, f64>,
    pub rhs: f64,
    pub sense: Sense,
    pub pi: Option<f64>,
    pub slack: Option<f64>,
}

#[derive(Debug)]
pub struct ModelCore {
    pub name: String,
    pub vars: Vec<VariableData>,
    pub constraints: Vec<ConstraintData>,
    pub objective: Option<AffineExpr>,
    /// Objective sense (min/max); set when set_objective is called, or default Minimize.
    pub sense: ObjSense,
    /// Counter for auto-generated constraint names (`_C1`, ...); shared by all `Model` handles.
    pub next_auto_constraint_id: usize,
}

impl ModelCore {
    pub fn new(name: String) -> Self {
        Self {
            name,
            vars: Vec::new(),
            constraints: Vec::new(),
            objective: None,
            sense: ObjSense::Minimize,
            next_auto_constraint_id: 0,
        }
    }

    pub fn add_variable(
        &mut self,
        name: String,
        lb: f64,
        ub: f64,
        category: Category,
    ) -> VarId {
        let id = self.vars.len();
        self.vars.push(VariableData {
            name,
            lb,
            ub,
            category,
            value: None,
            dj: None,
        });
        id
    }

    /// Add a constraint from a pending `AffineExpr` (must have `sense` set).
    /// `rhs` in storage is `-expr.constant` (same convention as Python `addConstraint`).
    pub fn add_constraint(&mut self, expr: &AffineExpr) -> PyResult<ConstrId> {
        let sense = expr.sense.ok_or_else(|| {
            PyValueError::new_err("Cannot add constraint without a sense (<=, >=, ==)")
        })?;
        if !expr.constant.is_finite() {
            return Err(PyValueError::new_err(format!(
                "Invalid constraint RHS value: {}. Coefficients and bounds must be finite.",
                expr.constant
            )));
        }
        for (vid, coeff) in &expr.terms {
            if !coeff.is_finite() {
                return Err(PyValueError::new_err(format!(
                    "Invalid coefficient value: {coeff} for variable id {vid}. Coefficients must be finite."
                )));
            }
            if *vid >= self.vars.len() {
                return Err(PyValueError::new_err(format!(
                    "Variable id {vid} is out of range (model has {} variables)",
                    self.vars.len()
                )));
            }
        }
        let rhs = -expr.constant;
        let coeffs = expr.terms.clone();
        let raw_name = expr
            .name
            .as_deref()
            .map(str::trim)
            .filter(|s| !s.is_empty());
        let name: String = match raw_name {
            None => {
                self.next_auto_constraint_id += 1;
                format!("_C{}", self.next_auto_constraint_id)
            }
            Some(n) if n.starts_with('_') => {
                return Err(PyValueError::new_err(
                    "Constraint names must not start with '_'; names beginning with '_' are reserved for auto-generated constraints (_C1, _C2, ...).",
                ));
            }
            Some(n) => n.to_string(),
        };
        let id = self.constraints.len();
        self.constraints.push(ConstraintData {
            name,
            coeffs,
            rhs,
            sense,
            pi: None,
            slack: None,
        });
        Ok(id)
    }

    pub fn set_objective(&mut self, expr: AffineExpr) {
        self.objective = Some(expr);
    }

    pub fn clear_objective(&mut self) {
        self.objective = None;
    }

    /// At least two variables share the same name (invalid for LP/MPS export).
    pub(crate) fn check_duplicate_var_names(&self) -> PyResult<()> {
        let mut seen: HashMap<&str, usize> = HashMap::new();
        for vd in &self.vars {
            *seen.entry(vd.name.as_str()).or_insert(0) += 1;
        }
        let repeated: Vec<(&str, usize)> = seen.into_iter().filter(|(_, c)| *c >= 2).collect();
        if !repeated.is_empty() {
            let msg: Vec<String> = repeated
                .iter()
                .map(|(n, c)| format!("('{}', {})", n, c))
                .collect();
            return Err(PyRuntimeError::new_err(format!(
                "Repeated variable names: {{{}}}",
                msg.join(", ")
            )));
        }
        Ok(())
    }

    /// At least two constraints share the same name (invalid for LP/MPS export).
    pub(crate) fn check_duplicate_constraint_names(&self) -> PyResult<()> {
        let mut seen: HashMap<&str, usize> = HashMap::new();
        for cd in &self.constraints {
            *seen.entry(cd.name.as_str()).or_insert(0) += 1;
        }
        let repeated: Vec<(&str, usize)> = seen.into_iter().filter(|(_, c)| *c >= 2).collect();
        if !repeated.is_empty() {
            let msg: Vec<String> = repeated
                .iter()
                .map(|(n, c)| format!("('{}', {})", n, c))
                .collect();
            return Err(PyRuntimeError::new_err(format!(
                "Repeated constraint names: {{{}}}",
                msg.join(", ")
            )));
        }
        Ok(())
    }

    /// Variable names longer than `max_length` are invalid for CPLEX LP format.
    pub(crate) fn check_var_name_lengths(&self, max_length: usize) -> PyResult<()> {
        let long: Vec<&str> = self
            .vars
            .iter()
            .filter(|v| v.name.len() > max_length)
            .map(|v| v.name.as_str())
            .collect();
        if !long.is_empty() {
            return Err(PyRuntimeError::new_err(format!(
                "Variable names too long for Lp format: {:?}",
                long
            )));
        }
        Ok(())
    }
}

pub fn upgrade_model(weak: &Weak<RefCell<ModelCore>>) -> PyResult<Rc<RefCell<ModelCore>>> {
    weak.upgrade().ok_or_else(|| {
        PyValueError::new_err(
            "The model this variable/constraint belongs to no longer exists. \
             Do not reassign or delete the LpProblem and then use its variables or constraints.",
        )
    })
}

/// Get the model from an optional weak ref. Use for AffineExpr and anywhere the model
/// may be missing or dropped. Returns a friendly error instead of panicking.
pub fn get_model_optional(
    opt_weak: &Option<Weak<RefCell<ModelCore>>>,
) -> PyResult<Rc<RefCell<ModelCore>>> {
    let weak = opt_weak.as_ref().ok_or_else(|| {
        PyValueError::new_err(
            "This expression has no associated model. Use variables from an existing LpProblem.",
        )
    })?;
    weak.upgrade().ok_or_else(|| {
        PyValueError::new_err(
            "The model this variable/expression belongs to no longer exists. \
             Do not reassign or delete the LpProblem and then use its variables or expressions.",
        )
    })
}

// ── LP formatting constants ──

pub const LP_CPLEX_LP_LINE_SIZE: usize = 78;

impl Sense {
    pub fn lp_symbol(&self) -> &'static str {
        match self {
            Sense::LessEqual => "<=",
            Sense::Equal => "=",
            Sense::GreaterEqual => ">=",
        }
    }

    /// PuLP uses -1 for LE, 0 for EQ, 1 for GE
    pub fn to_pulp_int(&self) -> i32 {
        match self {
            Sense::LessEqual => -1,
            Sense::Equal => 0,
            Sense::GreaterEqual => 1,
        }
    }

    pub fn from_pulp_int(val: i32) -> Option<Self> {
        match val {
            -1 => Some(Sense::LessEqual),
            0 => Some(Sense::Equal),
            1 => Some(Sense::GreaterEqual),
            _ => None,
        }
    }

    pub fn mps_code(&self) -> &'static str {
        match self {
            Sense::LessEqual => "L",
            Sense::Equal => "E",
            Sense::GreaterEqual => "G",
        }
    }
}

impl Category {
    pub fn as_str(&self) -> &'static str {
        match self {
            Category::Continuous => "Continuous",
            Category::Integer => "Integer",
            Category::Binary => "Binary",
        }
    }
}

impl VariableData {
    pub fn is_binary(&self) -> bool {
        self.category == Category::Binary
            || (self.category == Category::Integer && self.lb == 0.0 && self.ub == 1.0)
    }

    pub fn is_integer(&self) -> bool {
        self.category == Category::Integer
    }

    pub fn is_free(&self) -> bool {
        self.lb == f64::NEG_INFINITY && self.ub == f64::INFINITY
    }

    pub fn is_constant(&self) -> bool {
        self.lb.is_finite() && self.lb == self.ub
    }

    pub fn is_positive(&self) -> bool {
        self.lb == 0.0 && self.ub == f64::INFINITY
    }
}
