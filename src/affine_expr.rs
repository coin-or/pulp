//! Python-exposed AffineExpr (sum of coeff * variable + constant).

use std::cell::RefCell;
use std::rc::{Rc, Weak};

use indexmap::IndexMap;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use crate::format;
use crate::model::Model;
use crate::types::{ModelCore, Sense, VarId};
use crate::variable::Variable;

/// Affine expression: sum_i coeff_i * x_i + constant.
/// Optionally carries sense (for pending constraints) and name.
/// Holds a weak model ref acquired automatically from the first variable.
#[pyclass(unsendable)]
#[derive(Clone, Debug)]
pub struct AffineExpr {
    pub terms: IndexMap<VarId, f64>,
    pub constant: f64,
    pub sense: Option<Sense>,
    pub name: Option<String>,
    pub model: Option<Weak<RefCell<ModelCore>>>,
}

#[pymethods]
impl AffineExpr {
    #[new]
    fn new() -> Self {
        Self {
            terms: IndexMap::new(),
            constant: 0.0,
            sense: None,
            name: None,
            model: None,
        }
    }

    fn add_term(&mut self, var: &Variable, coeff: f64) {
        if self.model.is_none() {
            self.model = Some(var.model.clone());
        }
        let entry = self.terms.entry(var.id()).or_insert(0.0);
        *entry += coeff;
    }

    fn set_constant(&mut self, constant: f64) {
        self.constant = constant;
    }

    fn add_expr(&mut self, other: &AffineExpr, sign: f64) -> PyResult<()> {
        if self.model.is_none() {
            self.model = other.model.clone();
        }
        if let (Some(ref s), Some(ref o)) = (&self.model, &other.model) {
            if !Rc::ptr_eq(&s.upgrade().unwrap(), &o.upgrade().unwrap()) {
                return Err(PyValueError::new_err("Models are not the same"));
            }
        }
        for (var_id, coeff) in &other.terms {
            let entry = self.terms.entry(*var_id).or_insert(0.0);
            *entry += coeff * sign;
        }
        self.constant += other.constant * sign;
        Ok(())
    }

    fn scale(&mut self, factor: f64) {
        for coeff in self.terms.values_mut() {
            *coeff *= factor;
        }
        self.constant *= factor;
    }

    /// Resolve VarId -> Variable handles via the provided model.
    fn terms_with_variables(&self, model: &Model) -> Vec<(Variable, f64)> {
        self.terms
            .iter()
            .map(|(var_id, coeff)| (model.get_variable(*var_id), *coeff))
            .collect()
    }

    fn clone_expr(&self) -> Self {
        self.clone()
    }

    fn num_terms(&self) -> usize {
        self.terms.len()
    }

    fn get_coeff(&self, var: &Variable) -> f64 {
        self.terms.get(&var.id()).copied().unwrap_or(0.0)
    }

    #[getter]
    fn constant(&self) -> f64 {
        self.constant
    }

    #[getter]
    fn sense(&self) -> Option<Sense> {
        self.sense
    }

    fn set_sense(&mut self, sense: Sense) {
        self.sense = Some(sense);
    }

    fn clear_sense(&mut self) {
        self.sense = None;
    }

    #[getter]
    fn name(&self) -> Option<String> {
        self.name.clone()
    }

    fn set_name(&mut self, name: String) {
        self.name = Some(name);
    }

    fn clear_name(&mut self) {
        self.name = None;
    }

    /// Resolve VarId -> Variable handle pairs via the internal weak model ref.
    fn items(&self) -> Vec<(Variable, f64)> {
        let weak = match &self.model {
            Some(w) => w,
            None => return Vec::new(),
        };
        if weak.upgrade().is_none() {
            return Vec::new();
        }
        self.terms
            .iter()
            .map(|(var_id, coeff)| {
                (
                    Variable {
                        id: *var_id,
                        model: weak.clone(),
                    },
                    *coeff,
                )
            })
            .collect()
    }

    fn keys(&self) -> Vec<Variable> {
        let weak = match &self.model {
            Some(w) => w,
            None => return Vec::new(),
        };
        if weak.upgrade().is_none() {
            return Vec::new();
        }
        self.terms
            .keys()
            .map(|var_id| Variable {
                id: *var_id,
                model: weak.clone(),
            })
            .collect()
    }

    fn values(&self) -> Vec<f64> {
        self.terms.values().copied().collect()
    }

    /// Compute the expression value: sum(var.value * coeff) + constant.
    /// Returns None if any variable has no value set.
    fn value(&self) -> Option<f64> {
        let weak = match &self.model {
            Some(w) => w,
            None => {
                return if self.terms.is_empty() {
                    Some(self.constant)
                } else {
                    None
                }
            }
        };
        let core_rc = weak.upgrade()?;
        let core = core_rc.borrow();
        let mut total = self.constant;
        for (var_id, coeff) in &self.terms {
            let val = core.vars.get(*var_id)?.value?;
            total += val * coeff;
        }
        Some(total)
    }

    /// Returns (variable_name, coeff) pairs for Python serialization.
    fn var_name_coeffs(&self) -> Vec<(String, f64)> {
        let weak = match &self.model {
            Some(w) => w,
            None => return Vec::new(),
        };
        let core_rc = match weak.upgrade() {
            Some(rc) => rc,
            None => return Vec::new(),
        };
        let core = core_rc.borrow();
        self.terms
            .iter()
            .map(|(var_id, coeff)| {
                let name = core
                    .vars
                    .get(*var_id)
                    .map(|v| v.name.clone())
                    .unwrap_or_default();
                (name, *coeff)
            })
            .collect()
    }

    fn __str__(&self) -> String {
        self.format_expr()
    }

    fn __repr__(&self) -> String {
        self.format_expr()
    }

    #[staticmethod]
    fn from_variable(var: &Variable) -> Self {
        let mut terms = IndexMap::new();
        terms.insert(var.id(), 1.0);
        Self {
            terms,
            constant: 0.0,
            sense: None,
            name: None,
            model: Some(var.model.clone()),
        }
    }

    #[staticmethod]
    fn from_constant(value: f64) -> Self {
        Self {
            terms: IndexMap::new(),
            constant: value,
            sense: None,
            name: None,
            model: None,
        }
    }

    /// Combine sense when adding two constraint-like expressions.
    #[pyo3(signature = (other_sense, sign))]
    fn combine_sense(&mut self, other_sense: Option<Sense>, sign: f64) {
        if self.sense.is_some() {
            return;
        }
        if let Some(s) = other_sense {
            if sign < 0.0 {
                self.sense = Some(flip_sense(s));
            } else {
                self.sense = Some(s);
            }
        }
    }

    // ── Formatting methods (delegate to format.rs) ──

    /// Returns variables sorted by name, as Variable handles.
    fn sorted_keys(&self) -> Vec<Variable> {
        let weak = match &self.model {
            Some(w) => w,
            None => return Vec::new(),
        };
        let core_rc = match weak.upgrade() {
            Some(rc) => rc,
            None => return Vec::new(),
        };
        let core = core_rc.borrow();
        let mut pairs: Vec<(VarId, String)> = self
            .terms
            .keys()
            .map(|vid| {
                let name = core
                    .vars
                    .get(*vid)
                    .map(|v| v.name.clone())
                    .unwrap_or_default();
                (*vid, name)
            })
            .collect();
        pairs.sort_by(|a, b| a.1.cmp(&b.1));
        pairs
            .into_iter()
            .map(|(vid, _)| Variable {
                id: vid,
                model: weak.clone(),
            })
            .collect()
    }

    /// Evaluate using defaults for missing values.
    fn value_or_default(&self) -> f64 {
        let weak = match &self.model {
            Some(w) => w,
            None => return self.constant,
        };
        let core_rc = match weak.upgrade() {
            Some(rc) => rc,
            None => return self.constant,
        };
        let core = core_rc.borrow();
        let mut total = self.constant;
        for (var_id, coeff) in &self.terms {
            if let Some(vd) = core.vars.get(*var_id) {
                let v = vd.value.unwrap_or_else(|| format::default_value(vd.lb, vd.ub));
                total += v * coeff;
            }
        }
        total
    }

    /// CPLEX LP format: variable-terms portion.
    fn as_cplex_variables_only(&self, name: &str) -> (Vec<String>, Vec<String>) {
        let sorted = self.sorted_name_coeff_pairs();
        format::cplex_variables_only(&sorted, name)
    }

    /// CPLEX LP affine expression string.
    #[pyo3(signature = (name, include_constant=true))]
    fn as_cplex_lp_affine_expression(&self, name: &str, include_constant: bool) -> String {
        let sorted = self.sorted_name_coeff_pairs();
        format::cplex_lp_affine_expression(&sorted, self.constant, name, include_constant)
    }

    /// CPLEX LP constraint string (with sense and RHS).
    fn as_cplex_lp_constraint(&self, name: &str) -> PyResult<String> {
        let sense = self
            .sense
            .ok_or_else(|| PyValueError::new_err("Cannot format constraint without sense"))?;
        let sorted = self.sorted_name_coeff_pairs();
        let rhs = if self.constant == 0.0 || self.constant == -0.0 {
            0.0
        } else {
            -self.constant
        };
        Ok(format::cplex_lp_constraint(
            &sorted,
            sense,
            rhs,
            name,
            self.terms.is_empty(),
        ))
    }

    /// Human-readable expression string.
    #[pyo3(signature = (include_constant=true))]
    fn str_expr(&self, include_constant: bool) -> String {
        let sorted = self.sorted_name_coeff_pairs();
        format::str_expr(&sorted, self.constant, include_constant)
    }

    /// Full __str__ replacement: includes sense and RHS if present.
    fn str_with_sense(&self) -> String {
        if let Some(sense) = self.sense {
            let sorted = self.sorted_name_coeff_pairs();
            let lhs = format::str_expr(&sorted, 0.0, false);
            format!("{} {} {}", lhs, sense.lp_symbol(), -self.constant as f64)
        } else {
            let sorted = self.sorted_name_coeff_pairs();
            format::str_expr(&sorted, self.constant, true)
        }
    }

    /// Python __repr__ equivalent.
    fn repr_expr(&self) -> String {
        let sorted = self.sorted_name_coeff_pairs();
        format::repr_expr(&sorted, self.constant, self.sense)
    }
}

// ── Private helpers ──

impl AffineExpr {
    fn format_expr(&self) -> String {
        if self.terms.is_empty() {
            return format!("{}", self.constant);
        }

        let names: Vec<(String, f64)> = if let Some(ref weak) = self.model {
            if let Some(core_rc) = weak.upgrade() {
                let core = core_rc.borrow();
                self.terms
                    .iter()
                    .map(|(var_id, coeff)| {
                        let name = core
                            .vars
                            .get(*var_id)
                            .map(|v| v.name.clone())
                            .unwrap_or_else(|| format!("x{}", var_id));
                        (name, *coeff)
                    })
                    .collect()
            } else {
                self.terms
                    .iter()
                    .map(|(var_id, coeff)| (format!("x{}", var_id), *coeff))
                    .collect()
            }
        } else {
            self.terms
                .iter()
                .map(|(var_id, coeff)| (format!("x{}", var_id), *coeff))
                .collect()
        };

        let mut parts = Vec::new();
        for (i, (name, coeff)) in names.iter().enumerate() {
            if i == 0 {
                if *coeff == 1.0 {
                    parts.push(name.clone());
                } else if *coeff == -1.0 {
                    parts.push(format!("-{}", name));
                } else {
                    parts.push(format!("{}*{}", coeff, name));
                }
            } else if *coeff == 1.0 {
                parts.push(format!("+ {}", name));
            } else if *coeff == -1.0 {
                parts.push(format!("- {}", name));
            } else if *coeff < 0.0 {
                parts.push(format!("- {}*{}", -coeff, name));
            } else {
                parts.push(format!("+ {}*{}", coeff, name));
            }
        }
        if self.constant != 0.0 {
            if self.constant > 0.0 {
                parts.push(format!("+ {}", self.constant));
            } else {
                parts.push(format!("- {}", -self.constant));
            }
        }
        parts.join(" ")
    }

    /// Collect (name, coeff) pairs sorted by variable name.
    pub(crate) fn sorted_name_coeff_pairs(&self) -> Vec<(String, f64)> {
        let weak = match &self.model {
            Some(w) => w,
            None => return Vec::new(),
        };
        let core_rc = match weak.upgrade() {
            Some(rc) => rc,
            None => return Vec::new(),
        };
        let core = core_rc.borrow();
        format::sorted_pairs_from_coeffs(&self.terms, &core)
    }
}

fn flip_sense(s: Sense) -> Sense {
    match s {
        Sense::LessEqual => Sense::GreaterEqual,
        Sense::GreaterEqual => Sense::LessEqual,
        Sense::Equal => Sense::Equal,
    }
}
