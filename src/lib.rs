//! PuLP Rust extension: one module per pyclass (Variable, Constraint, AffineExpr, Model)
//! plus a shared types module.

use pyo3::prelude::*;

mod types;

mod variable;
mod constraint;
mod model;
mod affine_expr;

use affine_expr::AffineExpr;
use constraint::Constraint;
use model::Model;
use types::{Category, ObjSense, Sense};
use variable::Variable;

/// Python module definition. This will be exposed as `pulp._rustcore`.
#[pymodule]
fn _rustcore(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_class::<Model>()?;
    m.add_class::<Variable>()?;
    m.add_class::<Constraint>()?;
    m.add_class::<AffineExpr>()?;
    m.add_class::<Category>()?;
    m.add_class::<Sense>()?;
    m.add_class::<ObjSense>()?;
    Ok(())
}
