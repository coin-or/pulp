//! Shared types and model core used by Variable, Constraint, AffineExpr, and Model.

use std::cell::RefCell;
use std::rc::{Rc, Weak};

use indexmap::IndexMap;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use crate::affine_expr::AffineExpr;

/// Unique identifier for a variable within a model.
pub type VarId = usize;
/// Unique identifier for a constraint within a model.
pub type ConstrId = usize;

/// Variable category: continuous, integer, or binary.
#[pyclass]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Category {
    Continuous,
    Integer,
    Binary,
}

/// Constraint sense: <=, ==, >=.
#[pyclass]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Sense {
    LessEqual,
    Equal,
    GreaterEqual,
}

/// Objective sense: minimize or maximize.
#[pyclass]
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
    pub obj_coeff: f64,
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
}

impl ModelCore {
    pub fn new(name: String) -> Self {
        Self {
            name,
            vars: Vec::new(),
            constraints: Vec::new(),
            objective: None,
            sense: ObjSense::Minimize,
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
            obj_coeff: 0.0,
            value: None,
            dj: None,
        });
        id
    }

    pub fn add_constraint(
        &mut self,
        name: String,
        coeffs: IndexMap<VarId, f64>,
        rhs: f64,
        sense: Sense,
    ) -> ConstrId {
        let id = self.constraints.len();
        self.constraints.push(ConstraintData {
            name,
            coeffs,
            rhs,
            sense,
            pi: None,
            slack: None,
        });
        id
    }

    pub fn set_objective(&mut self, expr: AffineExpr) {
        self.objective = Some(expr);
    }

    pub fn clear_objective(&mut self) {
        self.objective = None;
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
