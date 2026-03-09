//! Python-exposed AffineExpr (sum of coeff * variable + constant).

use indexmap::IndexMap;
use pyo3::prelude::*;

use crate::model::Model;
use crate::types::VarId;
use crate::variable::Variable;

/// Affine expression: sum_i coeff_i * x_i + constant.
#[pyclass]
#[derive(Clone)]
pub struct AffineExpr {
    pub terms: IndexMap<VarId, f64>,
    pub constant: f64,
}

#[pymethods]
impl AffineExpr {
    #[new]
    fn new() -> Self {
        Self {
            terms: IndexMap::new(),
            constant: 0.0,
        }
    }

    fn add_term(&mut self, var: &Variable, coeff: f64) {
        let entry = self.terms.entry(var.id()).or_insert(0.0);
        *entry += coeff;
    }

    fn set_constant(&mut self, constant: f64) {
        self.constant = constant;
    }

    fn add_expr(&mut self, other: &AffineExpr, sign: f64) {
        for (var_id, coeff) in &other.terms {
            let entry = self.terms.entry(*var_id).or_insert(0.0);
            *entry += coeff * sign;
        }
        self.constant += other.constant * sign;
    }

    fn scale(&mut self, factor: f64) {
        for coeff in self.terms.values_mut() {
            *coeff *= factor;
        }
        self.constant *= factor;
    }

    fn terms_with_variables(&self, model: &Model) -> Vec<(Variable, f64)> {
        self.terms
            .iter()
            .map(|(var_id, coeff)| (model.get_variable(*var_id), *coeff))
            .collect()
    }

    fn clone_expr(&self) -> Self {
        self.clone()
    }

    /// Number of variable terms (excluding constant).
    fn num_terms(&self) -> usize {
        self.terms.len()
    }

    /// Coefficient for a variable (0.0 if not present).
    fn get_coeff(&self, var: &Variable) -> f64 {
        self.terms.get(&var.id()).copied().unwrap_or(0.0)
    }

    #[getter]
    fn constant(&self) -> f64 {
        self.constant
    }
}
