//! Shared types and model core used by Variable, Constraint, AffineExpr, and Model.

use std::cell::RefCell;
use std::rc::{Rc, Weak};

use indexmap::IndexMap;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

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
}

#[derive(Clone, Debug)]
pub struct ConstraintData {
    pub name: String,
    pub coeffs: IndexMap<VarId, f64>,
    pub rhs: f64,
    pub sense: Sense,
}

#[derive(Clone, Debug)]
pub struct ObjectiveData {
    pub coeffs: IndexMap<VarId, f64>,
    pub constant: f64,
    pub sense: ObjSense,
}

#[derive(Debug)]
pub struct ModelCore {
    pub name: String,
    pub vars: Vec<VariableData>,
    pub constraints: Vec<ConstraintData>,
    pub objective: Option<ObjectiveData>,
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
        });
        id
    }

    pub fn set_objective(
        &mut self,
        coeffs: IndexMap<VarId, f64>,
        constant: f64,
        sense: ObjSense,
    ) {
        self.sense = sense;
        self.objective = Some(ObjectiveData {
            coeffs,
            constant,
            sense,
        });
    }

    pub fn clear_objective(&mut self) {
        self.objective = None;
    }
}

pub fn upgrade_model(weak: &Weak<RefCell<ModelCore>>) -> PyResult<Rc<RefCell<ModelCore>>> {
    weak.upgrade().ok_or_else(|| {
        PyRuntimeError::new_err("Underlying model has been dropped; handle is no longer valid")
    })
}
